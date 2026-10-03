"""
Email Service for OTP Verification
Handles sending OTP emails for signup and password reset

IMPORTANT: To avoid spam folder, ensure the following:
1. SPF Record: Add TXT record to your domain DNS:
   v=spf1 include:_spf.google.com ~all

2. DKIM: Enable DKIM signing in Gmail settings:
   - Go to Gmail Admin Console
   - Apps > Google Workspace > Gmail > Authenticate email
   - Generate new DKIM key

3. DMARC Record: Add TXT record to your domain DNS:
   _dmarc.yourdomain.com TXT "v=DMARC1; p=quarantine; rua=mailto:dmarc@yourdomain.com"

4. Use a custom domain email instead of @gmail.com for FROM_EMAIL
   (e.g., noreply@yourdomain.com)

5. Warm up your email: Start by sending small volumes and gradually increase

6. Ask users to add your email to their contacts

7. Monitor your sender reputation at:
   - Google Postmaster Tools
   - mail-tester.com
"""

import smtplib
import random
import string
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime, timedelta
from utils.logger import server_logger, log_error
import os

# SMTP Configuration (loaded from environment variables)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = 587
SMTP_USERNAME = "awaissaeedsaib@gmail.com"
SMTP_PASSWORD = "okwcrnxfirpfxnul"
FROM_EMAIL = "awaissaeedsaib@gmail.com"
FROM_NAME = "Enterprise AI"

def generate_otp(length=6):
    """Generate a random OTP"""
    return ''.join(random.choices(string.digits, k=length))

def send_otp_email(to_email, otp, purpose="signup"):
    """
    Send OTP email to user
    
    Args:
        to_email: Recipient email address
        otp: The OTP code to send
        purpose: Either 'signup' or 'reset' for different email templates
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        # Create message with proper headers to avoid spam
        msg = MIMEMultipart('alternative')  # Changed from 'related' to 'alternative'
        msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg['To'] = to_email
        msg['Reply-To'] = FROM_EMAIL
        
        # Remove high priority flags (can trigger spam filters)
        # msg['X-Priority'] = '1'
        # msg['X-MSMail-Priority'] = 'High'
        # msg['Importance'] = 'High'
        
        # Add proper headers to improve deliverability
        msg['Message-ID'] = f"<{datetime.now().timestamp()}.{to_email}@Enterpriseai.com>"
        msg['Date'] = datetime.now().strftime('%a, %d %b %Y %H:%M:%S %z')
        msg['List-Unsubscribe'] = f'<mailto:{FROM_EMAIL}?subject=unsubscribe>'
        msg['X-Mailer'] = 'Enterprise AI'
        
        # Add authentication headers (helps with spam score)
        msg['MIME-Version'] = '1.0'
        
        if purpose == "signup":
            msg['Subject'] = "Verify Your Account - Enterprise AI"
            
            # Plain text version (important for spam filters)
            text_content = f"""
Verify Your Account - Enterprise AI

Welcome to Enterprise AI!

Thank you for joining Enterprise AI! To complete your registration, please verify your email address.

Your Verification Code: {otp}

This code expires in 10 minutes.

Enter this code on the verification page to activate your account.

If you didn't create an account, please ignore this email.

Need help? Contact us at support@Enterpriseai.com

© 2025 Enterprise AI. All rights reserved.
"""
            
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Verify Your Account</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" style="width: 100%; border-collapse: collapse; background: linear-gradient(135deg, #ff0000 0%, #ff6b6b 50%, #ffa5a5 100%); min-height: 600px; padding: 60px 20px;">
        <tr>
            <td align="center">
                <!-- Glassmorphism Card -->
                <table role="presentation" style="max-width: 600px; width: 100%; background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-radius: 30px; border: 1px solid rgba(255, 255, 255, 0.3); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden;">
                    
                    <!-- Logo Badge -->
                    <tr>
                        <td style="padding: 50px 40px 30px 40px; text-align: center;">
                            <div style="display: inline-block; background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(10px); padding: 15px 50px; border-radius: 50px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);">
                                <span style="font-size: 28px; font-weight: 800; color: #2d3748; letter-spacing: 1px;">VisionRD AI</span>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Main Heading -->
                    <tr>
                        <td style="padding: 20px 40px; text-align: center;">
                            <h1 style="margin: 0 0 15px 0; color: #ffffff; font-size: 36px; font-weight: 700; text-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);">Welcome to Enterprise AI!</h1>
                            <p style="margin: 0; color: rgba(255, 255, 255, 0.95); font-size: 18px; font-weight: 400;">Verify your email to get started</p>
                        </td>
                    </tr>
                    
                    <!-- Content Card -->
                    <tr>
                        <td style="padding: 30px 40px;">
                            <div style="background: rgba(255, 255, 255, 0.25); backdrop-filter: blur(10px); border-radius: 20px; padding: 40px 35px; border: 1px solid rgba(255, 255, 255, 0.3);">
                                <p style="margin: 0 0 30px 0; color: #2d3748; font-size: 16px; line-height: 1.6; text-align: center;">Thank you for joining Enterprise AI! To complete your registration and unlock the power of AI-driven intelligence, please verify your email.</p>
                                
                                <!-- Verify Button -->
                                <table role="presentation" style="width: 100%; margin: 0;">
                                    <tr>
                                        <td align="center">
                                            <table role="presentation" style="margin: 0;">
                                                <tr>
                                                    <td style="background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%); padding: 18px 60px; border-radius: 50px; box-shadow: 0 8px 20px rgba(220, 38, 38, 0.4); text-align: center;">
                                                        <span style="font-size: 32px; font-weight: 800; color: #ffffff; letter-spacing: 8px; font-family: 'Courier New', monospace;">{otp}</span>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                                
                                <p style="margin: 25px 0 0 0; color: #4a5568; font-size: 14px; text-align: center;">
                                    <span style="display: inline-block; padding: 8px 16px; background: rgba(255, 255, 255, 0.8); border-radius: 20px;">⏱️ Code expires in 10 minutes</span>
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Security Notice -->
                    <tr>
                        <td style="padding: 0 40px 50px 40px;">
                            <p style="margin: 0; color: rgba(255, 255, 255, 0.9); font-size: 13px; text-align: center; line-height: 1.6;">
                                🔒 If you didn't create an account, please ignore this email.
                            </p>
                        </td>
                    </tr>
                    
                </table>
                
                <!-- Footer -->
                <table role="presentation" style="max-width: 600px; width: 100%; margin-top: 30px;">
                    <tr>
                        <td style="text-align: center; padding: 20px;">
                            <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.9); font-size: 13px;">Need help? Contact us at <a href="mailto:support@Enterpriseai.com" style="color: #ffffff; text-decoration: underline;">support@Enterpriseai.com</a></p>
                            <p style="margin: 0; color: rgba(255, 255, 255, 0.7); font-size: 12px;">© 2025 Enterprise AI. All rights reserved.</p>
                        </td>
                    </tr>
                </table>
                
            </td>
        </tr>
    </table>
</body>
</html>"""
        else:  # reset password
            msg['Subject'] = "Reset Your Password - Enterprise AI"
            
            # Plain text version (important for spam filters)
            text_content = f"""
Reset Your Password - Enterprise AI

Password Reset Request

We received a request to reset your password for your Enterprise AI account.

Your Reset Code: {otp}

This code expires in 10 minutes.

Enter this code on the password reset page along with your new password to regain access to your account.

If you didn't request a password reset, please ignore this email and your password will remain unchanged.

Need help? Contact us at support@Enterpriseai.com

© 2025 Enterprise AI. All rights reserved.
"""
            
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Your Password</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
    <table role="presentation" style="width: 100%; border-collapse: collapse; background: linear-gradient(135deg, #ff0000 0%, #ff6b6b 50%, #ffa5a5 100%); min-height: 600px; padding: 60px 20px;">
        <tr>
            <td align="center">
                <!-- Glassmorphism Card -->
                <table role="presentation" style="max-width: 600px; width: 100%; background: rgba(255, 255, 255, 0.15); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border-radius: 30px; border: 1px solid rgba(255, 255, 255, 0.3); box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1); overflow: hidden;">
                    
                    <!-- Logo Badge -->
                    <tr>
                        <td style="padding: 50px 40px 30px 40px; text-align: center;">
                            <div style="display: inline-block; background: rgba(255, 255, 255, 0.9); backdrop-filter: blur(10px); padding: 15px 50px; border-radius: 50px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);">
                                <span style="font-size: 28px; font-weight: 800; color: #2d3748; letter-spacing: 1px;">VisionRD AI</span>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Main Heading -->
                    <tr>
                        <td style="padding: 20px 40px; text-align: center;">
                            <h1 style="margin: 0 0 15px 0; color: #ffffff; font-size: 36px; font-weight: 700; text-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);">Password Reset Request</h1>
                            <p style="margin: 0; color: rgba(255, 255, 255, 0.95); font-size: 18px; font-weight: 400;">Secure your account with a new password</p>
                        </td>
                    </tr>
                    
                    <!-- Content Card -->
                    <tr>
                        <td style="padding: 30px 40px;">
                            <div style="background: rgba(255, 255, 255, 0.25); backdrop-filter: blur(10px); border-radius: 20px; padding: 40px 35px; border: 1px solid rgba(255, 255, 255, 0.3);">
                                <p style="margin: 0 0 30px 0; color: #2d3748; font-size: 16px; line-height: 1.6; text-align: center;">We received a request to reset your password. Use the code below to create a new password for your Enterprise AI account.</p>
                                
                                <!-- Reset Code Button -->
                                <table role="presentation" style="width: 100%; margin: 0;">
                                    <tr>
                                        <td align="center">
                                            <table role="presentation" style="margin: 0;">
                                                <tr>
                                                    <td style="background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%); padding: 18px 60px; border-radius: 50px; box-shadow: 0 8px 20px rgba(220, 38, 38, 0.4); text-align: center;">
                                                        <span style="font-size: 32px; font-weight: 800; color: #ffffff; letter-spacing: 8px; font-family: 'Courier New', monospace;">{otp}</span>
                                                    </td>
                                                </tr>
                                            </table>
                                        </td>
                                    </tr>
                                </table>
                                
                                <p style="margin: 25px 0 0 0; color: #4a5568; font-size: 14px; text-align: center;">
                                    <span style="display: inline-block; padding: 8px 16px; background: rgba(255, 255, 255, 0.8); border-radius: 20px;">⏱️ Code expires in 10 minutes</span>
                                </p>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Security Notice -->
                    <tr>
                        <td style="padding: 0 40px 50px 40px;">
                            <p style="margin: 0; color: rgba(255, 255, 255, 0.9); font-size: 13px; text-align: center; line-height: 1.6;">
                                🔒 If you didn't request a password reset, please ignore this email and your password will remain unchanged.
                            </p>
                        </td>
                    </tr>
                    
                </table>
                
                <!-- Footer -->
                <table role="presentation" style="max-width: 600px; width: 100%; margin-top: 30px;">
                    <tr>
                        <td style="text-align: center; padding: 20px;">
                            <p style="margin: 0 0 8px 0; color: rgba(255, 255, 255, 0.9); font-size: 13px;">Need help? Contact us at <a href="mailto:support@Enterpriseai.com" style="color: #ffffff; text-decoration: underline;">support@Enterpriseai.com</a></p>
                            <p style="margin: 0; color: rgba(255, 255, 255, 0.7); font-size: 12px;">© 2025 Enterprise AI. All rights reserved.</p>
                        </td>
                    </tr>
                </table>
                
            </td>
        </tr>
    </table>
</body>
</html>"""
        
        # Attach both plain text and HTML (multipart/alternative)
        # Plain text should come first
        text_part = MIMEText(text_content, 'plain', 'utf-8')
        html_part = MIMEText(html_content, 'html', 'utf-8')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Connect to SMTP server and send email
        server_logger.info(f"Connecting to SMTP server: {SMTP_HOST}:{SMTP_PORT}")
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(msg)
        
        server_logger.info(f"OTP email sent successfully to {to_email} for {purpose}")
        return True
        
    except Exception as e:
        log_error(e, f"Failed to send OTP email to {to_email}")
        return False

def verify_otp(stored_otp, stored_expiry, provided_otp):
    """
    Verify if the provided OTP matches and is not expired
    
    Args:
        stored_otp: The OTP stored in database
        stored_expiry: The expiry timestamp from database
        provided_otp: The OTP provided by user
    
    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        # Check if OTP exists
        if not stored_otp:
            return False, "No OTP found. Please request a new one."
        
        # Check if OTP matches
        if stored_otp != provided_otp:
            return False, "Invalid OTP code. Please try again."
        
        # Check if OTP is expired
        if stored_expiry:
            expiry_time = datetime.fromisoformat(stored_expiry)
            if datetime.now() > expiry_time:
                return False, "OTP has expired. Please request a new one."
        
        return True, "OTP verified successfully"
        
    except Exception as e:
        log_error(e, "Error verifying OTP")
        return False, "Error verifying OTP. Please try again."
