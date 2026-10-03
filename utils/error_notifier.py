"""
Error Notification Service
Sends critical errors via email without disrupting application functionality
Uses async/background processing to avoid blocking main application flow
"""

import smtplib
import threading
import queue
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from utils.logger import server_logger, error_logger
import os
import traceback

# SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = 587
SMTP_USERNAME = "awaissaeedsaib@gmail.com"
SMTP_PASSWORD = "okwcrnxfirpfxnul"
FROM_EMAIL = "awaissaeedsaib@gmail.com"
FROM_NAME = "Enterprise AI - Error Alerts"

# Alert recipients (can be configured)
ALERT_RECIPIENTS = [
    "awaissaeedsaib@gmail.com",
    # "obaid.nasir@visionrdai.com"
]

# Error severity levels
ERROR_SEVERITY = {
    "CRITICAL": 1,      # System down, data loss risk
    "HIGH": 2,          # Major functionality broken
    "MEDIUM": 3,        # Feature degradation
    "LOW": 4            # Minor issues
}


class ErrorNotificationQueue:
    """Thread-safe queue for error notifications"""
    
    def __init__(self, max_queue_size=1000):
        self.queue = queue.Queue(maxsize=max_queue_size)
        self.running = False
        self.worker_thread = None
    
    def start(self):
        """Start the background worker thread"""
        if not self.running:
            self.running = True
            self.worker_thread = threading.Thread(
                target=self._worker,
                daemon=True,
                name="ErrorNotificationWorker"
            )
            self.worker_thread.start()
            server_logger.info("Error notification worker started")
    
    def stop(self):
        """Stop the background worker thread"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        server_logger.info("Error notification worker stopped")
    
    def add_error(self, error_data):
        """Add error to notification queue (non-blocking)"""
        try:
            self.queue.put_nowait(error_data)
        except queue.Full:
            error_logger.warning("Error notification queue is full, dropping error")
    
    def _worker(self):
        """Background worker that processes error notifications"""
        while self.running:
            try:
                # Get error from queue with timeout to allow graceful shutdown
                error_data = self.queue.get(timeout=1)
                
                # Check if we should send this error
                if self._should_send_notification(error_data):
                    self._send_error_email(error_data)
                
                self.queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                error_logger.error(f"Error in notification worker: {str(e)}")
                error_logger.error(traceback.format_exc())
    
    def _should_send_notification(self, error_data):
        """Determine if notification should be sent"""
        # Send every error notification (no deduplication)
        return True
    
    def _send_error_email(self, error_data):
        """Send error notification email"""
        try:
            severity = error_data.get("severity", "MEDIUM")
            error_type = error_data.get("error_type", "Unknown")
            function = error_data.get("function", "Unknown")
            message = error_data.get("message", "No message provided")
            timestamp = error_data.get("timestamp", datetime.now().isoformat())
            user = error_data.get("user", "Anonymous")
            endpoint = error_data.get("endpoint", "Unknown")
            operation = error_data.get("operation", "")
            traceback_str = error_data.get("traceback", "")
            
            # Create email
            msg = MIMEMultipart('alternative')
            msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
            msg['To'] = ", ".join(ALERT_RECIPIENTS)
            msg['Subject'] = f"[{severity}] Error Alert: {error_type} in {function}"
            msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
            msg['X-Priority'] = str(ERROR_SEVERITY.get(severity, 3))
            
            # Plain text version
            text_content = f"""
ERROR ALERT - {severity}
{'='*60}

Error Type: {error_type}
Function: {function}
Operation: {operation if operation else 'N/A'}
Timestamp: {timestamp}
User: {user}
Endpoint: {endpoint}

Message:
{message}

Traceback:
{traceback_str}

{'='*60}
This is an automated alert from Enterprise AI Error Monitoring System.
"""
            
            # HTML version with color coding
            severity_color = {
                "CRITICAL": "#dc2626",
                "HIGH": "#ea580c",
                "MEDIUM": "#f59e0b",
                "LOW": "#3b82f6"
            }.get(severity, "#6b7280")
            
            html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error Alert</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f3f4f6;">
    <table role="presentation" style="width: 100%; border-collapse: collapse; padding: 20px;">
        <tr>
            <td align="center">
                <table role="presentation" style="max-width: 700px; width: 100%; background: white; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); overflow: hidden;">
                    
                    <!-- Header with severity color -->
                    <tr>
                        <td style="background: {severity_color}; padding: 30px 40px; text-align: center;">
                            <h1 style="margin: 0; color: white; font-size: 28px; font-weight: 700;">
                                ⚠️ {severity} Error Alert
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Content -->
                    <tr>
                        <td style="padding: 40px;">
                            
                            <!-- Error Details -->
                            <table role="presentation" style="width: 100%; margin-bottom: 30px;">
                                <tr>
                                    <td style="padding: 15px; background: #f9fafb; border-left: 4px solid {severity_color}; border-radius: 4px;">
                                        <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 12px; font-weight: 600; text-transform: uppercase;">Error Type</p>
                                        <p style="margin: 0; color: #1f2937; font-size: 16px; font-weight: 600;">{error_type}</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td style="padding: 15px; background: #f9fafb; border-left: 4px solid {severity_color}; border-radius: 4px; margin-top: 10px;">
                                        <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 12px; font-weight: 600; text-transform: uppercase;">Function</p>
                                        <p style="margin: 0; color: #1f2937; font-size: 16px; font-weight: 600;">{function}</p>
                                    </td>
                                </tr>
                                {f'''<tr>
                                    <td style="padding: 15px; background: #f9fafb; border-left: 4px solid {severity_color}; border-radius: 4px; margin-top: 10px;">
                                        <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 12px; font-weight: 600; text-transform: uppercase;">Operation</p>
                                        <p style="margin: 0; color: #1f2937; font-size: 16px; font-weight: 600;">{operation if operation else "N/A"}</p>
                                    </td>
                                </tr>''' if operation else ''}
                            </table>
                            
                            <!-- Metadata Grid -->
                            <table role="presentation" style="width: 100%; margin-bottom: 30px; border-collapse: collapse;">
                                <tr>
                                    <td style="padding: 12px; background: #f3f4f6; border: 1px solid #e5e7eb; width: 50%;">
                                        <p style="margin: 0 0 5px 0; color: #6b7280; font-size: 11px; font-weight: 600;">TIMESTAMP</p>
                                        <p style="margin: 0; color: #1f2937; font-size: 13px;">{timestamp}</p>
                                    </td>
                                    <td style="padding: 12px; background: #f3f4f6; border: 1px solid #e5e7eb; width: 50%;">
                                        <p style="margin: 0 0 5px 0; color: #6b7280; font-size: 11px; font-weight: 600;">USER</p>
                                        <p style="margin: 0; color: #1f2937; font-size: 13px;">{user}</p>
                                    </td>
                                </tr>
                                <tr>
                                    <td colspan="2" style="padding: 12px; background: #f3f4f6; border: 1px solid #e5e7eb;">
                                        <p style="margin: 0 0 5px 0; color: #6b7280; font-size: 11px; font-weight: 600;">ENDPOINT</p>
                                        <p style="margin: 0; color: #1f2937; font-size: 13px;">{endpoint}</p>
                                    </td>
                                </tr>
                            </table>
                            
                            <!-- Error Message -->
                            <div style="margin-bottom: 30px;">
                                <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 12px; font-weight: 600; text-transform: uppercase;">Error Message</p>
                                <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 6px; padding: 15px; color: #991b1b; font-size: 13px; line-height: 1.6; font-family: 'Courier New', monospace; word-break: break-word;">
                                    {message}
                                </div>
                            </div>
                            
                            <!-- Traceback (if available) -->
                            {f'''<div style="margin-bottom: 30px;">
                                <p style="margin: 0 0 10px 0; color: #6b7280; font-size: 12px; font-weight: 600; text-transform: uppercase;">Stack Trace</p>
                                <div style="background: #1f2937; border-radius: 6px; padding: 15px; color: #d1d5db; font-size: 12px; line-height: 1.5; font-family: 'Courier New', monospace; overflow-x: auto; white-space: pre-wrap; word-break: break-word;">
                                    {traceback_str[:2000]}
                                </div>
                            </div>''' if traceback_str else ''}
                            
                            <!-- Action Items -->
                            <div style="background: #eff6ff; border-left: 4px solid #3b82f6; padding: 15px; border-radius: 4px; margin-bottom: 30px;">
                                <p style="margin: 0 0 10px 0; color: #1e40af; font-size: 12px; font-weight: 600; text-transform: uppercase;">⚡ Recommended Actions</p>
                                <ul style="margin: 0; padding-left: 20px; color: #1e40af; font-size: 13px;">
                                    <li>Check application logs for more details</li>
                                    <li>Verify system resources (CPU, memory, disk)</li>
                                    <li>Review recent code changes</li>
                                    <li>Check external service connectivity</li>
                                </ul>
                            </div>
                            
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background: #f9fafb; padding: 20px 40px; text-align: center; border-top: 1px solid #e5e7eb;">
                            <p style="margin: 0; color: #6b7280; font-size: 12px;">
                                This is an automated alert from Enterprise AI Error Monitoring System
                            </p>
                            <p style="margin: 5px 0 0 0; color: #9ca3af; font-size: 11px;">
                                © 2025 Enterprise AI. All rights reserved.
                            </p>
                        </td>
                    </tr>
                    
                </table>
            </td>
        </tr>
    </table>
</body>
</html>"""
            
            # Attach both versions
            text_part = MIMEText(text_content, 'plain', 'utf-8')
            html_part = MIMEText(html_content, 'html', 'utf-8')
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.send_message(msg)
            
            server_logger.info(f"Error notification sent for {error_type} in {function}")
            
        except Exception as e:
            error_logger.error(f"Failed to send error notification: {str(e)}")
            error_logger.error(traceback.format_exc())


# Global notification queue instance
_notification_queue = None


def get_notification_queue():
    """Get or create the global notification queue"""
    global _notification_queue
    if _notification_queue is None:
        _notification_queue = ErrorNotificationQueue()
        _notification_queue.start()
    return _notification_queue


def notify_error(error_type, function, message, severity="MEDIUM", 
                 user="Anonymous", endpoint="Unknown", traceback_str="", operation=""):
    """
    Queue an error for notification (non-blocking)
    
    Args:
        error_type: Type of error (e.g., "DatabaseError", "APIError")
        function: Function where error occurred
        message: Error message
        severity: One of CRITICAL, HIGH, MEDIUM, LOW
        user: User ID or identifier
        endpoint: API endpoint or route
        traceback_str: Full traceback string
        operation: Detailed operation description (e.g., "Scraping PakWheels", "Embedding vectors")
    """
    try:
        queue = get_notification_queue()
        error_data = {
            "error_type": error_type,
            "function": function,
            "message": message,
            "severity": severity,
            "user": user,
            "endpoint": endpoint,
            "traceback": traceback_str,
            "operation": operation,
            "timestamp": datetime.now().isoformat()
        }
        queue.add_error(error_data)
    except Exception as e:
        error_logger.error(f"Failed to queue error notification: {str(e)}")


def notify_startup_error(error_message):
    """
    Capture startup/configuration errors
    
    Args:
        error_message: Error message from startup logs
    """
    try:
        # Determine severity based on error keywords
        severity = "MEDIUM"
        for keyword, sev in STARTUP_ERRORS.items():
            if keyword.lower() in error_message.lower():
                severity = sev
                break
        
        # Determine error type
        if "SQL Server" in error_message or "MSSQL" in error_message:
            error_type = "SQLServerConnectionError"
        elif "Redis" in error_message:
            error_type = "RedisConnectionError"
        elif "ChromaDB" in error_message or "Vector" in error_message:
            error_type = "VectorStoreError"
        elif "OPENAI_API_KEY" in error_message:
            error_type = "ConfigurationWarning"
        else:
            error_type = "StartupError"
        
        notify_error(
            error_type=error_type,
            function="app_startup",
            message=error_message[:500],
            severity=severity,
            user="system",
            endpoint="/startup",
            traceback_str=error_message
        )
    except Exception as e:
        error_logger.error(f"Failed to notify startup error: {str(e)}")


def shutdown_notification_system():
    """Gracefully shutdown the notification system"""
    global _notification_queue
    if _notification_queue:
        _notification_queue.stop()
        _notification_queue = None
