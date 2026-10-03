"""
Error Notification Configuration
Centralized configuration for error email alerts
"""

import os

# SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = 587
SMTP_USERNAME = "awaissaeedsaib@gmail.com"
SMTP_PASSWORD = "okwcrnxfirpfxnul"
FROM_EMAIL = "awaissaeedsaib@gmail.com"
FROM_NAME = "Enterprise AI - Error Alerts"

# Alert Recipients - Add admin emails here
ALERT_RECIPIENTS = [
    "awaissaeedsaib@gmail.com",
    # "obaid.nasir@visionrdai.com"
]

# Error Severity Levels
ERROR_SEVERITY = {
    "CRITICAL": 1,      # System down, data loss risk
    "HIGH": 2,          # Major functionality broken
    "MEDIUM": 3,        # Feature degradation
    "LOW": 4            # Minor issues
}

# Deduplication Settings
DEDUP_WINDOW = 300  # 5 minutes - don't send same error twice within this window
MAX_SAME_ERRORS = 5  # Send alert after 5 occurrences of same error

# Queue Settings
MAX_QUEUE_SIZE = 1000  # Maximum errors to queue before dropping

# Error Classification
ERROR_SEVERITY_MAP = {
    "ConnectionError": "CRITICAL",
    "DatabaseError": "CRITICAL",
    "TimeoutError": "HIGH",
    "PermissionError": "HIGH",
    "ValueError": "MEDIUM",
    "FileNotFoundError": "MEDIUM",
    "KeyError": "MEDIUM",
    "AttributeError": "MEDIUM",
    "TypeError": "MEDIUM",
    "RuntimeError": "HIGH",
    "ImportError": "HIGH",
    "OSError": "HIGH"
}

# Errors to ignore (won't send notifications)
IGNORED_ERRORS = [
    "404",
    "Not Found",
    "Unauthorized",
    "Forbidden"
]

# Enable/Disable error notifications
ENABLED = True

# Batch settings (future enhancement)
BATCH_NOTIFICATIONS = False  # Set to True to batch errors before sending
BATCH_INTERVAL = 300  # Seconds between batch sends
