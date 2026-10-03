"""
Automated Scraping Scheduler

Provides scheduled execution of scraping jobs (PakWheels, Reddit, WATI)
using APScheduler integrated with Flask.
"""

from scheduler.manager import scheduler_manager

__all__ = ['scheduler_manager']
