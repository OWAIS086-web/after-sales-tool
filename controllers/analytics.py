import os
from datetime import datetime

from flask import jsonify, make_response, render_template, request, send_file
from flask_login import current_user, login_required

from controllers.analytics_report_enhanced import generate_enhanced_pdf_report
from models.analytics import Analytics
from models.whatsapp import WhatsAppMessage
from utils.logger import (analytics_logger, log_error, log_function_call,
                          log_user_action)


@log_function_call(analytics_logger)
def analysis():
    """Advanced analytics dashboard with sentiment analysis and complaint tracking"""
    # Get user's company
    user_company = current_user.company_id or 'haval'
    
    # Get date filter parameters
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    analytics_logger.info(f"Analytics dashboard accessed by user {current_user.username} for company {user_company}")
    analytics_logger.info(f"Date filter: {date_from} to {date_to}")
    
    # Get company configuration
    from config import get_company_config
    try:
        company_config = get_company_config(user_company)
        company_name = company_config.full_name
        analytics_logger.info(f"Company config loaded: {company_name}")
    except Exception as e:
        company_name = user_company.title()
        log_error(e, f"Failed to get company config for {user_company}")
    
    try:
        # Get analytics data
        analytics_logger.info("Fetching company analytics data...")
        user_analytics = Analytics.get_company_analytics(
            current_user.id,
            user_company, 
            date_from=date_from, 
            date_to=date_to
        )
        
        analytics_logger.info("Fetching sentiment analysis...")
        sentiment_analysis = Analytics.get_sentiment_analysis(
            user_company, 
            date_from=date_from, 
            date_to=date_to
        )
        
        analytics_logger.info("Fetching complaint analysis...")
        complaint_analysis = Analytics.get_complaint_analysis(
            user_company, 
            date_from=date_from, 
            date_to=date_to
        )
        
        analytics_logger.info("Fetching WhatsApp statistics...")
        whatsapp_stats = Analytics.get_whatsapp_analytics(
            user_company, 
            date_from=date_from, 
            date_to=date_to
        )
        
        # Pipeline analytics
        try:
            analytics_logger.info("Fetching pipeline analytics...")
            from ai.haval_pipeline import (get_daily_weekly_stats,
                                           get_pipeline_status)
            pipeline_status = get_pipeline_status()
            daily_stats, weekly_stats = get_daily_weekly_stats()
            analytics_logger.info(f"Pipeline status: {pipeline_status.get('status', 'unknown')}")
        except Exception as e:
            pipeline_status = {"status": "error", "error": str(e)}
            daily_stats, weekly_stats = [], []
            log_error(e, "Failed to get pipeline analytics")

        log_user_action("Analytics Dashboard", current_user.id, 
                       f"Company: {user_company}, Date range: {date_from} to {date_to}")
        
        analytics_logger.info(f"Analytics data compiled successfully for user {current_user.username}")
        
        # Check if this is an AJAX request for JSON data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            analytics_logger.info("Returning JSON response for AJAX request")
            return jsonify({
                'success': True,
                'total_posts': user_analytics.get("total_posts", 0),
                'search_posts': user_analytics.get("search_posts", 0),
                'unique_topics': user_analytics.get("unique_topics", 0),
                'unique_authors': user_analytics.get("unique_authors", 0),
                'chatbot_usage': user_analytics.get("chatbot_usage", {}),
                'popular_queries': user_analytics.get("popular_queries", []),
                'sentiment_analysis': sentiment_analysis,
                'pakwheels_complaints': complaint_analysis.get("pakwheels", []),
                'whatsapp_complaints': complaint_analysis.get("whatsapp", []),
                'whatsapp_stats': whatsapp_stats,
                'date_from': date_from,
                'date_to': date_to,
                'filtered': bool(date_from or date_to)
            })
        
        # Return HTML template for regular requests
        return render_template(
            "analysis_pro.html",
            total_posts=user_analytics.get("total_posts", 0),
            search_posts=user_analytics.get("search_posts", 0),
            unique_topics=user_analytics.get("unique_topics", 0),
            unique_authors=user_analytics.get("unique_authors", 0),
            chatbot_usage=user_analytics.get("chatbot_usage", {}),
            popular_queries=user_analytics.get("popular_queries", []),
            sentiment_analysis=sentiment_analysis,
            pakwheels_complaints=complaint_analysis.get("pakwheels", []),
            whatsapp_complaints=complaint_analysis.get("whatsapp", []),
            pipeline_status=pipeline_status,
            daily_stats=daily_stats,
            weekly_stats=weekly_stats,
            whatsapp_stats=whatsapp_stats,
            user_company=user_company,
            company_name=company_name,
            selected_company=user_company,
            date_from=date_from,
            date_to=date_to,
        )
        
    except Exception as e:
        log_error(e, f"Error in analytics dashboard for user {current_user.username}")
        analytics_logger.error(f"Analytics dashboard error: {str(e)}")
        
        # Return JSON error for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'Analytics data unavailable'
            }), 500
        
        # Return error template for regular requests
        return render_template("error.html", error="Analytics data unavailable")


@log_function_call(analytics_logger)
def analysis_new():
    """New modern analytics dashboard with source-based filtering using real database data"""
    # Get user's company
    user_company = current_user.company_id or 'haval'

    # Get source filter parameter
    source = request.args.get('source', 'pakwheels')

    analytics_logger.info(f"New analytics dashboard accessed by user {current_user.username} for company {user_company}, source: {source}")

    # Get user permissions for data sources
    from config.config_loader import get_config
    from models.datasource_permissions import DataSourcePermissions
    from scheduler.decorators import is_admin_user
    user_permissions = DataSourcePermissions.get_user_permissions(current_user.id)
    
    config = get_config()
    is_admin = is_admin_user(current_user)

    # Get company configuration
    from config import get_company_config
    try:
        company_config = get_company_config(user_company)
        company_name = company_config.full_name
        analytics_logger.info(f"Company config loaded: {company_name}")
    except Exception as e:
        company_name = user_company.title()
        log_error(e, f"Failed to get company config for {user_company}")
    
    try:
        # Get analytics data based on source
        analytics_logger.info(f"Fetching analytics data for source: {source}")
        
        if source == 'pakwheels':
            # Get PakWheels data
            user_analytics = Analytics.get_company_analytics(current_user.id, user_company)
            sentiment_analysis = Analytics.get_sentiment_analysis(user_company)
            complaint_analysis = Analytics.get_complaint_analysis(user_company)
            pakwheels_complaints = complaint_analysis.get("pakwheels", [])
            
            # Calculate stats
            total_posts = user_analytics.get("total_posts", 0)
            unique_authors = user_analytics.get("unique_authors", 0)
            unique_topics = user_analytics.get("unique_topics", 0)
            complaints_count = len(pakwheels_complaints)
            
            # Get sentiment data for charts
            positive_posts = sentiment_analysis.get("positive", 0)
            negative_posts = sentiment_analysis.get("negative", 0)
            neutral_posts = sentiment_analysis.get("neutral", 0)
            
            # Calculate revenue (placeholder - can be enhanced)
            unique_users_total = unique_authors  # Use unique authors as unique users
            
        elif source == 'whatsapp' and user_company == 'haval':
            # Get WhatsApp data
            whatsapp_stats = Analytics.get_whatsapp_analytics(user_company)
            complaint_analysis = Analytics.get_complaint_analysis(user_company)
            whatsapp_complaints = complaint_analysis.get("whatsapp", [])
            
            # Calculate stats
            total_posts = whatsapp_stats.get("total_messages", 0)
            unique_authors = whatsapp_stats.get("unique_customers", 0)  # Use unique_customers from analytics
            unique_topics = len(whatsapp_stats.get("common_queries", []))
            complaints_count = len(whatsapp_complaints)
            
            # Get message type data for charts
            message_types = whatsapp_stats.get("message_types", {})
            positive_posts = message_types.get("query", 0) + message_types.get("general", 0)
            negative_posts = message_types.get("complaint", 0)
            neutral_posts = message_types.get("support", 0)
            
            # Calculate revenue (placeholder)
            unique_users_total = unique_authors  # Use unique customers as unique users
            
        elif source == 'reddit':
            # Get Reddit data from database
            user_analytics_reddit = Analytics.get_reddit_analytics(user_company)
            sentiment_analysis_reddit = Analytics.get_reddit_sentiment_analysis(user_company)
            complaint_analysis_reddit = Analytics.get_reddit_complaint_analysis(user_company)
            reddit_complaints = complaint_analysis_reddit.get("reddit", [])
            
            # Calculate stats
            total_posts = user_analytics_reddit.get("total_posts", 0)
            unique_authors = user_analytics_reddit.get("unique_authors", 0)
            unique_topics = user_analytics_reddit.get("unique_topics", 0)
            complaints_count = len(reddit_complaints)
            
            # Get sentiment data for charts
            positive_posts = sentiment_analysis_reddit.get("positive", 0)
            negative_posts = sentiment_analysis_reddit.get("negative", 0)
            neutral_posts = sentiment_analysis_reddit.get("neutral", 0)
            
            # Calculate revenue (placeholder - can be enhanced)
            unique_users_total = unique_authors
            
        else:
            # Default to PakWheels
            user_analytics = Analytics.get_company_analytics(current_user.id, user_company)
            sentiment_analysis = Analytics.get_sentiment_analysis(user_company)
            complaint_analysis = Analytics.get_complaint_analysis(user_company)
            pakwheels_complaints = complaint_analysis.get("pakwheels", [])
            
            total_posts = user_analytics.get("total_posts", 0)
            unique_authors = user_analytics.get("unique_authors", 0)
            unique_topics = user_analytics.get("unique_topics", 0)
            complaints_count = len(pakwheels_complaints)
            
            positive_posts = sentiment_analysis.get("positive", 0)
            negative_posts = sentiment_analysis.get("negative", 0)
            neutral_posts = sentiment_analysis.get("neutral", 0)
            unique_users_total = unique_authors

        log_user_action("New Analytics Dashboard", current_user.id, 
                       f"Company: {user_company}, Source: {source}")
        
        analytics_logger.info(f"New analytics data compiled successfully for user {current_user.username}")
        
        # Get query analysis data (all sources combined)
        most_asked_queries = Analytics.get_most_asked_queries(user_company, limit=10)
        query_topics = Analytics.get_query_topics_distribution(user_company)
        
        # Check if this is an AJAX request for JSON data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            analytics_logger.info("Returning JSON response for AJAX request")
            return jsonify({
                'success': True,
                'source': source,
                'total_posts': total_posts,
                'unique_authors': unique_authors,
                'unique_topics': unique_topics,
                'complaints_count': complaints_count,
                'positive_posts': positive_posts,
                'negative_posts': negative_posts,
                'neutral_posts': neutral_posts,
                'unique_users_total': unique_users_total,
                'most_asked_queries': most_asked_queries,
                'query_topics': query_topics
            })
        
        # Return HTML template for regular requests
        return render_template(
            "analytics_new.html",
            total_posts=total_posts,
            unique_authors=unique_authors,
            unique_topics=unique_topics,
            complaints_count=complaints_count,
            positive_posts=positive_posts,
            negative_posts=negative_posts,
            neutral_posts=neutral_posts,
            unique_users_total=unique_users_total,
            user_company=user_company,
            company_name=company_name,
            selected_company=user_company,
            source=source,
            pakwheels_complaints=complaint_analysis.get("pakwheels", []) if 'complaint_analysis' in locals() else [],
            user_permissions=user_permissions,
            config=config,
            user=current_user,
            is_admin=is_admin
        )
        
    except Exception as e:
        log_error(e, f"Error in new analytics dashboard for user {current_user.username}")
        analytics_logger.error(f"New analytics dashboard error: {str(e)}")
        
        # Return JSON error for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'Analytics data unavailable'
            }), 500
        
        # Return error template for regular requests
        return render_template("error.html", error="Analytics data unavailable")


def get_daily_token_usage(company_id):
    """Get daily token usage data for the last 30 days"""
    try:
        from models.api_usage import APIUsage
        from datetime import datetime, timedelta
        
        # Get token usage data for last 30 days
        detailed_data = APIUsage.get_detailed_usage(
            company_id=company_id,
            api_type=None,
            days=30
        )
        
        # Aggregate by date
        daily_tokens = {}
        for item in detailed_data:
            try:
                # Skip migration marker entries (they have 0 tokens)
                if item.get('operation') == 'RAG_MIGRATION' or item.get('total_tokens', 0) == 0:
                    continue
                
                timestamp = item.get('timestamp', '')
                if timestamp:
                    # Parse date from timestamp - handle both formats
                    # Format 1: "2026-02-01 06:57:35"
                    # Format 2: "2026-02-06T08:44:38.810135"
                    if 'T' in timestamp:
                        date_str = timestamp.split('T')[0]
                    else:
                        date_str = timestamp.split(' ')[0] if ' ' in timestamp else timestamp
                    
                    daily_tokens[date_str] = daily_tokens.get(date_str, 0) + item.get('total_tokens', 0)
            except:
                continue
        
        # Sort by date
        sorted_dates = sorted(daily_tokens.keys())
        
        return {
            'labels': sorted_dates,
            'data': [daily_tokens[date] for date in sorted_dates]
        }
    except Exception as e:
        analytics_logger.error(f"Failed to get daily token usage: {str(e)}")
        return {'labels': [], 'data': []}


@log_function_call(analytics_logger)
def get_analytics_by_source():
    """API endpoint to get analytics data for specific source using real database data"""
    user_company = current_user.company_id or 'haval'
    source = request.args.get('source', 'pakwheels')
    
    analytics_logger.info(f"API request for analytics data - User: {current_user.username}, Company: {user_company}, Source: {source}")
    
    try:
        # Get token usage data (daily aggregation)
        token_usage_data = get_daily_token_usage(user_company)
        
        # Calculate total tokens found
        total_tokens_found = sum(token_usage_data.get('data', []))
        
        if source == 'pakwheels':
            # Get PakWheels data from database
            user_analytics = Analytics.get_company_analytics(current_user.id, user_company)
            sentiment_analysis = Analytics.get_sentiment_analysis(user_company)
            complaint_analysis = Analytics.get_complaint_analysis(user_company)
            pakwheels_complaints = complaint_analysis.get("pakwheels", [])
            
            # Calculate real stats
            total_posts = user_analytics.get("total_posts", 0)
            unique_authors = user_analytics.get("unique_authors", 0)
            unique_topics = user_analytics.get("unique_topics", 0)
            complaints_count = len(pakwheels_complaints)
            
            # Get sentiment data
            positive_posts = sentiment_analysis.get("positive", 0)
            negative_posts = sentiment_analysis.get("negative", 0)
            neutral_posts = sentiment_analysis.get("neutral", 0)
            
            # Generate activity data
            activity_data = generate_activity_chart_data(total_posts, 'pakwheels', request.args.get('period', '7d'))
            
            # Get query analysis data (all sources combined)
            most_asked_queries = Analytics.get_most_asked_queries(user_company, limit=10)
            query_topics = Analytics.get_query_topics_distribution(user_company)
            
            return jsonify({
                'success': True,
                'source': source,
                'stats': {
                    'totalPosts': total_posts,
                    'activeUsers': unique_authors,
                    'newUsers': unique_topics,
                    'uniqueUsersTotal': unique_authors
                },
                'activityData': activity_data,
                'conversionsData': {
                    'labels': ['Positive Posts', 'Negative Posts', 'Neutral Posts'],
                    'data': [positive_posts, negative_posts, neutral_posts],
                    'colors': ['#10b981', '#ef4444', '#6b7280']
                },
                'most_asked_queries': most_asked_queries,
                'query_topics': query_topics
            })
            
        elif source == 'whatsapp':
            if user_company != 'haval':
                return jsonify({
                    'success': False,
                    'error': 'WhatsApp analytics not available for this company'
                }), 400
                
            # Get WhatsApp data from database
            whatsapp_stats = Analytics.get_whatsapp_analytics(user_company)
            complaint_analysis = Analytics.get_complaint_analysis(user_company)
            whatsapp_complaints = complaint_analysis.get("whatsapp", [])
            
            # Calculate real stats
            total_messages = whatsapp_stats.get("total_messages", 0)
            unique_customers = whatsapp_stats.get("unique_customers", 0)  # Use unique_customers from analytics
            common_queries = len(whatsapp_stats.get("common_queries", []))
            complaints_count = len(whatsapp_complaints)
            
            # Get message type data
            message_types = whatsapp_stats.get("message_types", {})
            queries = message_types.get("query", 0)
            complaints = message_types.get("complaint", 0)
            support = message_types.get("support", 0)
            general = message_types.get("general", 0)
            
            # Generate activity data
            activity_data = generate_activity_chart_data(total_messages, 'whatsapp', request.args.get('period', '7d'))
            
            # Get query analysis data (all sources combined)
            most_asked_queries = Analytics.get_most_asked_queries(user_company, limit=10)
            query_topics = Analytics.get_query_topics_distribution(user_company)
            
            return jsonify({
                'success': True,
                'source': source,
                'stats': {
                    'totalPosts': total_messages,
                    'activeUsers': unique_customers,
                    'newUsers': common_queries,
                    'uniqueUsersTotal': unique_customers
                },
                'activityData': activity_data,
                'conversionsData': {
                    'labels': ['Queries', 'Complaints', 'Support', 'General'],
                    'data': [queries, complaints, support, general],
                    'colors': ['#3b82f6', '#ef4444', '#10b981', '#f59e0b']
                },
                'most_asked_queries': most_asked_queries,
                'query_topics': query_topics
            })
            
        elif source == 'reddit':
            # Get Reddit data from database
            user_analytics = Analytics.get_reddit_analytics(user_company)
            sentiment_analysis = Analytics.get_reddit_sentiment_analysis(user_company)
            complaint_analysis = Analytics.get_reddit_complaint_analysis(user_company)
            reddit_complaints = complaint_analysis.get("reddit", [])
            
            # Calculate real stats
            total_posts = user_analytics.get("total_posts", 0)
            unique_authors = user_analytics.get("unique_authors", 0)
            unique_topics = user_analytics.get("unique_topics", 0)
            complaints_count = len(reddit_complaints)
            
            # Get sentiment data
            positive_posts = sentiment_analysis.get("positive", 0)
            negative_posts = sentiment_analysis.get("negative", 0)
            neutral_posts = sentiment_analysis.get("neutral", 0)
            
            # Generate activity data
            activity_data = generate_activity_chart_data(total_posts, 'reddit', request.args.get('period', '7d'))
            
            # Get query analysis data (all sources combined)
            most_asked_queries = Analytics.get_most_asked_queries(user_company, limit=10)
            query_topics = Analytics.get_query_topics_distribution(user_company)
            
            return jsonify({
                'success': True,
                'source': source,
                'stats': {
                    'totalPosts': total_posts,
                    'activeUsers': unique_authors,
                    'newUsers': unique_topics,
                    'uniqueUsersTotal': unique_authors
                },
                'activityData': activity_data,
                'conversionsData': {
                    'labels': ['Positive Posts', 'Negative Posts', 'Neutral Posts'],
                    'data': [positive_posts, negative_posts, neutral_posts],
                    'colors': ['#10b981', '#ef4444', '#6b7280']
                },
                'most_asked_queries': most_asked_queries,
                'query_topics': query_topics
            })
        
        else:
            return jsonify({
                'success': False,
                'error': 'Invalid source specified'
            }), 400
            
    except Exception as e:
        log_error(e, f"Error in analytics API for user {current_user.username}")
        analytics_logger.error(f"Analytics API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Analytics data unavailable'
        }), 500


def generate_activity_chart_data(total_count, source_type, time_period='7d'):
    """Generate activity chart data from actual database records - showing real posts/messages"""
    from datetime import datetime, timedelta

    from models.database import get_db_connection
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    labels = []
    data = []
    
    try:
        if source_type == 'pakwheels':
            # Fetch real daily post counts from database
            if time_period == '7d':
                # Last 7 days - daily data
                for i in range(7):
                    date = datetime.now() - timedelta(days=6-i)
                    date_str = date.strftime('%Y-%m-%d')
                    labels.append(date.strftime('%b %d'))
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE company_id = 'haval' AND DATE(created_at) = ?
                    """, (date_str,))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '1m':
                # Last 30 days - weekly aggregates
                for i in range(4):
                    week_start = datetime.now() - timedelta(weeks=3-i)
                    week_end = week_start + timedelta(days=7)
                    labels.append(f"Week {i+1}")
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE company_id = 'haval' 
                        AND DATE(created_at) >= ? AND DATE(created_at) < ?
                    """, (week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '3m':
                # Last 90 days - weekly aggregates (12 weeks)
                for i in range(12):
                    week_start = datetime.now() - timedelta(weeks=11-i)
                    week_end = week_start + timedelta(days=7)
                    labels.append(week_start.strftime('%b %d'))
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE company_id = 'haval' 
                        AND DATE(created_at) >= ? AND DATE(created_at) < ?
                    """, (week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '1y':
                # Last 12 months - monthly aggregates
                for i in range(12):
                    month_start = datetime.now() - timedelta(days=30*(11-i))
                    month_end = month_start + timedelta(days=30)
                    labels.append(month_start.strftime('%b'))
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE company_id = 'haval' 
                        AND DATE(created_at) >= ? AND DATE(created_at) < ?
                    """, (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '3y':
                # Last 36 months - quarterly aggregates (12 quarters)
                for i in range(12):
                    quarter_start = datetime.now() - timedelta(days=90*(11-i))
                    quarter_end = quarter_start + timedelta(days=90)
                    labels.append(f"Q{(i % 4) + 1} {quarter_start.strftime('%y')}")
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE company_id = 'haval' 
                        AND DATE(created_at) >= ? AND DATE(created_at) < ?
                    """, (quarter_start.strftime('%Y-%m-%d'), quarter_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
        elif source_type == 'whatsapp':
            # Fetch real daily message counts from database
            if time_period == '7d':
                # Last 7 days - daily data
                for i in range(7):
                    date = datetime.now() - timedelta(days=6-i)
                    date_str = date.strftime('%Y-%m-%d')
                    labels.append(date.strftime('%b %d'))
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM whatsapp_messages 
                        WHERE company_id = 'haval' AND DATE(timestamp) = ?
                    """, (date_str,))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '1m':
                # Last 30 days - weekly aggregates
                for i in range(4):
                    week_start = datetime.now() - timedelta(weeks=3-i)
                    week_end = week_start + timedelta(days=7)
                    labels.append(f"Week {i+1}")
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM whatsapp_messages 
                        WHERE company_id = 'haval' 
                        AND DATE(timestamp) >= ? AND DATE(timestamp) < ?
                    """, (week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '3m':
                # Last 90 days - weekly aggregates (12 weeks)
                for i in range(12):
                    week_start = datetime.now() - timedelta(weeks=11-i)
                    week_end = week_start + timedelta(days=7)
                    labels.append(week_start.strftime('%b %d'))
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM whatsapp_messages 
                        WHERE company_id = 'haval' 
                        AND DATE(timestamp) >= ? AND DATE(timestamp) < ?
                    """, (week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '1y':
                # Last 12 months - monthly aggregates
                for i in range(12):
                    month_start = datetime.now() - timedelta(days=30*(11-i))
                    month_end = month_start + timedelta(days=30)
                    labels.append(month_start.strftime('%b'))
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM whatsapp_messages 
                        WHERE company_id = 'haval' 
                        AND DATE(timestamp) >= ? AND DATE(timestamp) < ?
                    """, (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '3y':
                # Last 36 months - quarterly aggregates (12 quarters)
                for i in range(12):
                    quarter_start = datetime.now() - timedelta(days=90*(11-i))
                    quarter_end = quarter_start + timedelta(days=90)
                    labels.append(f"Q{(i % 4) + 1} {quarter_start.strftime('%y')}")
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM whatsapp_messages 
                        WHERE company_id = 'haval' 
                        AND DATE(timestamp) >= ? AND DATE(timestamp) < ?
                    """, (quarter_start.strftime('%Y-%m-%d'), quarter_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
        elif source_type == 'reddit':
            # Fetch real daily Reddit post counts from database
            if time_period == '7d':
                # Last 7 days - daily data
                for i in range(7):
                    date = datetime.now() - timedelta(days=6-i)
                    date_str = date.strftime('%Y-%m-%d')
                    labels.append(date.strftime('%b %d'))
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE company_id = 'haval' AND category LIKE '%Reddit%' AND DATE(created_at) = ?
                    """, (date_str,))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '1m':
                # Last 30 days - weekly aggregates
                for i in range(4):
                    week_start = datetime.now() - timedelta(weeks=3-i)
                    week_end = week_start + timedelta(days=7)
                    labels.append(f"Week {i+1}")
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE company_id = 'haval' AND category LIKE '%Reddit%'
                        AND DATE(created_at) >= ? AND DATE(created_at) < ?
                    """, (week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '3m':
                # Last 90 days - weekly aggregates (12 weeks)
                for i in range(12):
                    week_start = datetime.now() - timedelta(weeks=11-i)
                    week_end = week_start + timedelta(days=7)
                    labels.append(week_start.strftime('%b %d'))
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE company_id = 'haval' AND category LIKE '%Reddit%'
                        AND DATE(created_at) >= ? AND DATE(created_at) < ?
                    """, (week_start.strftime('%Y-%m-%d'), week_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '1y':
                # Last 12 months - monthly aggregates
                for i in range(12):
                    month_start = datetime.now() - timedelta(days=30*(11-i))
                    month_end = month_start + timedelta(days=30)
                    labels.append(month_start.strftime('%b'))
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE company_id = 'haval' AND category LIKE '%Reddit%'
                        AND DATE(created_at) >= ? AND DATE(created_at) < ?
                    """, (month_start.strftime('%Y-%m-%d'), month_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
                    
            elif time_period == '3y':
                # Last 36 months - quarterly aggregates (12 quarters)
                for i in range(12):
                    quarter_start = datetime.now() - timedelta(days=90*(11-i))
                    quarter_end = quarter_start + timedelta(days=90)
                    labels.append(f"Q{(i % 4) + 1} {quarter_start.strftime('%y')}")
                    
                    cur.execute("""
                        SELECT COUNT(*) FROM posts 
                        WHERE company_id = 'haval' AND category LIKE '%Reddit%'
                        AND DATE(created_at) >= ? AND DATE(created_at) < ?
                    """, (quarter_start.strftime('%Y-%m-%d'), quarter_end.strftime('%Y-%m-%d')))
                    count = cur.fetchone()[0]
                    data.append(count)
    
    except Exception as e:
        analytics_logger.error(f"Error generating activity chart data: {str(e)}")
        # Return empty data on error
        labels = []
        data = []
    
    finally:
        conn.close()
    
    return {
        'labels': labels,
        'data': data
    }


# Placeholder functions for other analytics features
@log_function_call(analytics_logger)
def generate_report():
    """Generate comprehensive analytics report"""
    # This would contain the full report generation logic
    # For now, return a simple response
    return jsonify({
        'success': True,
        'message': 'Report generation feature available in full version'
    })


@log_function_call(analytics_logger)
def generate_report_charts():
    """Generate chart images for reports"""
    # This would contain chart generation logic
    return jsonify({
        'success': True,
        'charts': {}
    })


@log_function_call(analytics_logger)
def db_summary():
    """Database summary statistics"""
    # This would contain database summary logic
    return jsonify({
        'success': True,
        'summary': 'Database summary available'
    })

@log_function_call(analytics_logger)
def get_recent_complaints():
    """API endpoint to get recent complaints for the activity table with time period filtering"""
    user_company = current_user.company_id or 'haval'
    source = request.args.get('source', 'pakwheels')
    period = request.args.get('period', None)  # None means show all time
    
    analytics_logger.info(f"API request for complaints - User: {current_user.username}, Company: {user_company}, Source: {source}, Period: {period}")
    
    try:
        from datetime import datetime, timedelta

        # Calculate date range based on period (only if period is specified)
        date_from = None
        if period:
            now = datetime.now()
            if period == '7d':
                date_from = (now - timedelta(days=7)).strftime('%Y-%m-%d')
            elif period == '1m':
                date_from = (now - timedelta(days=30)).strftime('%Y-%m-%d')
            elif period == '3m':
                date_from = (now - timedelta(days=90)).strftime('%Y-%m-%d')
            elif period == '1y':
                date_from = (now - timedelta(days=365)).strftime('%Y-%m-%d')
            elif period == '3y':
                date_from = (now - timedelta(days=1095)).strftime('%Y-%m-%d')
        
        complaint_analysis = Analytics.get_complaint_analysis(user_company)
        
        # Import keyword analyzer for severity detection
        from ai.keyword_analyzer import ComprehensiveKeywordAnalyzer
        
        if source == 'pakwheels':
            complaints = complaint_analysis.get("pakwheels", [])
            formatted_complaints = []
            
            for complaint in complaints:
                # Analyze message for severity
                text = complaint.get('text', '')
                analysis = ComprehensiveKeywordAnalyzer.analyze_message(text)
                
                formatted_complaints.append({
                    'user': complaint.get('author', 'Unknown User'),
                    'activity': 'Filed complaint',
                    'source': 'pakwheels',
                    'date': complaint.get('date', 'Unknown'),
                    'status': 'pending',
                    'message': text,
                    'contact_number': complaint.get('contact_number', 'N/A'),
                    'country_code': complaint.get('country_code', '92'),
                    'url': complaint.get('url', ''),
                    'post_number': complaint.get('post_number', ''),
                    'category': complaint.get('category', 'none'),
                    'complaint_category': complaint.get('category', 'car_complaint'),
                    'severity': analysis.get('severity', 'low')
                })
                
        elif source == 'whatsapp' and user_company == 'haval':
            complaints = complaint_analysis.get("whatsapp", [])
            formatted_complaints = []
            
            for complaint in complaints:
                # Filter by date range only if period is specified
                if date_from:
                    complaint_date_str = complaint.get('date', '')
                    try:
                        # Parse ISO format date
                        if 'T' in complaint_date_str:
                            complaint_date = datetime.fromisoformat(complaint_date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                        else:
                            complaint_date = complaint_date_str[:10]
                        
                        if complaint_date < date_from:
                            continue
                    except:
                        pass
                
                # Analyze message for severity
                text = complaint.get('message', '')
                analysis = ComprehensiveKeywordAnalyzer.analyze_message(text)
                
                formatted_complaints.append({
                    'user': complaint.get('customer', 'Unknown Customer'),
                    'activity': 'WhatsApp complaint',
                    'source': 'whatsapp',
                    'date': complaint.get('date', 'Unknown'),
                    'status': 'pending',
                    'message': text,
                    'contact_number': complaint.get('contact_number', 'N/A'),
                    'country_code': complaint.get('country_code', '92'),
                    'category': complaint.get('category', 'none'),
                    'complaint_category': complaint.get('complaint_category', 'car_complaint'),
                    'severity': analysis.get('severity', 'low')
                })
                
        elif source == 'reddit':
            reddit_complaint_analysis = Analytics.get_reddit_complaint_analysis(user_company)
            reddit_complaints = reddit_complaint_analysis.get("reddit", [])
            formatted_complaints = []
            
            for complaint in reddit_complaints:
                # Filter by date range only if period is specified
                if date_from:
                    complaint_date_str = complaint.get('date', '')
                    try:
                        # Parse date format
                        if 'T' in complaint_date_str:
                            complaint_date = datetime.fromisoformat(complaint_date_str.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                        else:
                            complaint_date = complaint_date_str[:10]
                        
                        if complaint_date < date_from:
                            continue
                    except:
                        pass
                
                # Analyze message for severity
                text = complaint.get('text', '')
                analysis = ComprehensiveKeywordAnalyzer.analyze_message(text)
                
                formatted_complaints.append({
                    'user': complaint.get('author', 'Unknown User'),
                    'activity': 'Posted complaint',
                    'source': 'reddit',
                    'date': complaint.get('date', 'Unknown'),
                    'status': 'pending',
                    'message': text,
                    'contact_number': complaint.get('contact_number', 'N/A'),
                    'country_code': complaint.get('country_code', '92'),
                    'url': complaint.get('url', ''),
                    'category': complaint.get('category', 'none'),
                    'complaint_category': complaint.get('complaint_category', 'car_complaint'),
                    'severity': analysis.get('severity', 'low')
                })
        else:
            formatted_complaints = []
            
        return jsonify({
            'success': True,
            'complaints': formatted_complaints,
            'total_count': len(formatted_complaints),
            'period': period
        })
        
    except Exception as e:
        log_error(e, f"Error fetching recent complaints for user {current_user.username}")
        analytics_logger.error(f"Recent complaints API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'complaints': []
        }), 500


@log_function_call(analytics_logger)
def get_recent_queries():
    """API endpoint to get recent queries for the activity table with time period filtering"""
    user_company = current_user.company_id or 'haval'
    source = request.args.get('source', 'whatsapp')
    period = request.args.get('period', None)  # None means show all time
    
    analytics_logger.info(f"API request for queries - User: {current_user.username}, Company: {user_company}, Source: {source}, Period: {period}")
    
    try:
        from datetime import datetime, timedelta

        from models.database import get_db_connection

        # Calculate date range based on period (only if period is specified)
        date_from = None
        if period:
            now = datetime.now()
            if period == '7d':
                date_from = (now - timedelta(days=7)).strftime('%Y-%m-%d')
            elif period == '1m':
                date_from = (now - timedelta(days=30)).strftime('%Y-%m-%d')
            elif period == '3m':
                date_from = (now - timedelta(days=90)).strftime('%Y-%m-%d')
            elif period == '1y':
                date_from = (now - timedelta(days=365)).strftime('%Y-%m-%d')
            elif period == '3y':
                date_from = (now - timedelta(days=1095)).strftime('%Y-%m-%d')
        
        formatted_queries = []
        
        if source == 'whatsapp':
            # Get WhatsApp queries from database
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Build date filter
            date_filter = ""
            date_params = [user_company]
            if date_from:
                date_filter = " AND DATE(timestamp) >= ?"
                date_params.append(date_from)
            
            try:
                # Get queries from whatsapp_messages table
                cur.execute(f"""
                    SELECT customer_name, message, timestamp, contact_number, country_code
                    FROM whatsapp_messages 
                    WHERE company_id = ? AND message_type = 'query'{date_filter}
                    ORDER BY timestamp DESC
                """, date_params)
                
                queries = cur.fetchall()
                analytics_logger.info(f"Found {len(queries)} queries for company {user_company}")
                
                for query in queries:
                    formatted_queries.append({
                        'user': query[0] or 'Unknown Customer',
                        'activity': 'WhatsApp query',
                        'source': 'whatsapp',
                        'date': query[2] or 'Unknown',
                        'status': 'pending',
                        'message': query[1] or '',
                        'contact_number': query[3] or 'N/A',
                        'country_code': query[4] or '92'
                    })
            except Exception as e:
                analytics_logger.error(f"Error fetching WhatsApp queries: {str(e)}", exc_info=True)
                formatted_queries = []
            finally:
                conn.close()
        else:
            formatted_queries = []
            
        return jsonify({
            'success': True,
            'queries': formatted_queries,
            'total_count': len(formatted_queries),
            'period': period
        })
        
    except Exception as e:
        log_error(e, f"Error fetching recent queries for user {current_user.username}")
        analytics_logger.error(f"Recent queries API error: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'queries': []
        }), 500


@log_function_call(analytics_logger)
def api_generate_report():
    """API endpoint to generate and download reports"""
    try:
        import csv
        from datetime import datetime, timedelta
        from io import BytesIO
        
        user_company = current_user.company_id or 'haval'
        source = request.args.get('source', 'pakwheels')
        report_type = request.args.get('type', 'summary')
        period = request.args.get('period', '7d')
        report_format = request.args.get('format', 'pdf')
        
        analytics_logger.info(f"Generating report - User: {current_user.username}, Source: {source}, Type: {report_type}, Period: {period}, Format: {report_format}")
        
        # Calculate date range
        date_from = None
        if period != 'all':
            now = datetime.now()
            if period == '7d':
                date_from = (now - timedelta(days=7)).strftime('%Y-%m-%d')
            elif period == '1m':
                date_from = (now - timedelta(days=30)).strftime('%Y-%m-%d')
            elif period == '3m':
                date_from = (now - timedelta(days=90)).strftime('%Y-%m-%d')
            elif period == '1y':
                date_from = (now - timedelta(days=365)).strftime('%Y-%m-%d')
        
        # Get analytics data
        analytics_response = get_analytics_by_source()
        
        # Extract JSON from response
        if hasattr(analytics_response, 'get_json'):
            response_data = analytics_response.get_json()
        elif isinstance(analytics_response, dict):
            response_data = analytics_response
        else:
            response_data = {}
        
        # Extract stats from response structure
        analytics_data = response_data.get('stats', {})
        conversions_data = response_data.get('conversionsData', {})
        
        if report_format == 'csv':
            # Generate CSV report
            output = BytesIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow(['Analytics Report', f'{source.upper()}', f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            writer.writerow([])
            writer.writerow(['Report Type', report_type])
            writer.writerow(['Time Period', period])
            writer.writerow(['Company', user_company])
            writer.writerow([])
            
            # Write summary data
            writer.writerow(['Summary Statistics'])
            writer.writerow(['Metric', 'Value'])
            
            if source == 'pakwheels':
                writer.writerow(['Total Posts', analytics_data.get('totalPosts', 0)])
                writer.writerow(['Unique Authors', analytics_data.get('activeUsers', 0)])
                writer.writerow(['Complaints', analytics_data.get('complaints', 0)])
            elif source == 'whatsapp':
                writer.writerow(['Total Messages', analytics_data.get('totalMessages', 0)])
                writer.writerow(['Unique Customers', analytics_data.get('activeUsers', 0)])
                writer.writerow(['Complaints', analytics_data.get('complaints', 0)])
                writer.writerow(['Queries', analytics_data.get('commonQueries', 0)])
            
            output.seek(0)
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'report_{source}_{report_type}_{datetime.now().strftime("%Y%m%d")}.csv'
            )
        
        elif report_format == 'excel':
            # Generate Excel report
            try:
                import openpyxl
                from openpyxl.styles import Alignment, Font, PatternFill
                
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = 'Report'
                
                # Write header
                ws['A1'] = f'Analytics Report - {source.upper()}'
                ws['A1'].font = Font(bold=True, size=14)
                ws['A2'] = f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
                
                # Write summary
                ws['A4'] = 'Summary Statistics'
                ws['A4'].font = Font(bold=True)
                
                row = 5
                ws[f'A{row}'] = 'Metric'
                ws[f'B{row}'] = 'Value'
                ws[f'A{row}'].font = Font(bold=True)
                ws[f'B{row}'].font = Font(bold=True)
                
                row += 1
                if source == 'pakwheels':
                    ws[f'A{row}'] = 'Total Posts'
                    ws[f'B{row}'] = analytics_data.get('totalPosts', 0)
                    row += 1
                    ws[f'A{row}'] = 'Unique Authors'
                    ws[f'B{row}'] = analytics_data.get('activeUsers', 0)
                    row += 1
                    ws[f'A{row}'] = 'Complaints'
                    ws[f'B{row}'] = analytics_data.get('complaints', 0)
                elif source == 'whatsapp':
                    ws[f'A{row}'] = 'Total Messages'
                    ws[f'B{row}'] = analytics_data.get('totalMessages', 0)
                    row += 1
                    ws[f'A{row}'] = 'Unique Customers'
                    ws[f'B{row}'] = analytics_data.get('activeUsers', 0)
                    row += 1
                    ws[f'A{row}'] = 'Complaints'
                    ws[f'B{row}'] = analytics_data.get('complaints', 0)
                
                # Adjust column widths
                ws.column_dimensions['A'].width = 20
                ws.column_dimensions['B'].width = 15
                
                output = BytesIO()
                wb.save(output)
                output.seek(0)
                
                return send_file(
                    output,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=f'report_{source}_{report_type}_{datetime.now().strftime("%Y%m%d")}.xlsx'
                )
            except ImportError:
                return jsonify({
                    'success': False,
                    'error': 'Excel export requires openpyxl library'
                }), 400
        
        else:  # PDF format
            try:
                # Get token usage stats for the period
                from models.api_usage import APIUsage
                
                days_back = 30  # Default
                if period == '7d':
                    days_back = 7
                elif period == '1m':
                    days_back = 30
                elif period == '3m':
                    days_back = 90
                elif period == '1y':
                    days_back = 365
                
                # Get usage stats for the company
                token_stats = APIUsage.get_usage_stats(company_id=user_company, days=days_back)
                
                # Calculate totals
                total_tokens = sum(stat.get('total_tokens', 0) for stat in token_stats)
                total_cost = sum(stat.get('total_cost', 0) for stat in token_stats)
                total_requests = sum(stat.get('request_count', 0) for stat in token_stats)
                total_input = sum(stat.get('total_input_tokens', 0) for stat in token_stats)
                total_output = sum(stat.get('total_output_tokens', 0) for stat in token_stats)
                avg_tokens = total_tokens / max(total_requests, 1)
                
                token_stats_summary = {
                    'total_tokens': total_tokens,
                    'total_input_tokens': total_input,
                    'total_output_tokens': total_output,
                    'total_cost': total_cost,
                    'request_count': total_requests,
                    'avg_tokens_per_request': avg_tokens,
                    'by_api_type': token_stats
                }
                
                # Use enhanced PDF report generation
                pdf_output = generate_enhanced_pdf_report(
                    source=source,
                    report_type=report_type,
                    period=period,
                    analytics_data=analytics_data,
                    conversions_data=conversions_data,
                    user_company=user_company,
                    token_stats=token_stats_summary
                )
                
                return send_file(
                    pdf_output,
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f'report_{source}_{report_type}_{datetime.now().strftime("%Y%m%d")}.pdf'
                )
            except ImportError:
                return jsonify({
                    'success': False,
                    'error': 'PDF export requires reportlab library. Please install it: pip install reportlab'
                }), 400
            except Exception as e:
                analytics_logger.error(f"PDF generation error: {str(e)}", exc_info=True)
                return jsonify({
                    'success': False,
                    'error': f'Error generating PDF: {str(e)}'
                }), 500
        
    except Exception as e:
        log_error(e, f"Error generating report for user {current_user.username}")
        analytics_logger.error(f"Report generation error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@log_function_call(analytics_logger)
@login_required
def get_pakwheels_conversation(author):
    """Get all posts by a specific PakWheels author"""
    try:
        user_company = current_user.company_id or 'haval'
        
        # Decode author name from URL
        import urllib.parse
        decoded_author = urllib.parse.unquote(author)
        
        analytics_logger.info(f"Fetching PakWheels posts for author: {decoded_author}")
        
        from models.post import Post

        # Get all posts by this author for the company
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, topic_title, topic_url, post_number, author, created_at, cooked_text
            FROM posts 
            WHERE author = ? AND company_id = ?
            ORDER BY created_at ASC
        """, (decoded_author, user_company))
        
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            posts.append({
                'id': row[0],
                'topic_title': row[1],
                'topic_url': row[2],
                'post_number': row[3],
                'author': row[4],
                'created_at': row[5],
                'text': row[6]
            })
        
        analytics_logger.info(f"Found {len(posts)} posts for author {decoded_author}")
        
        return jsonify({
            'success': True,
            'author': decoded_author,
            'posts': posts,
            'count': len(posts)
        })
        
    except Exception as e:
        log_error(e, f"Error fetching PakWheels conversation for author {author}")
        return jsonify({
            'success': False,
            'error': str(e)[:100]
        }), 500


@log_function_call(analytics_logger)
@login_required
def get_whatsapp_conversation(customer_name):
    """Get all messages for a specific WhatsApp customer"""
    try:
        user_company = current_user.company_id or 'haval'
        
        # Only Haval users can access WhatsApp data
        if user_company != 'haval':
            return jsonify({
                'success': False,
                'error': 'WhatsApp access restricted'
            }), 403
        
        # Decode customer name from URL
        import urllib.parse
        decoded_customer = urllib.parse.unquote(customer_name)
        
        analytics_logger.info(f"Fetching WhatsApp messages for customer: {decoded_customer}")
        
        from models.whatsapp import WhatsAppMessage

        # Get all messages for this customer
        messages = WhatsAppMessage.get_messages_by_customer(decoded_customer, user_company)
        
        message_list = []
        for msg in messages:
            message_list.append({
                'id': msg.id,
                'customer_name': msg.customer_name,
                'contact_number': msg.contact_number,
                'message_type': msg.message_type,
                'message': msg.message,
                'timestamp': msg.timestamp,
                'sender': msg.sender
            })
        
        analytics_logger.info(f"Found {len(message_list)} messages for customer {decoded_customer}")
        
        return jsonify({
            'success': True,
            'customer_name': decoded_customer,
            'messages': message_list,
            'count': len(message_list)
        })
        
    except Exception as e:
        log_error(e, f"Error fetching WhatsApp conversation for customer {customer_name}")
        return jsonify({
            'success': False,
            'error': str(e)[:100]
        }), 500


def get_db_connection():
    """Import and return database connection"""
    from models.database import get_db_connection as db_conn
    return db_conn()


@log_function_call(analytics_logger)
@login_required
def view_pakwheels_conversation(author):
    """View all posts by a specific PakWheels author in a conversation-like view"""
    try:
        user_company = current_user.company_id or 'haval'
        
        # Decode author name from URL
        import urllib.parse
        decoded_author = urllib.parse.unquote(author)
        
        analytics_logger.info(f"Viewing PakWheels conversation for author: {decoded_author}")
        
        from models.post import Post

        # Get all posts by this author for the company
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, topic_title, topic_url, post_number, author, created_at, cooked_text
            FROM posts 
            WHERE author = ? AND company_id = ?
            ORDER BY created_at ASC
        """, (decoded_author, user_company))
        
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        seen_texts = set()
        
        for row in rows:
            text = row[6]
            text_lower = text.lower().strip() if text else ""
            
            # Skip if duplicate (exact match or very similar)
            if text_lower in seen_texts:
                continue
            
            # Check for near-duplicates (80% similarity)
            is_duplicate = False
            for seen_text in seen_texts:
                if len(text_lower) > 20 and len(seen_text) > 20:
                    # Simple similarity check
                    common_chars = sum(1 for a, b in zip(text_lower, seen_text) if a == b)
                    similarity = common_chars / max(len(text_lower), len(seen_text))
                    if similarity > 0.8:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                seen_texts.add(text_lower)
                posts.append({
                    'id': row[0],
                    'topic_title': row[1],
                    'topic_url': row[2],
                    'post_number': row[3],
                    'author': row[4],
                    'created_at': row[5],
                    'text': row[6]
                })
        
        analytics_logger.info(f"Found {len(posts)} unique posts for author {decoded_author} (filtered duplicates)")
        
        return render_template(
            'view_pakwheels_conversation.html',
            author=decoded_author,
            posts=posts,
            post_count=len(posts),
            user_company=user_company
        )
        
    except Exception as e:
        log_error(e, f"Error viewing PakWheels conversation for author {author}")
        return render_template("error.html", error="Failed to load conversation")


@log_function_call(analytics_logger)
@login_required
def get_reddit_conversation(author):
    """Get all posts by a specific Reddit author"""
    try:
        user_company = current_user.company_id or 'haval'
        
        # Decode author name from URL
        import urllib.parse
        decoded_author = urllib.parse.unquote(author)
        
        analytics_logger.info(f"Fetching Reddit posts for author: {decoded_author}")
        
        # Get all posts by this author for the company
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, topic_title, topic_url, post_number, author, created_at, cooked_text
            FROM posts 
            WHERE author = ? AND company_id = ? AND category LIKE '%Reddit%'
            ORDER BY created_at ASC
        """, (decoded_author, user_company))
        
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        for row in rows:
            posts.append({
                'id': row[0],
                'topic_title': row[1],
                'topic_url': row[2],
                'post_number': row[3],
                'author': row[4],
                'created_at': row[5],
                'text': row[6]
            })
        
        analytics_logger.info(f"Found {len(posts)} Reddit posts for author {decoded_author}")
        
        return jsonify({
            'success': True,
            'author': decoded_author,
            'posts': posts,
            'count': len(posts)
        })
        
    except Exception as e:
        log_error(e, f"Error fetching Reddit conversation for author {author}")
        return jsonify({
            'success': False,
            'error': str(e)[:100]
        }), 500


@log_function_call(analytics_logger)
@login_required
def view_reddit_conversation(author):
    """View all posts by a specific Reddit author in a conversation-like view"""
    try:
        user_company = current_user.company_id or 'haval'
        
        # Decode author name from URL
        import urllib.parse
        decoded_author = urllib.parse.unquote(author)
        
        analytics_logger.info(f"Viewing Reddit conversation for author: {decoded_author}")
        
        # Get all posts by this author for the company
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id, topic_title, topic_url, post_number, author, created_at, cooked_text
            FROM posts 
            WHERE author = ? AND company_id = ? AND category LIKE '%Reddit%'
            ORDER BY created_at ASC
        """, (decoded_author, user_company))
        
        rows = cur.fetchall()
        conn.close()
        
        posts = []
        seen_texts = set()
        
        for row in rows:
            text = row[6]
            text_lower = text.lower().strip() if text else ""
            
            # Skip if duplicate (exact match)
            if text_lower in seen_texts:
                continue
            
            # Check for near-duplicates (80% similarity)
            is_duplicate = False
            for seen_text in seen_texts:
                if len(text_lower) > 20 and len(seen_text) > 20:
                    # Simple similarity check
                    common_chars = sum(1 for a, b in zip(text_lower, seen_text) if a == b)
                    similarity = common_chars / max(len(text_lower), len(seen_text))
                    if similarity > 0.8:
                        is_duplicate = True
                        break
            
            if not is_duplicate:
                seen_texts.add(text_lower)
                posts.append({
                    'id': row[0],
                    'topic_title': row[1],
                    'topic_url': row[2],
                    'post_number': row[3],
                    'author': row[4],
                    'created_at': row[5],
                    'text': row[6]
                })
        
        analytics_logger.info(f"Found {len(posts)} unique Reddit posts for author {decoded_author} (filtered duplicates)")
        
        return render_template(
            'view_reddit_conversation.html',
            author=decoded_author,
            posts=posts,
            post_count=len(posts),
            user_company=user_company
        )
        
    except Exception as e:
        log_error(e, f"Error viewing Reddit conversation for author {author}")
        return render_template("error.html", error="Failed to load conversation")



@log_function_call(analytics_logger)
@login_required
def view_all_complaints():
    """View all complaints across all sources in a dedicated page with comprehensive keyword analysis"""
    try:
        user_company = current_user.company_id or 'haval'
        
        analytics_logger.info(f"Viewing all complaints for company: {user_company}")
        
        # Get company configuration
        from config import get_company_config
        try:
            company_config = get_company_config(user_company)
            company_name = company_config.full_name
        except Exception as e:
            company_name = user_company.title()
            log_error(e, f"Failed to get company config for {user_company}")
        
        # Get all complaints from all sources
        complaint_analysis = Analytics.get_complaint_analysis(user_company)
        reddit_complaint_analysis = Analytics.get_reddit_complaint_analysis(user_company)
        
        pakwheels_complaints = complaint_analysis.get("pakwheels", [])
        whatsapp_complaints = complaint_analysis.get("whatsapp", [])
        reddit_complaints = reddit_complaint_analysis.get("reddit", [])
        
        # Import comprehensive keyword analyzer
        from ai.keyword_analyzer import ComprehensiveKeywordAnalyzer

        # Combine all complaints with source information and keyword analysis
        all_complaints = []
        
        for complaint in pakwheels_complaints:
            complaint['source'] = 'PakWheels'
            # Analyze keywords in complaint text
            text = complaint.get('text', '')
            analysis = ComprehensiveKeywordAnalyzer.analyze_message(text)
            complaint['keyword_analysis'] = analysis
            complaint['matched_keywords'] = analysis.get('matched_keywords', [])
            complaint['severity'] = analysis.get('severity', 'low')
            complaint['car_models_mentioned'] = analysis.get('car_models', [])
            all_complaints.append(complaint)
        
        for complaint in whatsapp_complaints:
            complaint['source'] = 'WhatsApp'
            # Analyze keywords in WhatsApp message
            text = complaint.get('message', '')
            analysis = ComprehensiveKeywordAnalyzer.analyze_message(text)
            complaint['keyword_analysis'] = analysis
            complaint['matched_keywords'] = analysis.get('matched_keywords', [])
            complaint['severity'] = analysis.get('severity', 'low')
            complaint['car_models_mentioned'] = analysis.get('car_models', [])
            all_complaints.append(complaint)
        
        for complaint in reddit_complaints:
            complaint['source'] = 'Reddit'
            # Analyze keywords in Reddit post
            text = complaint.get('text', '')
            analysis = ComprehensiveKeywordAnalyzer.analyze_message(text)
            complaint['keyword_analysis'] = analysis
            complaint['matched_keywords'] = analysis.get('matched_keywords', [])
            complaint['severity'] = analysis.get('severity', 'low')
            complaint['car_models_mentioned'] = analysis.get('car_models', [])
            all_complaints.append(complaint)
        
        # Sort by date (newest first)
        all_complaints.sort(key=lambda x: x.get('created_at', x.get('timestamp', x.get('date', ''))), reverse=True)
        
        analytics_logger.info(f"Found {len(all_complaints)} total complaints ({len(pakwheels_complaints)} PakWheels, {len(whatsapp_complaints)} WhatsApp, {len(reddit_complaints)} Reddit)")
        
        return render_template(
            'view_all_complaints.html',
            complaints=all_complaints,
            total_complaints=len(all_complaints),
            pakwheels_count=len(pakwheels_complaints),
            whatsapp_count=len(whatsapp_complaints),
            reddit_count=len(reddit_complaints),
            user_company=user_company,
            company_name=company_name,
            selected_company=user_company
        )
        
    except Exception as e:
        log_error(e, f"Error viewing all complaints for user {current_user.username}")
        return render_template("error.html", error="Failed to load complaints")


@log_function_call(analytics_logger)
@login_required
def lucid_analytics():
    """Lucid Forum analytics dashboard - Only for Lucid users"""
    import sqlite3
    
    # Get user's company
    user_company = current_user.company_id or 'haval'
    
    # Check if user is Lucid user
    if user_company != 'lucid':
        analytics_logger.warning(f"Lucid analytics access denied for user {current_user.username} (company: {user_company})")
        log_user_action("Lucid Analytics Access Denied", current_user.id, f"Company: {user_company}")
        return render_template("access_denied.html", 
                             message="Lucid Analytics Access Restricted",
                             description="Lucid Forum analytics is only available for Lucid users.",
                             redirect_url=url_for('chatbot_advanced'),
                             redirect_text="Go to Chatbot")
    
    analytics_logger.info(f"Lucid analytics dashboard accessed by user {current_user.username}")
    
    # Get user permissions for data sources
    from config.config_loader import get_config
    from models.datasource_permissions import DataSourcePermissions
    from scheduler.decorators import is_admin_user
    from flask import url_for
    
    user_permissions = DataSourcePermissions.get_user_permissions(current_user.id)
    config = get_config()
    is_admin = is_admin_user(current_user)
    
    # Get company configuration
    from config import get_company_config
    try:
        company_config = get_company_config(user_company)
        company_name = company_config.full_name
        analytics_logger.info(f"Company config loaded: {company_name}")
    except Exception as e:
        company_name = "LUCID Enterprise AI"
        log_error(e, f"Failed to get company config for {user_company}")
    
    # Get data source from request parameter
    data_source = request.args.get('source', 'lucid_forum')
    
    try:
        # Connect to posts.db and get data
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'posts.db')
        
        total_posts = 0
        unique_authors = 0
        unique_topics = 0
        total_comments = 0
        positive_posts = 0
        negative_posts = 0
        neutral_posts = 0
        
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            if data_source == 'reddit_lucid':
                # Get Reddit Lucid data from reddit_lucid_posts table
                cur.execute("SELECT COUNT(*) as count FROM reddit_lucid_posts")
                result = cur.fetchone()
                total_posts = result['count'] if result else 0
                
                # Get unique authors
                cur.execute("SELECT COUNT(DISTINCT author) as count FROM reddit_lucid_posts")
                result = cur.fetchone()
                unique_authors = result['count'] if result else 0
                
                # Get unique subreddits (topics)
                cur.execute("SELECT COUNT(DISTINCT subreddit) as count FROM reddit_lucid_posts")
                result = cur.fetchone()
                unique_topics = result['count'] if result else 0
                
                # Get total comments
                cur.execute("SELECT SUM(num_comments) as total FROM reddit_lucid_posts")
                result = cur.fetchone()
                total_comments = result['total'] if result and result['total'] else 0
                
                # Get sentiment analysis (if sentiment column exists, otherwise use defaults)
                try:
                    cur.execute("""
                        SELECT 
                            SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) as positive,
                            SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative,
                            SUM(CASE WHEN sentiment = 'neutral' THEN 1 ELSE 0 END) as neutral
                        FROM reddit_lucid_posts
                    """)
                    result = cur.fetchone()
                    if result:
                        positive_posts = result['positive'] or 0
                        negative_posts = result['negative'] or 0
                        neutral_posts = result['neutral'] or 0
                except sqlite3.OperationalError:
                    # Sentiment column doesn't exist, use default distribution based on score
                    # Assume posts with score > 5 are positive, < -5 are negative, rest are neutral
                    cur.execute("""
                        SELECT 
                            SUM(CASE WHEN score > 5 THEN 1 ELSE 0 END) as positive,
                            SUM(CASE WHEN score < -5 THEN 1 ELSE 0 END) as negative,
                            SUM(CASE WHEN score BETWEEN -5 AND 5 THEN 1 ELSE 0 END) as neutral
                        FROM reddit_lucid_posts
                    """)
                    result = cur.fetchone()
                    if result:
                        positive_posts = result['positive'] or 0
                        negative_posts = result['negative'] or 0
                        neutral_posts = result['neutral'] or 0
            else:
                # Get Lucid Forum data from lucid_posts table (default)
                cur.execute("SELECT COUNT(*) as count FROM lucid_posts")
                result = cur.fetchone()
                total_posts = result['count'] if result else 0
                
                # Get unique authors
                cur.execute("SELECT COUNT(DISTINCT author) as count FROM lucid_posts")
                result = cur.fetchone()
                unique_authors = result['count'] if result else 0
                
                # Get unique topics (threads)
                cur.execute("SELECT COUNT(DISTINCT thread_url) as count FROM lucid_posts")
                result = cur.fetchone()
                unique_topics = result['count'] if result else 0
                
                # Estimate comments (assume average 2 comments per post)
                total_comments = total_posts * 2
                
                # Get sentiment analysis (if sentiment column exists, otherwise use defaults)
                try:
                    cur.execute("""
                        SELECT 
                            SUM(CASE WHEN sentiment = 'positive' THEN 1 ELSE 0 END) as positive,
                            SUM(CASE WHEN sentiment = 'negative' THEN 1 ELSE 0 END) as negative,
                            SUM(CASE WHEN sentiment = 'neutral' THEN 1 ELSE 0 END) as neutral
                        FROM lucid_posts
                    """)
                    result = cur.fetchone()
                    if result:
                        positive_posts = result['positive'] or 0
                        negative_posts = result['negative'] or 0
                        neutral_posts = result['neutral'] or 0
                except sqlite3.OperationalError:
                    # Sentiment column doesn't exist, use default distribution
                    # Assume 60% positive, 20% negative, 20% neutral
                    positive_posts = int(total_posts * 0.6)
                    negative_posts = int(total_posts * 0.2)
                    neutral_posts = total_posts - positive_posts - negative_posts
            
            conn.close()
        
        unique_users_total = unique_authors
        complaints_count = negative_posts
        
        log_user_action("Lucid Analytics Dashboard", current_user.id, 
                       f"Company: {user_company}, Source: {data_source}, Posts: {total_posts}")
        
        analytics_logger.info(f"Lucid analytics data compiled successfully for user {current_user.username} (source: {data_source})")
        
        # Check if this is an AJAX request for JSON data
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            analytics_logger.info("Returning JSON response for AJAX request")
            return jsonify({
                'success': True,
                'source': data_source,
                'total_posts': total_posts,
                'unique_authors': unique_authors,
                'unique_topics': unique_topics,
                'complaints_count': complaints_count,
                'positive_posts': positive_posts,
                'negative_posts': negative_posts,
                'neutral_posts': neutral_posts,
                'unique_users_total': unique_users_total,
                'total_comments': total_comments
            })
        
        # Return HTML template for regular requests (only for lucid_forum)
        return render_template(
            "lucid_analytics.html",
            total_posts=total_posts,
            unique_authors=unique_authors,
            unique_topics=unique_topics,
            complaints_count=complaints_count,
            positive_posts=positive_posts,
            negative_posts=negative_posts,
            neutral_posts=neutral_posts,
            unique_users_total=unique_users_total,
            user_company=user_company,
            company_name=company_name,
            selected_company=user_company,
            user_permissions=user_permissions,
            config=config,
            user=current_user,
            is_admin=is_admin,
            total_comments=total_comments
        )
        
    except Exception as e:
        log_error(e, f"Error in Lucid analytics dashboard for user {current_user.username}")
        analytics_logger.error(f"Lucid analytics dashboard error: {str(e)}")
        
        # Return JSON error for AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'error': str(e),
                'message': 'Lucid analytics data unavailable'
            }), 500
        
        # Return error template for regular requests
        return render_template("error.html", error="Lucid analytics data unavailable")
