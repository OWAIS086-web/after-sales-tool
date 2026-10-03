from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, current_user
from datetime import datetime
from models.user import User
from models.database import get_db_connection
from utils.logger import auth_logger, log_function_call, log_user_action, log_error


@log_function_call(auth_logger)
def login():
    """Handle user login"""
    if current_user.is_authenticated:
        auth_logger.info(f"Already authenticated user {current_user.username} attempted login")
        return redirect(url_for('chatbot_advanced'))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))
        
        auth_logger.info(f"Login attempt for username: {username}")
        
        if not username or not password:
            auth_logger.warning(f"Login failed - missing credentials for username: {username}")
            flash("Please enter both username and password.", "error")
            return render_template("auth/login.html")
        
        user = User.get_by_username(username)
        if user and User.verify_password(username, password):
            # Update last login
            from services.user_service import UserService
            UserService.update_last_login(user.id)
            
            # Log user in directly (no verification check needed)
            login_user(user, remember=remember)
            
            # Log detailed login information
            login_time = datetime.now().isoformat()
            auth_logger.info(f"✓ LOGIN SUCCESS | User: {username} (ID: {user.id}) | Time: {login_time} | Company: {user.company_id}")
            log_user_action("Login", user.id, f"Username: {username}")
            
            flash(f"Welcome back, {username}!", "success")
            return redirect(url_for('chatbot_advanced'))
        else:
            auth_logger.warning(f"✗ LOGIN FAILED | Username: {username} | Time: {datetime.now().isoformat()} | Reason: Invalid credentials")
            log_user_action("Login Failed", None, f"Username: {username}")
            flash("Invalid username or password.", "error")
    
    return render_template("auth/login.html")


@log_function_call(auth_logger)
def register():
    """Handle user registration"""
    if current_user.is_authenticated:
        auth_logger.info(f"Already authenticated user {current_user.username} attempted registration")
        return redirect(url_for('chatbot_advanced'))
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        company_id = request.form.get("company_id", "haval").strip()
        
        auth_logger.info(f"Registration attempt for username: {username}, email: {email}, company: {company_id}")
        
        # Validation
        if not all([username, email, password, confirm_password]):
            auth_logger.warning(f"Registration failed - missing fields for username: {username}")
            flash("All fields are required.", "error")
            return render_template("auth/register.html")
        
        if password != confirm_password:
            auth_logger.warning(f"Registration failed - password mismatch for username: {username}")
            flash("Passwords do not match.", "error")
            return render_template("auth/register.html")
        
        if len(password) < 6:
            auth_logger.warning(f"Registration failed - password too short for username: {username}")
            flash("Password must be at least 6 characters long.", "error")
            return render_template("auth/register.html")
        
        if len(username) < 3:
            auth_logger.warning(f"Registration failed - username too short: {username}")
            flash("Username must be at least 3 characters long.", "error")
            return render_template("auth/register.html")
        
        if "@" not in email:
            auth_logger.warning(f"Registration failed - invalid email for username: {username}")
            flash("Please enter a valid email address.", "error")
            return render_template("auth/register.html")

        # Validate company_id
        from config import get_enabled_companies
        try:
            enabled_companies = get_enabled_companies()
            if company_id not in enabled_companies:
                auth_logger.warning(f"Registration failed - invalid company {company_id} for username: {username}")
                flash("Invalid company selection.", "error")
                return render_template("auth/register.html", companies=enabled_companies)
        except Exception as e:
            log_error(e, "Failed to get enabled companies")
            # Fallback if config is not available
            if company_id not in ['haval', 'mg', 'kia']:
                company_id = 'haval'
                auth_logger.info(f"Fallback to default company 'haval' for username: {username}")
        
        # Create user (verified immediately)
        user = User.create(username, email, password, company_id, is_verified=True)
        if user:
            auth_logger.info(f"User registered and auto-verified: {username} (ID: {user.id})")

            # Permissions are automatically initialized in database with default TRUE values
            # No need to initialize separately

            # Update last login for new user
            from services.user_service import UserService
            UserService.update_last_login(user.id)

            # Log the user in immediately
            login_user(user)
            
            # Log detailed registration and login information
            login_time = datetime.now().isoformat()
            auth_logger.info(f"✓ REGISTRATION & LOGIN | User: {username} (ID: {user.id}) | Email: {email} | Company: {company_id} | Time: {login_time}")
            
            flash(f"Registration successful! Welcome {username}.", "success")
            return redirect(url_for('chatbot_advanced'))
        else:
            auth_logger.warning(f"Registration failed - user already exists: username={username}, email={email}")
            flash("Username or email already exists. Please choose different ones.", "error")
    
    # Get available companies for the form
    try:
        from config import get_enabled_companies
        companies = get_enabled_companies()
        # auth_logger.debug(f"Available companies loaded: {list(companies.keys())}")
    except Exception as e:
        log_error(e, "Failed to load companies for registration form")
        companies = {'haval': 'Haval', 'mg': 'MG', 'kia': 'Kia'}
    
    return render_template("auth/register.html", companies=companies)


@log_function_call(auth_logger)
def logout():
    """Handle user logout"""
    if current_user.is_authenticated:
        username = current_user.username
        user_id = current_user.id
        
        # Calculate session duration
        from datetime import datetime
        from models.database import get_db_connection
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT last_login FROM users WHERE id = ?", (user_id,))
            result = cur.fetchone()
            conn.close()
            
            if result and result[0]:
                login_time = datetime.fromisoformat(result[0])
                logout_time = datetime.now()
                session_duration = (logout_time - login_time).total_seconds()
                
                # Convert to readable format
                hours = int(session_duration // 3600)
                minutes = int((session_duration % 3600) // 60)
                seconds = int(session_duration % 60)
                
                duration_str = f"{hours}h {minutes}m {seconds}s"
                logout_timestamp = logout_time.isoformat()
                
                auth_logger.info(f"✓ LOGOUT | User: {username} (ID: {user_id}) | Logout Time: {logout_timestamp} | Session Duration: {duration_str}")
            else:
                logout_timestamp = datetime.now().isoformat()
                auth_logger.info(f"✓ LOGOUT | User: {username} (ID: {user_id}) | Logout Time: {logout_timestamp}")
        except Exception as e:
            logout_timestamp = datetime.now().isoformat()
            auth_logger.info(f"✓ LOGOUT | User: {username} (ID: {user_id}) | Logout Time: {logout_timestamp}")
        
        logout_user()
        log_user_action("Logout", user_id, f"Username: {username}")
        flash("You have been logged out.", "info")
    else:
        auth_logger.warning("Logout attempt by non-authenticated user")
    
    return redirect(url_for('login'))



@log_function_call(auth_logger)
def verify_otp():
    """OTP verification endpoint - deprecated"""
    auth_logger.info("verify_otp endpoint called - OTP verification is no longer used")
    flash("Email verification is no longer required. Please log in.", "info")
    return redirect(url_for('login'))


@log_function_call(auth_logger)
def resend_otp():
    """Resend OTP endpoint - deprecated"""
    auth_logger.info("resend_otp endpoint called - OTP verification is no longer used")
    return jsonify({"success": False, "message": "Email verification is no longer required"})


@log_function_call(auth_logger)
def forgot_password():
    """Handle forgot password request"""
    if current_user.is_authenticated:
        return redirect(url_for('chatbot_advanced'))
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        
        if not email:
            flash("Please enter your email address.", "error")
            return render_template("auth/forgot_password.html")
        
        # Check if user exists
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, username FROM users WHERE email = ?", (email,))
            user = cur.fetchone()
            
            if user:
                from utils.email_service import generate_otp, send_otp_email
                from datetime import timedelta
                
                otp = generate_otp()
                otp_expiry = datetime.now() + timedelta(minutes=10)
                
                # Store reset OTP
                cur.execute("""
                    UPDATE users 
                    SET reset_otp = ?, reset_otp_expiry = ? 
                    WHERE id = ?
                """, (otp, otp_expiry.isoformat(), user[0]))
                conn.commit()
                
                # Send OTP email
                if send_otp_email(email, otp, purpose="reset"):
                    session['reset_user_id'] = user[0]
                    session['reset_email'] = email
                    auth_logger.info(f"Password reset OTP sent to {email}")
                    flash("Password reset code sent to your email.", "success")
                    conn.close()
                    return redirect(url_for('reset_password'))
                else:
                    flash("Failed to send reset code. Please try again.", "error")
            else:
                # Don't reveal if email exists or not for security
                flash("If an account exists with this email, you will receive a password reset code.", "info")
            
            conn.close()
            
        except Exception as e:
            log_error(e, f"Error in forgot password for {email}")
            flash("Error processing request. Please try again.", "error")
    
    return render_template("auth/forgot_password.html")


@log_function_call(auth_logger)
def reset_password():
    """Handle password reset with OTP"""
    if current_user.is_authenticated:
        return redirect(url_for('chatbot_advanced'))
    
    reset_user_id = session.get('reset_user_id')
    reset_email = session.get('reset_email')
    
    if not reset_user_id:
        flash("No password reset request found. Please start over.", "error")
        return redirect(url_for('forgot_password'))
    
    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")
        
        if not all([otp, new_password, confirm_password]):
            flash("All fields are required.", "error")
            return render_template("auth/reset_password.html", email=reset_email)
        
        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("auth/reset_password.html", email=reset_email)
        
        if len(new_password) < 6:
            flash("Password must be at least 6 characters long.", "error")
            return render_template("auth/reset_password.html", email=reset_email)
        
        # Verify OTP and reset password
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT reset_otp, reset_otp_expiry, username 
                FROM users 
                WHERE id = ?
            """, (reset_user_id,))
            
            result = cur.fetchone()
            
            if result:
                from utils.email_service import verify_otp as check_otp
                is_valid, message = check_otp(result[0], result[1], otp)
                
                if is_valid:
                    # Update password
                    from werkzeug.security import generate_password_hash
                    password_hash = generate_password_hash(new_password)
                    
                    cur.execute("""
                        UPDATE users 
                        SET password_hash = ?, reset_otp = NULL, reset_otp_expiry = NULL 
                        WHERE id = ?
                    """, (password_hash, reset_user_id))
                    conn.commit()
                    
                    session.pop('reset_user_id', None)
                    session.pop('reset_email', None)
                    
                    auth_logger.info(f"Password reset successful for user {result[2]}")
                    log_user_action("Password Reset", reset_user_id, f"Username: {result[2]}")
                    flash("Password reset successful! You can now log in with your new password.", "success")
                    conn.close()
                    return redirect(url_for('login'))
                else:
                    flash(message, "error")
            else:
                flash("User not found. Please try again.", "error")
                conn.close()
                return redirect(url_for('forgot_password'))
            
            conn.close()
            
        except Exception as e:
            log_error(e, f"Error resetting password for user {reset_user_id}")
            flash("Error resetting password. Please try again.", "error")
    
    return render_template("auth/reset_password.html", email=reset_email)


@log_function_call(auth_logger)
def resend_reset_otp():
    """Resend password reset OTP"""
    reset_user_id = session.get('reset_user_id')
    reset_email = session.get('reset_email')
    
    if not reset_user_id or not reset_email:
        return jsonify({"success": False, "message": "No password reset request found"})
    
    try:
        from utils.email_service import generate_otp, send_otp_email
        from datetime import timedelta
        
        otp = generate_otp()
        otp_expiry = datetime.now() + timedelta(minutes=10)
        
        # Update reset OTP in database
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE users 
            SET reset_otp = ?, reset_otp_expiry = ? 
            WHERE id = ?
        """, (otp, otp_expiry.isoformat(), reset_user_id))
        conn.commit()
        conn.close()
        
        # Send OTP email
        if send_otp_email(reset_email, otp, purpose="reset"):
            auth_logger.info(f"Reset OTP resent to {reset_email}")
            return jsonify({"success": True, "message": "Reset code sent successfully"})
        else:
            return jsonify({"success": False, "message": "Failed to send reset code"})
            
    except Exception as e:
        log_error(e, f"Error resending reset OTP to {reset_email}")
        return jsonify({"success": False, "message": "Error sending reset code"})
