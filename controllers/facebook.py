from flask import render_template, request, jsonify, flash, url_for
from flask_login import current_user, login_required
from utils.logger import server_logger, log_function_call, log_user_action, log_error
import json
import os
from datetime import datetime
from typing import List, Dict, Any


@log_function_call(server_logger)
def view_facebook():
    """View all Facebook posts page with filtering options - Only for Haval users"""
    
    # Check if user has access to Facebook data (only Haval users)
    user_company = current_user.company_id or 'haval'
    server_logger.info(f"Facebook view accessed by user {current_user.username} (company: {user_company})")
    
    if user_company != 'haval':
        server_logger.warning(f"Facebook access denied for user {current_user.username} (company: {user_company})")
        log_user_action("Facebook Access Denied", current_user.id, f"Company: {user_company}")
        
        flash(f"Facebook data is only available for Haval users. You are registered as {user_company.title()} user.", "error")
        return render_template("access_denied.html", 
                             message="Facebook Access Restricted",
                             description=f"Facebook data is only available for Haval users. You are registered as a {user_company.title()} user.",
                             redirect_url=url_for('chatbot_advanced'),
                             redirect_text="Go to Chatbot")
    
    # Get filter parameters
    message_type_filter = request.args.get('type', 'all')
    customer_filter = request.args.get('customer', '')
    date_filter = request.args.get('date', 'all')
    
    server_logger.info(f"Facebook filters applied by {current_user.username}: type={message_type_filter}, customer={customer_filter}, date={date_filter}")
    
    try:
        # Get Facebook posts
        server_logger.info(f"Fetching Facebook posts for user {current_user.username}")
        posts = get_facebook_posts(
            message_type=message_type_filter,
            customer_name=customer_filter,
            date_filter=date_filter,
            limit=1000
        )
        
        # Get statistics
        server_logger.info(f"Fetching Facebook statistics for user {current_user.username}")
        stats = get_facebook_statistics()
        
        # Get unique customers for filter dropdown
        customers = get_unique_customers()
        
        server_logger.info(f"Facebook data loaded successfully for user {current_user.username}: {len(posts)} posts, {len(customers)} customers")
        log_user_action("Facebook Data Viewed", current_user.id, f"Posts: {len(posts)}, Filters: type={message_type_filter}")
        
        return render_template("facebook/view_facebook.html", 
                             posts=posts,
                             stats=stats,
                             customers=customers,
                             current_filters={
                                 'type': message_type_filter,
                                 'customer': customer_filter,
                                 'date': date_filter
                             })
        
    except Exception as e:
        server_logger.error(f"Error loading Facebook data for user {current_user.username}: {str(e)}")
        log_error("Facebook Data Load Error", current_user.id, str(e))
        flash("Error loading Facebook data. Please try again.", "error")
        return render_template("facebook/view_facebook.html", 
                             posts=[],
                             stats={},
                             customers=[],
                             current_filters={})


def get_facebook_posts(message_type='all', customer_name='', date_filter='all', issue_filter='all', limit=1000) -> List[Dict[str, Any]]:
    """Load Facebook posts from JSON file with advanced filtering"""
    
    try:
        # Load Facebook posts from JSON file
        json_file_path = os.path.join('data', 'facebook_issues.json')
        
        if not os.path.exists(json_file_path):
            server_logger.error(f"Facebook data file not found: {json_file_path}")
            return []
        
        with open(json_file_path, 'r', encoding='utf-8') as f:
            posts = json.load(f)
        
        server_logger.info(f"Loaded {len(posts)} Facebook posts from {json_file_path}")
        
        # Define issue patterns for filtering
        issue_patterns = {
            'head_unit': ['head unit', 'infotainment', 'screen', 'display', 'reboot', 'restart'],
            'cruise_control': ['cruise control', 'cruise', 'speed control'],
            'lane_assist': ['lane assist', 'lane departure', 'lane keep', 'lane warning'],
            'tpms': ['tpms', 'tire pressure', 'tyre pressure', 'pressure warning'],
            'ac_issues': ['ac', 'air conditioning', 'cooling', 'heating', 'climate'],
            'engine_issues': ['engine', 'motor', 'power', 'acceleration', 'rpm'],
            'brake_issues': ['brake', 'braking', 'abs', 'brake pedal'],
            'transmission': ['transmission', 'gear', 'shifting', 'cvt', 'gearbox'],
            'fuel_issues': ['fuel', 'mileage', 'consumption', 'average', 'efficiency'],
            'electrical': ['electrical', 'battery', 'charging', 'power', 'lights'],
            'suspension': ['suspension', 'shock', 'ride', 'comfort', 'bumpy'],
            'noise_issues': ['noise', 'sound', 'vibration', 'rattling', 'squeaking']
        }
        
        # Apply filters
        filtered_posts = []
        
        for post in posts:
            # Message type filter
            if message_type != 'all' and post.get('message_type', '').lower() != message_type.lower():
                continue
            
            # Customer name filter
            if customer_name and customer_name.lower() not in post.get('customer_name', '').lower():
                continue
            
            # Date filter
            if date_filter != 'all':
                try:
                    post_date = datetime.fromisoformat(post.get('timestamp', '').replace('Z', '+00:00'))
                    now = datetime.now()
                    
                    if date_filter == 'today' and (now - post_date).days > 1:
                        continue
                    elif date_filter == 'week' and (now - post_date).days > 7:
                        continue
                    elif date_filter == 'month' and (now - post_date).days > 30:
                        continue
                    # 'recent' filter removed - now shows all available data
                except:
                    pass
            
            # Issue-specific filter
            if issue_filter != 'all':
                content_lower = post.get('content', '').lower()
                issue_keywords = issue_patterns.get(issue_filter, [])
                
                if not any(keyword in content_lower for keyword in issue_keywords):
                    continue
            
            # Add processed fields
            post['processed_timestamp'] = format_timestamp(post.get('timestamp', ''))
            post['message_preview'] = post.get('content', '')[:100] + '...' if len(post.get('content', '')) > 100 else post.get('content', '')
            
            # Detect and add issue categories
            content_lower = post.get('content', '').lower()
            detected_issues = []
            for issue_type, keywords in issue_patterns.items():
                if any(keyword in content_lower for keyword in keywords):
                    detected_issues.append(issue_type.replace('_', ' ').title())
            
            post['detected_issues'] = detected_issues
            post['primary_issue'] = detected_issues[0] if detected_issues else 'General'
            
            filtered_posts.append(post)
        
        # Sort by timestamp (newest first)
        filtered_posts.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Apply limit
        if limit:
            filtered_posts = filtered_posts[:limit]
        
        server_logger.info(f"Filtered Facebook posts: {len(filtered_posts)} posts after filtering")
        return filtered_posts
        
    except Exception as e:
        server_logger.error(f"Error loading Facebook posts: {str(e)}")
        return []


def get_facebook_statistics() -> Dict[str, Any]:
    """Get comprehensive Facebook posts statistics with issue analysis"""
    
    try:
        posts = get_facebook_posts()  # Get all posts for stats
        
        if not posts:
            return {}
        
        # Basic statistics
        total_posts = len(posts)
        complaints = len([p for p in posts if p.get('message_type', '').lower() == 'complaint'])
        queries = len([p for p in posts if p.get('message_type', '').lower() == 'query'])
        issues = len([p for p in posts if p.get('message_type', '').lower() == 'issue'])
        
        # Get unique customers
        unique_customers = len(set(p.get('customer_name', '') for p in posts))
        
        # Date-based analysis
        from datetime import datetime, timedelta
        now = datetime.now()
        
        recent_posts = 0  # Last 3 days
        weekly_posts = 0  # Last 7 days
        monthly_posts = 0  # Last 30 days
        
        for post in posts:
            try:
                post_date = datetime.fromisoformat(post.get('timestamp', '').replace('Z', '+00:00'))
                days_ago = (now - post_date).days
                
                if days_ago <= 3:
                    recent_posts += 1
                if days_ago <= 7:
                    weekly_posts += 1
                if days_ago <= 30:
                    monthly_posts += 1
            except:
                pass
        
        # Issue analysis
        issue_patterns = {
            'head_unit': ['head unit', 'infotainment', 'screen', 'display', 'reboot', 'restart'],
            'cruise_control': ['cruise control', 'cruise', 'speed control'],
            'lane_assist': ['lane assist', 'lane departure', 'lane keep', 'lane warning'],
            'tpms': ['tpms', 'tire pressure', 'tyre pressure', 'pressure warning'],
            'ac_issues': ['ac', 'air conditioning', 'cooling', 'heating', 'climate'],
            'engine_issues': ['engine', 'motor', 'power', 'acceleration', 'rpm'],
            'brake_issues': ['brake', 'braking', 'abs', 'brake pedal'],
            'transmission': ['transmission', 'gear', 'shifting', 'cvt', 'gearbox'],
            'fuel_issues': ['fuel', 'mileage', 'consumption', 'average', 'efficiency'],
            'electrical': ['electrical', 'battery', 'charging', 'power', 'lights'],
            'suspension': ['suspension', 'shock', 'ride', 'comfort', 'bumpy'],
            'noise_issues': ['noise', 'sound', 'vibration', 'rattling', 'squeaking']
        }
        
        issue_counts = {}
        for issue_type, keywords in issue_patterns.items():
            count = 0
            for post in posts:
                content_lower = post.get('content', '').lower()
                if any(keyword in content_lower for keyword in keywords):
                    count += 1
            issue_counts[issue_type.replace('_', ' ').title()] = count
        
        # Sort issues by frequency
        top_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        # Severity analysis (complaints are high severity)
        high_severity = complaints
        medium_severity = issues
        low_severity = queries
        
        stats = {
            'total_posts': total_posts,
            'complaints': complaints,
            'queries': queries,
            'issues': issues,
            'unique_customers': unique_customers,
            'recent_posts': recent_posts,
            'weekly_posts': weekly_posts,
            'monthly_posts': monthly_posts,
            'complaint_rate': round((complaints / total_posts * 100), 1) if total_posts > 0 else 0,
            'query_rate': round((queries / total_posts * 100), 1) if total_posts > 0 else 0,
            'issue_rate': round((issues / total_posts * 100), 1) if total_posts > 0 else 0,
            'top_issues': dict(top_issues),
            'severity_analysis': {
                'high_severity': high_severity,
                'medium_severity': medium_severity,
                'low_severity': low_severity
            },
            'activity_trends': {
                'daily_average': round(recent_posts / 3, 1) if recent_posts > 0 else 0,
                'weekly_average': round(weekly_posts / 7, 1) if weekly_posts > 0 else 0,
                'monthly_average': round(monthly_posts / 30, 1) if monthly_posts > 0 else 0
            }
        }
        
        server_logger.info(f"Facebook statistics calculated: {stats}")
        return stats
        
    except Exception as e:
        server_logger.error(f"Error calculating Facebook statistics: {str(e)}")
        return {}


def get_unique_customers() -> List[str]:
    """Get list of unique customer names for filtering"""
    
    try:
        posts = get_facebook_posts()  # Get all posts
        customers = list(set(p.get('CustomerName', '') for p in posts if p.get('CustomerName')))
        customers.sort()
        
        server_logger.info(f"Found {len(customers)} unique Facebook customers")
        return customers
        
    except Exception as e:
        server_logger.error(f"Error getting unique customers: {str(e)}")
        return []


def format_timestamp(timestamp_str: str) -> str:
    """Format timestamp for display"""
    
    try:
        if not timestamp_str:
            return 'Unknown'
        
        # Parse ISO timestamp
        dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        
        # Format for display
        return dt.strftime('%Y-%m-%d %H:%M:%S')
        
    except Exception as e:
        server_logger.error(f"Error formatting timestamp {timestamp_str}: {str(e)}")
        return timestamp_str


def process_facebook_data_for_ai():
    """Process Facebook data for AI analysis and save to facebook_issues.json"""
    
    try:
        server_logger.info("Starting Facebook data processing for AI analysis")
        
        # Load raw Facebook posts
        posts = get_facebook_posts()
        
        if not posts:
            server_logger.warning("No Facebook posts found for processing")
            return False
        
        # Filter and process issues, complaints, and queries
        processed_data = []
        
        for post in posts:
            message_type = post.get('MessageType', '').lower()
            
            # Only process complaints, issues, and queries
            if message_type in ['complaint', 'issue', 'query']:
                processed_item = {
                    'id': post.get('FacebookPostID', ''),
                    'customer_name': post.get('CustomerName', ''),
                    'message_type': message_type,
                    'content': post.get('Message', ''),
                    'timestamp': post.get('Timestamp', ''),
                    'country_code': post.get('CountryCode', 92),
                    'source': 'facebook_group',
                    'processed_at': datetime.now().isoformat()
                }
                
                processed_data.append(processed_item)
        
        # Save processed data to facebook_issues.json
        output_file = os.path.join('data', 'facebook_issues.json')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(processed_data, f, indent=2, ensure_ascii=False)
        
        server_logger.info(f"Facebook data processed successfully: {len(processed_data)} items saved to {output_file}")
        
        return True
        
    except Exception as e:
        server_logger.error(f"Error processing Facebook data for AI: {str(e)}")
        return False


# API endpoints for Facebook data
@log_function_call(server_logger)
def api_facebook_posts():
    """API endpoint to get Facebook posts with advanced filtering"""
    
    try:
        # Get query parameters
        message_type = request.args.get('type', 'all')
        customer = request.args.get('customer', '')
        date_filter = request.args.get('date', 'all')
        issue_filter = request.args.get('issue', 'all')
        limit = int(request.args.get('limit', 100))
        
        # Get posts with advanced filtering
        posts = get_facebook_posts(
            message_type=message_type,
            customer_name=customer,
            date_filter=date_filter,
            issue_filter=issue_filter,
            limit=limit
        )
        
        return jsonify({
            'success': True,
            'posts': posts,
            'count': len(posts),
            'filters_applied': {
                'message_type': message_type,
                'customer': customer,
                'date_filter': date_filter,
                'issue_filter': issue_filter
            }
        })
        
    except Exception as e:
        server_logger.error(f"Error in Facebook posts API: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'posts': [],
            'count': 0
        }), 500


@log_function_call(server_logger)
def api_facebook_issue_insights():
    """API endpoint to get Facebook issue insights and analysis"""
    
    try:
        # Get query parameters
        issue_type = request.args.get('issue_type', 'all')
        date_range = request.args.get('date_range', 'all')
        
        # Get comprehensive statistics
        stats = get_facebook_statistics()
        
        # Get posts for specific issue analysis
        if issue_type != 'all':
            issue_posts = get_facebook_posts(issue_filter=issue_type, limit=50)
        else:
            issue_posts = get_facebook_posts(limit=50)
        
        # Generate insights
        insights = {
            'overview': {
                'total_posts': stats.get('total_posts', 0),
                'total_issues': len([p for p in issue_posts if p.get('detected_issues')]),
                'severity_breakdown': stats.get('severity_analysis', {}),
                'activity_trends': stats.get('activity_trends', {})
            },
            'top_issues': stats.get('top_issues', {}),
            'recent_activity': {
                'last_3_days': stats.get('recent_posts', 0),
                'last_week': stats.get('weekly_posts', 0),
                'last_month': stats.get('monthly_posts', 0)
            },
            'issue_analysis': {
                'most_common_complaints': [
                    issue for issue, count in sorted(stats.get('top_issues', {}).items(), 
                                                   key=lambda x: x[1], reverse=True)[:5]
                ],
                'trending_issues': [
                    p.get('primary_issue', 'General') for p in issue_posts[:10]
                ]
            }
        }
        
        return jsonify({
            'success': True,
            'insights': insights,
            'statistics': stats,
            'sample_posts': issue_posts[:10]  # Sample posts for context
        })
        
    except Exception as e:
        server_logger.error(f"Error in Facebook issue insights API: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'insights': {},
            'statistics': {}
        }), 500


@log_function_call(server_logger)
def api_facebook_stats():
    """API endpoint to get Facebook statistics"""
    
    try:
        stats = get_facebook_statistics()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        server_logger.error(f"Error in Facebook stats API: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'stats': {}
        }), 500


@log_function_call(server_logger)
def api_process_facebook_data():
    """API endpoint to process Facebook data for AI"""
    
    try:
        success = process_facebook_data_for_ai()
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Facebook data processed successfully for AI analysis'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to process Facebook data'
            }), 500
        
    except Exception as e:
        server_logger.error(f"Error in Facebook data processing API: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500