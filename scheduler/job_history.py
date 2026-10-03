"""
Job History Database Tracking

Provides functions for tracking job execution history in the database.
Uses the main application database for persistence.
"""

import sqlite3
from datetime import datetime
from utils.logger import LoggerManager
import json
import os

logger = LoggerManager.get_logger('scheduler')

# Use the same database as the main app
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'marketing.db')


def ensure_table_exists():
    """Ensure the job_executions table exists."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS job_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                company_id TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                duration_seconds REAL,
                records_processed INTEGER DEFAULT 0,
                error_message TEXT,
                details TEXT
            )
        """)

        # Create indexes if they don't exist
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_executions_job_id ON job_executions(job_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_executions_started_at ON job_executions(started_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_job_executions_status ON job_executions(status)")

        conn.commit()
        conn.close()
        logger.debug("Job executions table ensured")

    except Exception as e:
        logger.error(f"Failed to ensure job_executions table: {e}", exc_info=True)


def start_execution(job_id, company_id):
    """
    Record the start of a job execution.

    Args:
        job_id (str): Job identifier
        company_id (str): Company identifier

    Returns:
        int: Execution ID or None on failure
    """
    ensure_table_exists()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        started_at = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO job_executions (job_id, company_id, status, started_at)
            VALUES (?, ?, 'running', ?)
        """, (job_id, company_id, started_at))

        execution_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.info(f"Started execution tracking: {job_id} (ID: {execution_id})")
        return execution_id

    except Exception as e:
        logger.error(f"Failed to record job start: {e}", exc_info=True)
        return None


def mark_success(execution_id, message, records=0):
    """
    Mark job execution as successful.

    Args:
        execution_id (int): Execution ID
        message (str): Success message
        records (int): Number of records processed
    """
    if not execution_id:
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        completed_at = datetime.now().isoformat()

        # Calculate duration
        cursor.execute("SELECT started_at FROM job_executions WHERE id = ?", (execution_id,))
        row = cursor.fetchone()
        duration = 0
        if row:
            try:
                started_at = datetime.fromisoformat(row[0])
                duration = (datetime.now() - started_at).total_seconds()
            except:
                pass

        cursor.execute("""
            UPDATE job_executions
            SET status = 'success',
                completed_at = ?,
                duration_seconds = ?,
                records_processed = ?,
                details = ?
            WHERE id = ?
        """, (completed_at, duration, records, message, execution_id))

        conn.commit()
        conn.close()

        logger.info(f"Execution {execution_id} marked as successful: {records} records")

    except Exception as e:
        logger.error(f"Failed to mark job success: {e}", exc_info=True)


def mark_failed(execution_id, error_message):
    """
    Mark job execution as failed.

    Args:
        execution_id (int): Execution ID
        error_message (str): Error message
    """
    if not execution_id:
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        completed_at = datetime.now().isoformat()

        # Calculate duration
        cursor.execute("SELECT started_at FROM job_executions WHERE id = ?", (execution_id,))
        row = cursor.fetchone()
        duration = 0
        if row:
            try:
                started_at = datetime.fromisoformat(row[0])
                duration = (datetime.now() - started_at).total_seconds()
            except:
                pass

        cursor.execute("""
            UPDATE job_executions
            SET status = 'failed',
                completed_at = ?,
                duration_seconds = ?,
                error_message = ?
            WHERE id = ?
        """, (completed_at, duration, error_message, execution_id))

        conn.commit()
        conn.close()

        logger.error(f"Execution {execution_id} marked as failed: {error_message}")

    except Exception as e:
        logger.error(f"Failed to mark job failure: {e}", exc_info=True)


def mark_skipped(execution_id, reason):
    """
    Mark job execution as skipped.

    Args:
        execution_id (int): Execution ID
        reason (str): Skip reason
    """
    if not execution_id:
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        completed_at = datetime.now().isoformat()

        # Calculate duration
        cursor.execute("SELECT started_at FROM job_executions WHERE id = ?", (execution_id,))
        row = cursor.fetchone()
        duration = 0
        if row:
            try:
                started_at = datetime.fromisoformat(row[0])
                duration = (datetime.now() - started_at).total_seconds()
            except:
                pass

        cursor.execute("""
            UPDATE job_executions
            SET status = 'skipped',
                completed_at = ?,
                duration_seconds = ?,
                details = ?
            WHERE id = ?
        """, (completed_at, duration, reason, execution_id))

        conn.commit()
        conn.close()

        logger.info(f"Execution {execution_id} marked as skipped: {reason}")

    except Exception as e:
        logger.error(f"Failed to mark job skip: {e}", exc_info=True)


def get_recent_executions(job_id=None, limit=50):
    """
    Get recent job executions.

    Args:
        job_id (str): Optional job ID filter
        limit (int): Maximum number of executions to return

    Returns:
        list: List of execution dictionaries
    """
    ensure_table_exists()

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if job_id:
            cursor.execute("""
                SELECT * FROM job_executions
                WHERE job_id = ?
                ORDER BY started_at DESC
                LIMIT ?
            """, (job_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM job_executions
                ORDER BY started_at DESC
                LIMIT ?
            """, (limit,))

        rows = cursor.fetchall()
        conn.close()

        executions = []
        for row in rows:
            executions.append({
                'id': row['id'],
                'job_id': row['job_id'],
                'company_id': row['company_id'],
                'status': row['status'],
                'started_at': row['started_at'],
                'completed_at': row['completed_at'],
                'duration_seconds': row['duration_seconds'],
                'records_processed': row['records_processed'],
                'error_message': row['error_message'],
                'details': row['details']
            })

        return executions

    except Exception as e:
        logger.error(f"Failed to get recent executions: {e}", exc_info=True)
        return []


def get_last_execution(job_id):
    """
    Get the most recent execution for a job.

    Args:
        job_id (str): Job identifier

    Returns:
        dict: Execution dictionary or None
    """
    executions = get_recent_executions(job_id=job_id, limit=1)
    return executions[0] if executions else None


def get_execution_stats():
    """
    Get overall execution statistics.

    Returns:
        dict: Statistics dictionary
    """
    ensure_table_exists()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Total executions
        cursor.execute("SELECT COUNT(*) FROM job_executions")
        total = cursor.fetchone()[0]

        # By status
        cursor.execute("""
            SELECT status, COUNT(*)
            FROM job_executions
            GROUP BY status
        """)
        by_status = dict(cursor.fetchall())

        # Last 24 hours
        cursor.execute("""
            SELECT COUNT(*) FROM job_executions
            WHERE started_at > datetime('now', '-1 day')
        """)
        last_24h = cursor.fetchone()[0]

        conn.close()

        return {
            'total': total,
            'success': by_status.get('success', 0),
            'failed': by_status.get('failed', 0),
            'skipped': by_status.get('skipped', 0),
            'running': by_status.get('running', 0),
            'last_24h': last_24h
        }

    except Exception as e:
        logger.error(f"Failed to get execution stats: {e}", exc_info=True)
        return {
            'total': 0,
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'running': 0,
            'last_24h': 0
        }


def clear_execution_history():
    """
    Clear all execution history from the database.

    Returns:
        bool: True if successful, False otherwise
    """
    ensure_table_exists()

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM job_executions")
        deleted_count = cursor.rowcount

        conn.commit()
        conn.close()

        logger.info(f"Cleared {deleted_count} execution history records")
        return True

    except Exception as e:
        logger.error(f"Failed to clear execution history: {e}", exc_info=True)
        return False


def format_duration(seconds):
    """
    Format duration in seconds to human-readable string.

    Args:
        seconds (float): Duration in seconds

    Returns:
        str: Formatted duration (e.g., "1m 30s")
    """
    if seconds is None:
        return "-"

    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = int(seconds % 60)
        return f"{minutes}m {secs}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
