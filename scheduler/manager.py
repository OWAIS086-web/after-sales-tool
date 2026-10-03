"""
Scheduler Manager

Core scheduler management using APScheduler BackgroundScheduler.
Handles job loading, scheduling, execution, and lifecycle management.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from datetime import datetime, timezone
import os

from scheduler.config_parser import parse_schedule, format_schedule_human, get_next_run_display
from utils.logger import LoggerManager

logger = LoggerManager.get_logger('scheduler')


# Standalone job wrapper (cannot be instance method due to APScheduler serialization)
def execute_scheduled_job(job_id, job_config, job_func):
    """
    Standalone wrapper for job execution with logging and error handling.
    This must be a module-level function (not instance method) for APScheduler serialization.

    Note: Gets Flask app from global scheduler_manager instance to avoid pickling issues.

    Args:
        job_id (str): Job identifier
        job_config (dict): Job configuration
        job_func (callable): Job function to execute
    """
    # Get Flask app from global scheduler_manager
    # This avoids passing the app as an argument (which can't be pickled)
    flask_app = scheduler_manager.flask_app

    if not flask_app:
        logger.error(f"[{job_id}] Flask app not available in scheduler_manager")
        return

    # Use Flask app context
    with flask_app.app_context():
        logger.info(f"[{job_id}] Starting scheduled execution")
        start_time = datetime.now()

        try:
            # Execute job
            result = job_func(job_config, job_id)

            # Log result
            duration = (datetime.now() - start_time).total_seconds()

            if result and result.get('skipped'):
                logger.info(f"[{job_id}] Skipped: {result.get('reason')} ({duration:.1f}s)")
            elif result and result.get('success'):
                records = result.get('posts_scraped', result.get('records_imported', 0))
                logger.info(f"[{job_id}] Completed successfully: {records} records ({duration:.1f}s)")
            else:
                logger.warning(f"[{job_id}] Completed with unknown status ({duration:.1f}s)")

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"[{job_id}] Failed after {duration:.1f}s: {e}", exc_info=True)


class SchedulerManager:
    """
    Manages automated scraping scheduler using APScheduler.

    Responsibilities:
    - Initialize BackgroundScheduler with Flask app
    - Load job configurations from YAML
    - Schedule jobs with APScheduler
    - Provide job management API (start, stop, reload)
    - Track job execution status
    """

    def __init__(self):
        self.scheduler = None
        self.config = None
        self.flask_app = None
        self._initialized = False
        self._job_functions = None

    def init_app(self, flask_app):
        """
        Initialize scheduler with Flask app.

        Args:
            flask_app: Flask application instance
        """
        if self._initialized:
            logger.warning("Scheduler already initialized")
            return

        self.flask_app = flask_app

        # Load configuration
        from config.config_loader import get_config
        self.config = get_config()

        # Check if scheduling is enabled
        if not self.config.get('scheduling.enabled', False):
            logger.info("Scheduling disabled in configuration")
            return

        try:
            # Ensure data directory exists
            data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
            os.makedirs(data_dir, exist_ok=True)

            # Configure job store (SQLite persistence)
            job_store_config = self.config.get('scheduling.job_store', {})
            job_store_path = job_store_config.get('path', 'data/scheduler_jobs.db')

            # Make path absolute if relative
            if not os.path.isabs(job_store_path):
                job_store_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), job_store_path)

            jobstores = {
                'default': SQLAlchemyJobStore(url=f'sqlite:///{job_store_path}')
            }

            # Configure executor (thread pool)
            max_workers = self.config.get('scheduling.max_concurrent_jobs', 1)
            executors = {
                'default': ThreadPoolExecutor(max_workers=max_workers)
            }

            # Job defaults
            job_defaults = {
                'coalesce': self.config.get('scheduling.coalesce', True),
                'max_instances': 1,  # Prevent same job running concurrently
                'misfire_grace_time': self.config.get('scheduling.misfire_grace_time', 3600)
            }

            # Get timezone
            tz_name = self.config.get('scheduling.timezone', 'Asia/Karachi')

            # Create scheduler
            self.scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
                timezone=tz_name
            )

            # Add event listeners
            self.scheduler.add_listener(self._on_job_executed, EVENT_JOB_EXECUTED)
            self.scheduler.add_listener(self._on_job_error, EVENT_JOB_ERROR)
            self.scheduler.add_listener(self._on_job_missed, EVENT_JOB_MISSED)

            # Load job functions
            self._load_job_functions()

            # Load and schedule jobs
            self._load_jobs()

            # Start scheduler
            self.scheduler.start()
            self._initialized = True

            logger.info(f"Scheduler initialized with timezone {tz_name}")
            job_count = len(self.scheduler.get_jobs())
            logger.info(f"Loaded {job_count} scheduled jobs")

            # Log next run times
            self._log_next_runs()

        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}", exc_info=True)
            # Don't raise - allow app to continue without scheduler
            self._initialized = False

    def _load_job_functions(self):
        """Load job function registry."""
        try:
            from scheduler.jobs import JOB_FUNCTIONS
            self._job_functions = JOB_FUNCTIONS
        except ImportError as e:
            logger.error(f"Failed to import job functions: {e}")
            self._job_functions = {}

    def _load_jobs(self):
        """Load jobs from configuration and schedule them."""
        jobs_config = self.config.get('scheduling.jobs', {})

        if not jobs_config:
            logger.warning("No jobs configured in scheduling.jobs")
            return

        for job_id, job_config in jobs_config.items():
            try:
                # Check if job is enabled
                if not job_config.get('enabled', False):
                    logger.info(f"Job '{job_id}' is disabled, skipping scheduling")
                    continue

                # Schedule the job
                self.schedule_job(job_id, job_config)
                logger.info(f"Scheduled job: {job_id}")

            except Exception as e:
                logger.error(f"Failed to schedule job '{job_id}': {e}", exc_info=True)

    def schedule_job(self, job_id, job_config):
        """
        Schedule a single job from configuration.

        Args:
            job_id (str): Unique job identifier
            job_config (dict): Job configuration from YAML
        """
        # Get job type
        job_type = job_config.get('type')
        if not job_type:
            raise ValueError(f"Job '{job_id}' missing 'type' field")

        # Get job function
        if not self._job_functions:
            self._load_job_functions()

        job_func = self._job_functions.get(job_type)
        if not job_func:
            raise ValueError(f"Unknown job type '{job_type}' for job '{job_id}'")

        # Parse schedule with configured timezone
        schedule_config = job_config.get('schedule', {})
        tz_name = self.config.get('scheduling.timezone', 'Asia/Karachi')
        trigger = parse_schedule(schedule_config, timezone=tz_name)

        # Remove existing job if any
        existing_job = self.scheduler.get_job(job_id)
        if existing_job:
            self.scheduler.remove_job(job_id)

        # Schedule job with APScheduler (use standalone function for serialization)
        self.scheduler.add_job(
            func=execute_scheduled_job,
            trigger=trigger,
            args=[job_id, job_config, job_func],
            id=job_id,
            name=job_id,
            replace_existing=True
        )

        schedule_str = format_schedule_human(schedule_config)
        logger.info(f"Scheduled '{job_id}' ({job_type}): {schedule_str}")

    def _on_job_executed(self, event):
        """Handle job executed event."""
        logger.debug(f"Job executed: {event.job_id}")

    def _on_job_error(self, event):
        """Handle job error event."""
        logger.error(f"Job error: {event.job_id} - {event.exception}")

    def _on_job_missed(self, event):
        """Handle job missed event."""
        logger.warning(f"Job missed: {event.job_id}")

    def reload_jobs(self):
        """Reload all jobs from updated configuration."""
        if not self.scheduler:
            logger.warning("Scheduler not initialized, cannot reload jobs")
            return False

        logger.info("Reloading jobs from configuration...")

        try:
            # Remove all existing jobs
            self.scheduler.remove_all_jobs()

            # Reload config
            from config.config_loader import get_config
            self.config = get_config()

            # Load jobs again
            self._load_jobs()

            job_count = len(self.scheduler.get_jobs())
            logger.info(f"Reloaded {job_count} jobs")
            self._log_next_runs()

            return True

        except Exception as e:
            logger.error(f"Failed to reload jobs: {e}", exc_info=True)
            return False

    def get_scheduled_jobs(self):
        """
        Get all scheduled jobs with their details (both enabled and disabled).

        Returns:
            list: List of job dictionaries
        """
        jobs_config = self.config.get('scheduling.jobs', {}) if self.config else {}
        jobs = []

        # Get all jobs from config (enabled and disabled)
        for job_id, job_config in jobs_config.items():
            schedule_config = job_config.get('schedule', {})
            
            # Try to get next run time from scheduler if job is scheduled
            next_run = None
            if self.scheduler:
                job = self.scheduler.get_job(job_id)
                if job:
                    next_run = getattr(job, 'next_run_time', None)
                    if next_run is None:
                        try:
                            next_run = job.trigger.get_next_fire_time(None, datetime.now())
                        except:
                            next_run = None

            jobs.append({
                'id': job_id,
                'name': job_id,
                'type': job_config.get('type', 'unknown'),
                'company_id': job_config.get('company_id', 'unknown'),
                'enabled': job_config.get('enabled', False),
                'next_run_time': next_run,
                'next_run_display': get_next_run_display(next_run) if next_run else 'Not scheduled',
                'schedule_display': format_schedule_human(schedule_config),
                'trigger': str(self.scheduler.get_job(job_id).trigger) if self.scheduler and self.scheduler.get_job(job_id) else 'N/A'
            })

        return jobs

    def get_job_config(self, job_id):
        """
        Get configuration for a specific job.

        Args:
            job_id (str): Job identifier

        Returns:
            dict: Job configuration or None
        """
        if not self.config:
            return None

        jobs_config = self.config.get('scheduling.jobs', {})
        return jobs_config.get(job_id)

    def run_job_immediately(self, job_id):
        """
        Manually trigger immediate execution of a job.

        Args:
            job_id (str): Job identifier

        Returns:
            bool: True if job was triggered
        """
        if not self.scheduler:
            logger.error("Scheduler not initialized")
            return False

        try:
            job = self.scheduler.get_job(job_id)
            if not job:
                logger.error(f"Job '{job_id}' not found")
                return False

            # Get job config
            job_config = self.get_job_config(job_id)
            if not job_config:
                logger.error(f"Job config not found for '{job_id}'")
                return False

            # Get job function
            job_type = job_config.get('type')
            job_func = self._job_functions.get(job_type)
            if not job_func:
                logger.error(f"Job function not found for type '{job_type}'")
                return False

            # Run job in background
            import threading
            thread = threading.Thread(
                target=execute_scheduled_job,
                args=[job_id, job_config, job_func],
                daemon=True
            )
            thread.start()

            logger.info(f"Manually triggered job: {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to trigger job '{job_id}': {e}", exc_info=True)
            return False

    def toggle_job(self, job_id, enabled):
        """
        Enable or disable a job.

        Updates both in-memory config and config.yml file.

        Args:
            job_id (str): Job identifier
            enabled (bool): Whether to enable or disable

        Returns:
            bool: True if successful
        """
        if not self.scheduler:
            return False

        try:
            # Get current job config
            job_config = self.get_job_config(job_id)
            if not job_config:
                logger.error(f"Job '{job_id}' not found in configuration")
                return False

            # Update in-memory config
            job_config['enabled'] = enabled

            # Update config.yml file
            try:
                from ruamel.yaml import YAML
                YAML_AVAILABLE = True
            except ImportError:
                import yaml as yaml_fallback
                YAML = None
                YAML_AVAILABLE = False

            import os
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.yml')

            # Use ruamel.yaml to preserve comments if available
            if YAML_AVAILABLE:
                yaml = YAML()
                yaml.preserve_quotes = True
                yaml.default_flow_style = False
                yaml.width = 4096

                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml.load(f)
            else:
                # Fallback to PyYAML
                with open(config_path, 'r', encoding='utf-8') as f:
                    config_data = yaml_fallback.safe_load(f)

            # Update the job's enabled status
            if 'scheduling' in config_data and 'jobs' in config_data['scheduling']:
                if job_id in config_data['scheduling']['jobs']:
                    config_data['scheduling']['jobs'][job_id]['enabled'] = enabled

                    # Write back to config.yml
                    if YAML_AVAILABLE:
                        with open(config_path, 'w', encoding='utf-8') as f:
                            yaml.dump(config_data, f)
                    else:
                        with open(config_path, 'w', encoding='utf-8') as f:
                            yaml_fallback.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

                    logger.info(f"Updated config.yml: Job '{job_id}' set to enabled={enabled}")

            # Update scheduler
            if enabled:
                # Re-add job if it was removed
                self.schedule_job(job_id, job_config)
                logger.info(f"Enabled job: {job_id}")
            else:
                # Remove job from scheduler
                existing = self.scheduler.get_job(job_id)
                if existing:
                    self.scheduler.remove_job(job_id)
                    logger.info(f"Disabled job: {job_id}")

            return True

        except Exception as e:
            logger.error(f"Failed to toggle job '{job_id}': {e}", exc_info=True)
            return False

    def get_scheduler_status(self):
        """
        Get overall scheduler status.

        Returns:
            dict: Status information
        """
        if not self.scheduler:
            jobs_config = self.config.get('scheduling.jobs', {}) if self.config else {}
            return {
                'running': False,
                'initialized': self._initialized,
                'job_count': len(jobs_config),
                'next_job': None
            }

        jobs = self.get_scheduled_jobs()
        next_job = None

        if jobs:
            # Find job with earliest next_run_time (only from enabled jobs)
            enabled_jobs = [j for j in jobs if j['enabled'] and j['next_run_time']]
            
            if enabled_jobs:
                def sort_key(x):
                    nrt = x['next_run_time']
                    if nrt is None:
                        return datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
                    if nrt.tzinfo is None:
                        return nrt.replace(tzinfo=timezone.utc)
                    return nrt

                first_job = sorted(enabled_jobs, key=sort_key)[0]
                next_job = {
                    'id': first_job['id'],
                    'next_run_time': first_job['next_run_time'].isoformat() if first_job['next_run_time'] else None,
                    'next_run_display': first_job['next_run_display']
                }

        return {
            'running': self.scheduler.running if self.scheduler else False,
            'initialized': self._initialized,
            'job_count': len(jobs),
            'next_job': next_job
        }

    def shutdown(self):
        """Shutdown scheduler gracefully."""
        if self.scheduler and self.scheduler.running:
            logger.info("Shutting down scheduler...")
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler shutdown complete")

    def _log_next_runs(self):
        """Log next run times for all scheduled jobs."""
        jobs = self.get_scheduled_jobs()
        if jobs:
            logger.info("Next scheduled runs:")

            # Use a helper function for timezone-aware sorting
            def sort_key(x):
                nrt = x['next_run_time']
                if nrt is None:
                    return datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
                if nrt.tzinfo is None:
                    return nrt.replace(tzinfo=timezone.utc)
                return nrt

            for job in sorted(jobs, key=sort_key):
                next_run = job['next_run_time']
                if next_run:
                    logger.info(f"  - {job['id']}: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    logger.info(f"  - {job['id']}: No next run scheduled")


# Global instance
scheduler_manager = SchedulerManager()
