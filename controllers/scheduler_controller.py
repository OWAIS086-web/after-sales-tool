"""
Scheduler Controller

Flask routes for scheduler admin dashboard.
Admin access controlled via config.yml - no database changes needed.
EMAIL is the source of truth for admin authentication.
Supports multiple admins.
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from scheduler.decorators import is_admin_user, get_admin_users_display, admin_required
from scheduler import job_history
from scheduler.config_parser import format_schedule_human
from utils.logger import LoggerManager
from datetime import datetime

logger = LoggerManager.get_logger('scheduler')

bp = Blueprint('scheduler', __name__, url_prefix='/admin')


@bp.route('/scheduler')
@login_required
@admin_required
def dashboard():
    """Scheduler admin dashboard."""
    from scheduler.manager import scheduler_manager
    from config.config_loader import get_config

    config = get_config()

    # Get scheduler status
    scheduler_status = scheduler_manager.get_scheduler_status()

    # Get all scheduled jobs with details
    jobs = scheduler_manager.get_scheduled_jobs()
    jobs_config = config.get('scheduling.jobs', {})

    # Enrich job data with config and last execution
    enriched_jobs = []
    for job in jobs:
        job_cfg = jobs_config.get(job['id'], {})
        last_exec = job_history.get_last_execution(job['id'])

        enriched_jobs.append({
            'id': job['id'],
            'type': job['type'],
            'company_id': job['company_id'],
            'enabled': job['enabled'],
            'schedule_display': job['schedule_display'],
            'next_run_time': job['next_run_time'],
            'next_run_display': job['next_run_display'],
            'parameters': job_cfg.get('parameters', {}),
            'last_execution': last_exec
        })

    # Get recent executions for history
    recent_executions = job_history.get_recent_executions(limit=20)

    # Get execution stats
    stats = job_history.get_execution_stats()

    # Get admin users for display
    admin_users = get_admin_users_display()

    return render_template('scheduler_dashboard.html',
        user=current_user,
        scheduler_status=scheduler_status,
        jobs=enriched_jobs,
        recent_executions=recent_executions,
        stats=stats,
        admin_users=admin_users,
        config=config
    )


@bp.route('/api/scheduler/status')
@login_required
@admin_required
def get_status():
    """Get scheduler status as JSON."""
    from scheduler.manager import scheduler_manager

    status = scheduler_manager.get_scheduler_status()
    jobs = scheduler_manager.get_scheduled_jobs()

    # Add last execution for each job
    for job in jobs:
        last_exec = job_history.get_last_execution(job['id'])
        if last_exec:
            job['last_execution'] = {
                'status': last_exec['status'],
                'started_at': last_exec['started_at'],
                'duration': job_history.format_duration(last_exec['duration_seconds']),
                'records': last_exec['records_processed']
            }
        # Convert datetime to string for JSON
        if job['next_run_time']:
            job['next_run_time'] = job['next_run_time'].isoformat()

    return jsonify({
        'status': status,
        'jobs': jobs,
        'stats': job_history.get_execution_stats()
    })


@bp.route('/api/scheduler/toggle/<job_id>', methods=['POST'])
@login_required
@admin_required
def toggle_job(job_id):
    """Enable or disable a job."""
    from scheduler.manager import scheduler_manager

    data = request.get_json() or {}
    enabled = data.get('enabled', True)

    success = scheduler_manager.toggle_job(job_id, enabled)

    if success:
        # Reload config to pick up changes
        try:
            from config.config_loader import reload_config
            reload_config()
        except Exception as e:
            logger.warning(f"Failed to reload config after toggle: {e}")

        action = 'enabled' if enabled else 'disabled'
        logger.info(f"Job '{job_id}' {action} by admin {current_user.username}")
        return jsonify({
            'success': True,
            'message': f"Job '{job_id}' {action}"
        })
    else:
        return jsonify({
            'success': False,
            'error': f"Failed to toggle job '{job_id}'"
        }), 400


@bp.route('/api/scheduler/run-now/<job_id>', methods=['POST'])
@login_required
@admin_required
def run_job_now(job_id):
    """Manually trigger immediate execution of a job."""
    from scheduler.manager import scheduler_manager

    logger.info(f"Manual job trigger requested by admin {current_user.username}: {job_id}")

    success = scheduler_manager.run_job_immediately(job_id)

    if success:
        return jsonify({
            'success': True,
            'message': f"Job '{job_id}' triggered"
        })
    else:
        return jsonify({
            'success': False,
            'error': f"Failed to trigger job '{job_id}'"
        }), 400


@bp.route('/api/scheduler/history')
@login_required
@admin_required
def get_history():
    """Get execution history."""
    job_id = request.args.get('job_id')
    limit = int(request.args.get('limit', 50))

    executions = job_history.get_recent_executions(job_id=job_id, limit=limit)

    # Format for display
    for exec_record in executions:
        exec_record['duration_display'] = job_history.format_duration(exec_record['duration_seconds'])

    return jsonify({
        'success': True,
        'executions': executions
    })


@bp.route('/api/scheduler/history/<job_id>')
@login_required
@admin_required
def get_job_history(job_id):
    """Get execution history for a specific job."""
    limit = int(request.args.get('limit', 20))

    executions = job_history.get_recent_executions(job_id=job_id, limit=limit)

    # Format for display
    for exec_record in executions:
        exec_record['duration_display'] = job_history.format_duration(exec_record['duration_seconds'])

    return jsonify({
        'success': True,
        'job_id': job_id,
        'executions': executions
    })


@bp.route('/api/scheduler/update-schedule/<job_id>', methods=['POST'])
@login_required
@admin_required
def update_schedule(job_id):
    """Update job schedule in config.yml and reload scheduler."""
    try:
        from ruamel.yaml import YAML
        from ruamel.yaml.scalarstring import DoubleQuotedScalarString
        YAML_AVAILABLE = True
    except ImportError:
        import yaml as yaml_fallback
        YAML = None
        DoubleQuotedScalarString = None
        YAML_AVAILABLE = False
    import os
    from scheduler.manager import scheduler_manager

    data = request.get_json() or {}

    # Validate input
    frequency = data.get('frequency')
    time_str = data.get('time')
    enabled = data.get('enabled', True)

    if not frequency or frequency not in ['daily', 'weekly', 'monthly']:
        return jsonify({
            'success': False,
            'error': 'Invalid frequency. Must be daily, weekly, or monthly'
        }), 400

    if not time_str:
        return jsonify({
            'success': False,
            'error': 'Time is required (HH:MM format)'
        }), 400

    # Build schedule object
    # NOTE: Time must be stored as string to prevent YAML sexagesimal interpretation
    schedule = {
        'frequency': frequency,
        'time': str(time_str)  # Ensure it's a string
    }

    if frequency == 'weekly':
        day_of_week = data.get('day_of_week')
        if not day_of_week:
            return jsonify({
                'success': False,
                'error': 'day_of_week is required for weekly schedule'
            }), 400
        schedule['day_of_week'] = day_of_week.lower()

    elif frequency == 'monthly':
        day_of_month = data.get('day_of_month')
        if not day_of_month:
            return jsonify({
                'success': False,
                'error': 'day_of_month is required for monthly schedule'
            }), 400
        try:
            day_of_month = int(day_of_month)
            if not (1 <= day_of_month <= 31):
                raise ValueError()
        except:
            return jsonify({
                'success': False,
                'error': 'day_of_month must be between 1 and 31'
            }), 400
        schedule['day_of_month'] = day_of_month

    try:
        # Read config.yml
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'config.yml')

        # Use ruamel.yaml to preserve comments if available
        if YAML:
            yaml = YAML()
            yaml.preserve_quotes = True
            yaml.default_flow_style = False
            yaml.width = 4096  # Prevent line wrapping

            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.load(f)
        else:
            # Fallback to PyYAML (won't preserve comments)
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml_fallback.safe_load(f)

        # Update the job's schedule
        if 'scheduling' not in config_data:
            config_data['scheduling'] = {}
        if 'jobs' not in config_data['scheduling']:
            config_data['scheduling']['jobs'] = {}
        if job_id not in config_data['scheduling']['jobs']:
            return jsonify({
                'success': False,
                'error': f'Job {job_id} not found in configuration'
            }), 404

        # Update schedule and enabled status
        # Use DoubleQuotedScalarString for time to prevent YAML sexagesimal interpretation
        if YAML_AVAILABLE and DoubleQuotedScalarString:
            schedule['time'] = DoubleQuotedScalarString(schedule['time'])

        config_data['scheduling']['jobs'][job_id]['schedule'] = schedule
        config_data['scheduling']['jobs'][job_id]['enabled'] = enabled

        # Update max_posts if provided (for pakwheels and reddit)
        max_posts = data.get('max_posts')
        if max_posts is not None:
            if 'parameters' not in config_data['scheduling']['jobs'][job_id]:
                config_data['scheduling']['jobs'][job_id]['parameters'] = {}
            config_data['scheduling']['jobs'][job_id]['parameters']['max_posts'] = max_posts

        # Write back to config.yml
        if YAML:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f)
        else:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml_fallback.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        logger.info(f"Schedule updated for {job_id} by admin {current_user.username}: {schedule}")

        # Reload config cache to pick up changes
        from config.config_loader import reload_config
        reload_config()

        # Reload scheduler
        success = scheduler_manager.reload_jobs()

        if success:
            return jsonify({
                'success': True,
                'message': f'Schedule updated for {job_id}'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Schedule updated but failed to reload scheduler'
            }), 500

    except Exception as e:
        logger.error(f"Failed to update schedule for {job_id}: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/api/scheduler/reload', methods=['POST'])
@login_required
@admin_required
def reload_scheduler():
    """Reload scheduler configuration."""
    from scheduler.manager import scheduler_manager

    logger.info(f"Scheduler reload requested by {current_user.username}")

    # Check if scheduler is initialized
    if not scheduler_manager._initialized:
        logger.warning("Scheduler not initialized - attempting to initialize")
        try:
            from app import app
            scheduler_manager.init_app(app)
        except Exception as e:
            logger.error(f"Failed to initialize scheduler: {e}")
            return jsonify({
                'success': False,
                'error': 'Scheduler not initialized. Please check configuration.'
            }), 400

    success = scheduler_manager.reload_jobs()

    if success:
        return jsonify({
            'success': True,
            'message': 'Scheduler reloaded successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to reload scheduler'
        }), 400


@bp.route('/api/scheduler/job-config/<job_id>')
@login_required
@admin_required
def get_job_config(job_id):
    """Get job configuration for editing."""
    from config.config_loader import get_config

    config = get_config()
    jobs_config = config.get('scheduling.jobs', {})
    job_config = jobs_config.get(job_id)

    if not job_config:
        return jsonify({
            'success': False,
            'error': f'Job {job_id} not found'
        }), 404

    return jsonify({
        'success': True,
        'job_id': job_id,
        'config': job_config
    })


@bp.route('/api/scheduler/stats')
@login_required
@admin_required
def get_stats():
    """Get execution statistics."""
    stats = job_history.get_execution_stats()
    return jsonify({
        'success': True,
        'stats': stats
    })


@bp.route('/api/scheduler/clear-history', methods=['POST'])
@login_required
@admin_required
def clear_history():
    """Clear all execution history."""
    logger.info(f"Clear execution history requested by admin {current_user.username}")

    success = job_history.clear_execution_history()

    if success:
        return jsonify({
            'success': True,
            'message': 'Execution history cleared successfully'
        })
    else:
        return jsonify({
            'success': False,
            'error': 'Failed to clear execution history'
        }), 500


@bp.route('/api/scheduler/save-job', methods=['POST'])
@login_required
@admin_required
def save_job():
    """Save a new job to config.yml (admin required)."""
    try:
        from ruamel.yaml import YAML
        from ruamel.yaml.scalarstring import DoubleQuotedScalarString
        YAML_AVAILABLE = True
    except ImportError:
        import yaml as yaml_fallback
        YAML = None
        DoubleQuotedScalarString = None
        YAML_AVAILABLE = False
    import os
    from scheduler.manager import scheduler_manager
    from config.config_loader import reload_config

    data = request.get_json() or {}

    # Validate input
    job_name = data.get('name', '').strip()
    job_type = data.get('type', '').strip()
    frequency = data.get('schedule', {}).get('frequency', '').strip()
    time_str = data.get('schedule', {}).get('time', '').strip()
    enabled = data.get('enabled', True)

    if not job_name:
        return jsonify({
            'success': False,
            'error': 'Job name is required'
        }), 400

    if not job_type or job_type not in ['pakwheels', 'reddit', 'wati', 'lucid']:
        return jsonify({
            'success': False,
            'error': 'Invalid job type. Must be pakwheels, reddit, wati, or lucid'
        }), 400

    if not frequency or frequency not in ['daily', 'weekly', 'monthly', 'interval']:
        return jsonify({
            'success': False,
            'error': 'Invalid frequency. Must be daily, weekly, monthly, or interval'
        }), 400

    if not time_str and frequency != 'interval':
        return jsonify({
            'success': False,
            'error': 'Time is required (HH:MM format)'
        }), 400

    # Build schedule object
    schedule = {
        'frequency': frequency,
    }

    if frequency != 'interval':
        schedule['time'] = str(time_str)

    if frequency == 'weekly':
        day_of_week = data.get('schedule', {}).get('day_of_week')
        if day_of_week is not None:
            schedule['day_of_week'] = int(day_of_week)

    elif frequency == 'monthly':
        day_of_month = data.get('schedule', {}).get('day_of_month')
        if day_of_month is not None:
            try:
                day_of_month = int(day_of_month)
                if not (1 <= day_of_month <= 31):
                    raise ValueError()
                schedule['day_of_month'] = day_of_month
            except:
                return jsonify({
                    'success': False,
                    'error': 'day_of_month must be between 1 and 31'
                }), 400

    elif frequency == 'interval':
        minutes = data.get('schedule', {}).get('minutes')
        if minutes is not None:
            try:
                minutes = int(minutes)
                if minutes < 5:
                    raise ValueError()
                schedule['minutes'] = minutes
            except:
                return jsonify({
                    'success': False,
                    'error': 'minutes must be at least 5'
                }), 400

    # Get company_id from current user or default
    company_id = 'haval'
    if current_user and hasattr(current_user, 'company_id'):
        company_id = current_user.company_id or 'haval'

    # Build job config
    job_config = {
        'enabled': enabled,
        'company_id': company_id,
        'type': job_type,
        'schedule': schedule,
        'parameters': data.get('parameters', {})
    }

    try:
        # Read config.yml
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

        # Ensure scheduling section exists
        if 'scheduling' not in config_data:
            config_data['scheduling'] = {}
        if 'jobs' not in config_data['scheduling']:
            config_data['scheduling']['jobs'] = {}

        # Add the new job
        config_data['scheduling']['jobs'][job_name] = job_config

        # Write back to config.yml
        if YAML_AVAILABLE:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config_data, f)
        else:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml_fallback.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

        logger.info(f"New job '{job_name}' created by user {current_user.username if current_user else 'anonymous'}: type={job_type}, frequency={frequency}")

        # Reload config cache
        reload_config()

        # Try to reload scheduler if available
        try:
            scheduler_manager.reload_jobs()
        except:
            pass  # Scheduler might not be running

        return jsonify({
            'success': True,
            'message': f'Job {job_name} saved successfully',
            'job_name': job_name,
            'job_type': job_type
        })

    except Exception as e:
        logger.error(f"Failed to save job '{job_name}': {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'Failed to save job: {str(e)}'
        }), 500


# Helper functions for templates

@bp.app_template_filter('format_datetime')
def format_datetime_filter(value):
    """Format datetime for display."""
    if not value:
        return '-'
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except:
            return value
    return value.strftime('%Y-%m-%d %H:%M:%S')


@bp.app_template_filter('format_duration')
def format_duration_filter(seconds):
    """Format duration for display."""
    return job_history.format_duration(seconds)


@bp.app_template_filter('status_badge')
def status_badge_filter(status):
    """Return CSS class for status badge."""
    return {
        'success': 'badge-success',
        'failed': 'badge-danger',
        'skipped': 'badge-warning',
        'running': 'badge-info'
    }.get(status, 'badge-secondary')
