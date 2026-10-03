"""
Settings controller for managing application configuration.
Provides web interface for editing server settings, feature flags, and other configuration options.
"""

from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from config.config_loader import get_config, reload_config
from utils.logger import server_logger
from utils.logging_config import LoggingConfigManager
import json


def settings_page():
    """Display the settings management page"""
    try:
        from models.datasource_permissions import DataSourcePermissions
        from scheduler.decorators import is_admin_user
        config = get_config()

        # Get user permissions for data sources
        user_permissions = DataSourcePermissions.get_user_permissions(current_user.id)
        
        is_admin = is_admin_user(current_user)

        # Check if user has admin privileges (for now, all users can access settings)
        # In production, you might want to add role-based access control
        
        # Get current configuration (excluding sensitive data)
        current_config = config.export_config()
        
        # Get server status information
        server_info = {
            'host': config.get('server.host'),
            'port': config.get('server.port'),
            'debug_mode': config.get('server.debug'),
            'auto_reload': config.get('server.auto_reload'),
            'is_production': config.is_production(),
            'maintenance_mode': config.is_maintenance_mode()
        }
        
        # Get feature flags
        features = config.get_feature_flags()
        
        # Get user's company features and configuration
        user_company = current_user.company_id or 'haval'
        
        # Get company-specific configuration
        from config import get_company_config
        try:
            company_config = get_company_config(user_company)
        except Exception as e:
            server_logger.warning(f"Could not load company config for {user_company}: {e}")
            company_config = None
        
        company_features = config.get_company_features(user_company)
        
        # Get logging configuration
        logging_manager = LoggingConfigManager()
        logging_config = logging_manager.load_config()
        log_levels = logging_manager.get_log_levels()
        log_files = logging_manager.list_log_files()
        
        server_logger.info(f"Settings page accessed by user {current_user.username}")
        server_logger.info(f"Found {len(log_files)} log files")
        server_logger.info(f"Log levels: {log_levels}")

        # Check if user is scheduler admin
        try:
            from scheduler.decorators import is_admin_user
            is_scheduler_admin = is_admin_user(current_user)
        except:
            is_scheduler_admin = False

        return render_template('settings.html',
                             config=current_config,
                             server_info=server_info,
                             features=features,
                             user=current_user,
                             company_features=company_features,
                             user_company=user_company,
                             selected_company=user_company,
                             company_config=company_config,
                             logging_config=logging_config,
                             log_levels=log_levels,
                             log_files=log_files,
                             is_scheduler_admin=is_scheduler_admin,
                             user_permissions=user_permissions,
                             is_admin=is_admin)
    
    except Exception as e:
        server_logger.error(f"Error loading settings page: {e}")
        flash(f"Error loading settings: {str(e)}", "error")
        return redirect(url_for('chatbot_advanced'))


def update_settings():
    """Update application settings"""
    if request.method != 'POST':
        return redirect(url_for('settings_page'))
    
    try:
        config = get_config()
        
        # Get form data
        form_data = request.form.to_dict()
        json_data = request.get_json() if request.is_json else {}
        
        # Combine form and JSON data
        updates = {**form_data, **json_data}
        
        # Process different types of updates
        updated_sections = []
        
        # Server settings
        if 'server_host' in updates:
            config.set('server.host', updates['server_host'])
            updated_sections.append('Server Host')
        
        if 'server_port' in updates:
            try:
                port = int(updates['server_port'])
                if 1 <= port <= 65535:
                    config.set('server.port', port)
                    updated_sections.append('Server Port')
                else:
                    flash("Port must be between 1 and 65535", "error")
            except ValueError:
                flash("Invalid port number", "error")
        
        if 'debug_mode' in updates:
            debug = updates['debug_mode'].lower() in ['true', '1', 'on', 'yes']
            config.set('server.debug', debug)
            updated_sections.append('Debug Mode')
        
        if 'auto_reload' in updates:
            auto_reload = updates['auto_reload'].lower() in ['true', '1', 'on', 'yes']
            config.set('server.auto_reload', auto_reload)
            updated_sections.append('Auto Reload')
        
        # Logging settings
        logging_manager = LoggingConfigManager()
        
        if 'log_level' in updates:
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            if updates['log_level'] in valid_levels:
                config.set('logging.level', updates['log_level'])
                updated_sections.append('Log Level')
        
        # Individual logger level updates
        for key, value in updates.items():
            if key.startswith('logger_level_'):
                logger_name = key.replace('logger_level_', '')
                if value in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
                    # Convert 'root' to empty string for root logger
                    actual_logger_name = '' if logger_name == 'root' else logger_name
                    if logging_manager.set_log_level(actual_logger_name, value):
                        updated_sections.append(f'Logger: {logger_name}')
        
        if 'console_logging' in updates:
            console_logging = updates['console_logging'].lower() in ['true', '1', 'on', 'yes']
            config.set('logging.console_logging', console_logging)
            updated_sections.append('Console Logging')
        
        if 'max_log_size' in updates:
            try:
                size_mb = int(updates['max_log_size'])
                size_bytes = size_mb * 1048576  # Convert MB to bytes
                config.set('logging.max_log_size', size_bytes)
                updated_sections.append('Max Log Size')
            except ValueError:
                flash("Invalid log file size", "error")
        
        if 'backup_count' in updates:
            try:
                backup_count = int(updates['backup_count'])
                if 1 <= backup_count <= 20:
                    config.set('logging.backup_count', backup_count)
                    updated_sections.append('Backup Count')
                else:
                    flash("Backup count must be between 1 and 20", "error")
            except ValueError:
                flash("Invalid backup count", "error")
        
        # Feature flags
        feature_updates = {k: v for k, v in updates.items() if k.startswith('feature_')}
        for feature_key, value in feature_updates.items():
            feature_name = feature_key.replace('feature_', '')
            enabled = value.lower() in ['true', '1', 'on', 'yes']
            config.set(f'features.{feature_name}', enabled)
            updated_sections.append(f'Feature: {feature_name}')
        
        # Performance settings
        if 'cache_enabled' in updates:
            cache_enabled = updates['cache_enabled'].lower() in ['true', '1', 'on', 'yes']
            config.set('performance.cache_enabled', cache_enabled)
            updated_sections.append('Cache')
        
        if 'compression_enabled' in updates:
            compression = updates['compression_enabled'].lower() in ['true', '1', 'on', 'yes']
            config.set('performance.compression_enabled', compression)
            updated_sections.append('Compression')
        
        # Maintenance mode
        if 'maintenance_mode' in updates:
            maintenance = updates['maintenance_mode'].lower() in ['true', '1', 'on', 'yes']
            config.set('maintenance.maintenance_mode', maintenance)
            updated_sections.append('Maintenance Mode')
        
        if 'maintenance_message' in updates:
            config.set('maintenance.maintenance_message', updates['maintenance_message'])
            updated_sections.append('Maintenance Message')
        
        # Save configuration
        if config.save():
            if updated_sections:
                flash(f"Settings updated: {', '.join(updated_sections)}", "success")
                server_logger.info(f"Settings updated by {current_user.username}: {', '.join(updated_sections)}")
            else:
                flash("No changes detected", "info")
            
            # Check if server restart is needed
            restart_needed = any(section in ['Server Host', 'Server Port', 'Debug Mode', 'Auto Reload'] 
                               for section in updated_sections)
            
            if restart_needed:
                flash("⚠️ Server restart required for some changes to take effect", "warning")
            
            if request.is_json:
                return jsonify({
                    "success": True,
                    "message": f"Settings updated: {', '.join(updated_sections)}",
                    "restart_needed": restart_needed
                })
        else:
            flash("Error saving settings", "error")
            if request.is_json:
                return jsonify({"success": False, "error": "Error saving settings"})
    
    except Exception as e:
        server_logger.error(f"Error updating settings: {e}")
        flash(f"Error updating settings: {str(e)}", "error")
        if request.is_json:
            return jsonify({"success": False, "error": str(e)})
    
    return redirect(url_for('settings_page'))


def get_settings_api():
    """API endpoint to get current settings"""
    try:
        config = get_config()
        
        return jsonify({
            "success": True,
            "config": config.export_config(),
            "server_info": {
                'host': config.get('server.host'),
                'port': config.get('server.port'),
                'debug_mode': config.get('server.debug'),
                'auto_reload': config.get('server.auto_reload'),
                'is_production': config.is_production(),
                'maintenance_mode': config.is_maintenance_mode()
            },
            "features": config.get_feature_flags()
        })
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def reset_settings():
    """Reset settings to defaults"""
    try:
        config = get_config()
        
        # Backup current config
        backup_config = config.config.copy()
        
        # Reset to defaults (reload from file or use built-in defaults)
        config.config = {}
        config._setup_defaults()
        
        if config.save():
            flash("Settings reset to defaults", "success")
            server_logger.info(f"Settings reset to defaults by {current_user.username}")
            
            if request.is_json:
                return jsonify({"success": True, "message": "Settings reset to defaults"})
        else:
            # Restore backup on failure
            config.config = backup_config
            flash("Error resetting settings", "error")
            if request.is_json:
                return jsonify({"success": False, "error": "Error resetting settings"})
    
    except Exception as e:
        server_logger.error(f"Error resetting settings: {e}")
        flash(f"Error resetting settings: {str(e)}", "error")
        if request.is_json:
            return jsonify({"success": False, "error": str(e)})
    
    return redirect(url_for('settings_page'))


def export_settings():
    """Export current settings as JSON"""
    try:
        config = get_config()
        
        export_data = {
            "app_info": {
                "name": config.get('app.name'),
                "version": config.get('app.version'),
                "export_date": config.get('app.build_date')
            },
            "config": config.export_config()
        }
        
        return jsonify(export_data)
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def import_settings():
    """Import settings from JSON"""
    try:
        if 'config_file' not in request.files:
            flash("No configuration file provided", "error")
            return redirect(url_for('settings_page'))
        
        file = request.files['config_file']
        if file.filename == '':
            flash("No file selected", "error")
            return redirect(url_for('settings_page'))
        
        if not file.filename.endswith('.json'):
            flash("Only JSON files are supported", "error")
            return redirect(url_for('settings_page'))
        
        # Parse JSON
        import_data = json.loads(file.read().decode('utf-8'))
        
        if 'config' not in import_data:
            flash("Invalid configuration file format", "error")
            return redirect(url_for('settings_page'))
        
        config = get_config()
        
        # Update configuration
        imported_config = import_data['config']
        
        # Remove sensitive data from import
        if 'server' in imported_config and 'secret_key' in imported_config['server']:
            del imported_config['server']['secret_key']
        
        # Merge configurations
        config.config.update(imported_config)
        config._validate_config()
        
        if config.save():
            flash("Settings imported successfully", "success")
            server_logger.info(f"Settings imported by {current_user.username}")
        else:
            flash("Error saving imported settings", "error")
    
    except json.JSONDecodeError:
        flash("Invalid JSON file", "error")
    except Exception as e:
        server_logger.error(f"Error importing settings: {e}")
        flash(f"Error importing settings: {str(e)}", "error")
    
    return redirect(url_for('settings_page'))


def restart_server():
    """Restart the Flask server (development only)"""
    try:
        config = get_config()
        
        if config.is_production():
            flash("Server restart not available in production mode", "error")
            return jsonify({"success": False, "error": "Not available in production"})
        
        # In development, we can trigger a restart by touching a file
        # This works with Flask's auto-reloader
        import os
        import time
        
        restart_file = "restart.trigger"
        with open(restart_file, 'w') as f:
            f.write(str(time.time()))
        
        # Clean up the trigger file after a delay
        def cleanup():
            time.sleep(2)
            if os.path.exists(restart_file):
                os.remove(restart_file)
        
        import threading
        threading.Thread(target=cleanup).start()
        
        flash("Server restart initiated", "info")
        server_logger.info(f"Server restart triggered by {current_user.username}")
        
        return jsonify({"success": True, "message": "Server restart initiated"})
    
    except Exception as e:
        server_logger.error(f"Error restarting server: {e}")
        return jsonify({"success": False, "error": str(e)})


def get_logging_status():
    """API endpoint to get current logging status"""
    try:
        logging_manager = LoggingConfigManager()
        
        return jsonify({
            "success": True,
            "log_levels": logging_manager.get_log_levels(),
            "log_files": logging_manager.list_log_files(),
            "config": logging_manager.load_config()
        })
    
    except Exception as e:
        server_logger.error(f"Error getting logging status: {e}")
        return jsonify({"success": False, "error": str(e)})


def rotate_logs():
    """API endpoint to rotate log files"""
    try:
        logging_manager = LoggingConfigManager()
        rotated_count = logging_manager.rotate_logs()
        
        server_logger.info(f"Log rotation triggered by {current_user.username}")
        
        return jsonify({
            "success": True,
            "message": f"Rotated {rotated_count} log files",
            "rotated_count": rotated_count
        })
    
    except Exception as e:
        server_logger.error(f"Error rotating logs: {e}")
        return jsonify({"success": False, "error": str(e)})


def cleanup_logs():
    """API endpoint to clean up old log files"""
    try:
        days_to_keep = int(request.args.get('days', 30))
        
        if days_to_keep < 1:
            return jsonify({"success": False, "error": "Days must be at least 1"})
        
        logging_manager = LoggingConfigManager()
        cleaned_count = logging_manager.cleanup_old_logs(days_to_keep)
        
        server_logger.info(f"Log cleanup triggered by {current_user.username} - {cleaned_count} files removed")
        
        return jsonify({
            "success": True,
            "message": f"Cleaned up {cleaned_count} old log files",
            "cleaned_count": cleaned_count
        })
    
    except ValueError:
        return jsonify({"success": False, "error": "Invalid days parameter"})
    except Exception as e:
        server_logger.error(f"Error cleaning up logs: {e}")
        return jsonify({"success": False, "error": str(e)})


def set_logger_level():
    """API endpoint to set individual logger level"""
    try:
        data = request.get_json()
        logger_name = data.get('logger_name', '')
        level = data.get('level', 'INFO')
        
        if level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            return jsonify({"success": False, "error": "Invalid log level"})
        
        logging_manager = LoggingConfigManager()
        
        # Convert 'root' to empty string for root logger
        actual_logger_name = '' if logger_name == 'root' else logger_name
        
        if logging_manager.set_log_level(actual_logger_name, level):
            server_logger.info(f"Log level changed by {current_user.username}: {logger_name} -> {level}")
            
            return jsonify({
                "success": True,
                "message": f"Set {logger_name or 'root'} log level to {level}"
            })
        else:
            return jsonify({"success": False, "error": "Failed to set log level"})
    
    except Exception as e:
        server_logger.error(f"Error setting logger level: {e}")
        return jsonify({"success": False, "error": str(e)})


def download_log_file():
    """API endpoint to download a specific log file"""
    try:
        filename = request.args.get('filename')
        if not filename:
            return jsonify({"success": False, "error": "No filename provided"})
        
        logging_manager = LoggingConfigManager()
        log_files = logging_manager.list_log_files()
        
        if filename not in log_files:
            return jsonify({"success": False, "error": "Log file not found"})
        
        log_file_path = log_files[filename]['path']
        
        from flask import send_file
        return send_file(log_file_path, as_attachment=True, download_name=filename)
    
    except Exception as e:
        server_logger.error(f"Error downloading log file: {e}")
        return jsonify({"success": False, "error": str(e)})