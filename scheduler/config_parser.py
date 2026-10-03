"""
Configuration Parser

Converts human-readable YAML schedule configuration into APScheduler triggers.
"""

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from utils.logger import LoggerManager

logger = LoggerManager.get_logger('scheduler')


def parse_schedule(schedule_config, timezone='Asia/Karachi'):
    """
    Convert YAML schedule configuration to APScheduler trigger.

    Supported schedule types:
    - daily: {"frequency": "daily", "time": "03:00"}
    - weekly: {"frequency": "weekly", "day_of_week": "monday", "time": "03:00"}
    - monthly: {"frequency": "monthly", "day_of_month": 1, "time": "03:00"}
    - interval: {"frequency": "interval", "minutes": 5} (for testing only)

    Args:
        schedule_config (dict): Schedule configuration from YAML
        timezone (str): Timezone for the trigger (default: Asia/Karachi)

    Returns:
        APScheduler trigger (CronTrigger or IntervalTrigger)
    """
    frequency = schedule_config.get('frequency', 'daily').lower()

    # Parse time (HH:MM format)
    time_str = schedule_config.get('time', '03:00')
    try:
        hour, minute = map(int, time_str.split(':'))
    except (ValueError, AttributeError):
        logger.warning(f"Invalid time format '{time_str}', defaulting to 03:00")
        hour, minute = 3, 0

    # Validate hour and minute
    if not (0 <= hour <= 23) or not (0 <= minute <= 59):
        logger.warning(f"Invalid time {hour}:{minute}, defaulting to 03:00")
        hour, minute = 3, 0

    # Parse start date (optional)
    start_date = schedule_config.get('start_date')
    if start_date:
        try:
            start_date = datetime.fromisoformat(start_date)
        except (ValueError, TypeError):
            logger.warning(f"Invalid start_date '{start_date}', ignoring")
            start_date = None

    # Create trigger based on frequency
    if frequency == 'daily':
        return CronTrigger(
            hour=hour,
            minute=minute,
            start_date=start_date,
            timezone=timezone
        )

    elif frequency == 'weekly':
        day_map = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2,
            'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
        }
        day_str = schedule_config.get('day_of_week', 'monday').lower()
        day_of_week = day_map.get(day_str, 0)

        return CronTrigger(
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            start_date=start_date,
            timezone=timezone
        )

    elif frequency == 'monthly':
        day_of_month = schedule_config.get('day_of_month', 1)
        # Validate day (1-31)
        if not (1 <= day_of_month <= 31):
            logger.warning(f"Invalid day_of_month {day_of_month}, defaulting to 1")
            day_of_month = 1

        return CronTrigger(
            day=day_of_month,
            hour=hour,
            minute=minute,
            start_date=start_date,
            timezone=timezone
        )

    elif frequency == 'interval':
        # For testing only - run every X minutes/hours
        minutes = schedule_config.get('minutes')
        hours = schedule_config.get('hours')

        if minutes:
            return IntervalTrigger(minutes=minutes, start_date=start_date)
        elif hours:
            return IntervalTrigger(hours=hours, start_date=start_date)
        else:
            logger.warning("Interval schedule missing 'minutes' or 'hours', defaulting to 60 minutes")
            return IntervalTrigger(minutes=60, start_date=start_date)

    else:
        logger.error(f"Unknown schedule frequency '{frequency}', defaulting to daily")
        return CronTrigger(hour=hour, minute=minute, start_date=start_date, timezone=timezone)


def format_schedule_human(schedule_config):
    """
    Convert schedule config to human-readable string for display.

    Args:
        schedule_config (dict): Schedule configuration

    Returns:
        str: Human-readable schedule (e.g., "Daily at 03:00 AM")
    """
    frequency = schedule_config.get('frequency', 'daily').lower()
    time_str = schedule_config.get('time', '03:00')

    # Convert 24h to 12h format
    try:
        hour, minute = map(int, time_str.split(':'))
        period = 'AM' if hour < 12 else 'PM'
        display_hour = hour if hour <= 12 else hour - 12
        if display_hour == 0:
            display_hour = 12
        formatted_time = f"{display_hour}:{minute:02d} {period}"
    except:
        formatted_time = time_str

    if frequency == 'daily':
        return f"Daily at {formatted_time}"

    elif frequency == 'weekly':
        day = schedule_config.get('day_of_week', 'Monday').capitalize()
        return f"Weekly on {day} at {formatted_time}"

    elif frequency == 'monthly':
        day = schedule_config.get('day_of_month', 1)
        suffix = 'th' if 11 <= day <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(day % 10, 'th')
        return f"Monthly on {day}{suffix} at {formatted_time}"

    elif frequency == 'interval':
        if 'minutes' in schedule_config:
            return f"Every {schedule_config['minutes']} minutes"
        elif 'hours' in schedule_config:
            return f"Every {schedule_config['hours']} hours"

    return "Unknown schedule"


def get_next_run_display(next_run_time):
    """
    Format next run time for display.

    Args:
        next_run_time: datetime object or None

    Returns:
        str: Human-readable next run time
    """
    if not next_run_time:
        return "Not scheduled"

    now = datetime.now(next_run_time.tzinfo) if next_run_time.tzinfo else datetime.now()
    delta = next_run_time - now

    if delta.total_seconds() < 0:
        return "Running now"
    elif delta.total_seconds() < 60:
        return "Less than a minute"
    elif delta.total_seconds() < 3600:
        minutes = int(delta.total_seconds() / 60)
        return f"In {minutes} minute{'s' if minutes > 1 else ''}"
    elif delta.total_seconds() < 86400:
        hours = int(delta.total_seconds() / 3600)
        return f"In {hours} hour{'s' if hours > 1 else ''}"
    else:
        days = int(delta.total_seconds() / 86400)
        return f"In {days} day{'s' if days > 1 else ''}"
