"""
Logs Management Controller
Handles log file listing, downloading, and deletion
"""

import os
import json
from flask import Blueprint, jsonify, send_file, request
from functools import wraps
from datetime import datetime

# Create blueprint
bp = Blueprint('logs', __name__, url_prefix='/api/logs')

# Get logs directory
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')

def admin_required(f):
    """Decorator to check if user is admin"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # This will be checked by the main app
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/list')
def list_logs():
    """List all log files"""
    try:
        if not os.path.exists(LOGS_DIR):
            return jsonify({'success': True, 'logs': []})
        
        logs = []
        for filename in os.listdir(LOGS_DIR):
            filepath = os.path.join(LOGS_DIR, filename)
            if os.path.isfile(filepath):
                try:
                    size = os.path.getsize(filepath)
                    modified = os.path.getmtime(filepath)
                    modified_date = datetime.fromtimestamp(modified).isoformat()
                    
                    logs.append({
                        'name': filename,
                        'size': size,
                        'modified': modified_date
                    })
                except Exception as e:
                    print(f"Error getting file info for {filename}: {e}")
                    continue
        
        # Sort by modified date (newest first)
        logs.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify({'success': True, 'logs': logs})
    except Exception as e:
        print(f"Error listing logs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/download')
def download_log():
    """Download a log file"""
    try:
        filename = request.args.get('filename')
        if not filename:
            return jsonify({'success': False, 'error': 'Filename required'}), 400
        
        # Security: prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'success': False, 'error': 'Invalid filename'}), 400
        
        filepath = os.path.join(LOGS_DIR, filename)
        
        # Verify file exists and is in logs directory
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Verify the file is actually in the logs directory
        if not os.path.abspath(filepath).startswith(os.path.abspath(LOGS_DIR)):
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400
        
        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        print(f"Error downloading log: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/delete', methods=['POST'])
def delete_log():
    """Delete a log file"""
    try:
        filename = request.args.get('filename')
        if not filename:
            return jsonify({'success': False, 'error': 'Filename required'}), 400
        
        # Security: prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({'success': False, 'error': 'Invalid filename'}), 400
        
        filepath = os.path.join(LOGS_DIR, filename)
        
        # Verify file exists and is in logs directory
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            return jsonify({'success': False, 'error': 'File not found'}), 404
        
        # Verify the file is actually in the logs directory
        if not os.path.abspath(filepath).startswith(os.path.abspath(LOGS_DIR)):
            return jsonify({'success': False, 'error': 'Invalid file path'}), 400
        
        os.remove(filepath)
        return jsonify({'success': True, 'message': f'{filename} deleted successfully'})
    except Exception as e:
        print(f"Error deleting log: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@bp.route('/clear', methods=['POST'])
def clear_all_logs():
    """Clear all log files"""
    try:
        if not os.path.exists(LOGS_DIR):
            return jsonify({'success': True, 'message': 'No logs to clear'})
        
        deleted_count = 0
        for filename in os.listdir(LOGS_DIR):
            filepath = os.path.join(LOGS_DIR, filename)
            if os.path.isfile(filepath):
                try:
                    os.remove(filepath)
                    deleted_count += 1
                except Exception as e:
                    print(f"Error deleting {filename}: {e}")
                    continue
        
        return jsonify({'success': True, 'message': f'{deleted_count} log files deleted'})
    except Exception as e:
        print(f"Error clearing logs: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
