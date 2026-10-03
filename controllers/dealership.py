"""
Dealership Management Controller
Handles all dealership-related routes and business logic
"""

from flask import render_template, request, jsonify, flash, redirect, url_for
from flask_login import login_required, current_user
from models.dealership import (
    DealershipDatabase, WarrantyClaim, CampaignService, 
    InspectionService, RepairOrder
)
from utils.logger import dealership_logger, log_function_call
from datetime import datetime, timedelta
import json
import csv
import io
import sqlite3
from typing import Dict, List, Any

@log_function_call(dealership_logger)
def dealership_dashboard():
    """Main dealership dashboard"""
    try:
        # Get company information
        from config import get_company_config
        company_config = get_company_config(current_user.company_id)
        company_name = company_config.name
        
        # Get summary statistics from database
        db = DealershipDatabase(company_id=current_user.company_id)
        
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            
            # Get total warranty claims
            cursor.execute("SELECT COUNT(*) FROM warranty_claims")
            total_warranty_claims = cursor.fetchone()[0]
            
            # Get total active campaigns
            cursor.execute("SELECT COUNT(DISTINCT campaign_id) FROM campaign_services")
            total_campaigns = cursor.fetchone()[0]
            
            # Get total PDI inspections
            cursor.execute("SELECT COUNT(*) FROM pdi_inspections")
            total_pdis = cursor.fetchone()[0]
            
            # Get total repair orders
            cursor.execute("SELECT COUNT(*) FROM repair_orders")
            total_ros = cursor.fetchone()[0]
            
            # Get recent warranty claims for activity feed
            cursor.execute("""
                SELECT vin_number, dealership_name, problem_description, claim_date
                FROM warranty_claims 
                ORDER BY claim_date DESC 
                LIMIT 5
            """)
            recent_claims = [dict(zip(['vin_number', 'dealership_name', 'problem_description', 'claim_date'], row)) 
                           for row in cursor.fetchall()]
            
            # Get top dealerships by activity
            cursor.execute("""
                SELECT dealership_name, COUNT(*) as activity_count
                FROM (
                    SELECT dealership_name FROM warranty_claims
                    UNION ALL
                    SELECT dealership_name FROM pdi_inspections
                    UNION ALL
                    SELECT dealership_name FROM repair_orders
                ) combined
                GROUP BY dealership_name
                ORDER BY activity_count DESC
                LIMIT 5
            """)
            top_dealerships = [dict(zip(['dealership_name', 'activity_count'], row)) 
                             for row in cursor.fetchall()]
        
        summary_stats = {
            'total_warranty_claims': total_warranty_claims,
            'total_campaigns': total_campaigns,
            'total_pdis': total_pdis,
            'total_ros': total_ros,
            'recent_claims': recent_claims,
            'top_dealerships': top_dealerships
        }
        
        dealership_logger.info(f"User {current_user.username} accessed dealership dashboard for {company_name}")
        dealership_logger.info(f"Dashboard stats: Warranty Claims: {total_warranty_claims}, Campaigns: {total_campaigns}, PDIs: {total_pdis}, ROs: {total_ros}")
        
        return render_template(
            'dealership/dashboard.html',
            stats=summary_stats,
            user=current_user,
            company_name=company_name,
            company_config=company_config
        )
        
    except Exception as e:
        dealership_logger.error(f"Error loading dealership dashboard: {str(e)}")
        flash('Error loading dashboard data', 'error')
        return render_template('dealership/dashboard.html', stats={}, user=current_user, 
                             company_name=current_user.company_id.title(), company_config=None)

@log_function_call(dealership_logger)
def warranty_claims():
    """Warranty claims management page"""
    try:
        # Get company information
        from config import get_company_config
        company_config = get_company_config(current_user.company_id)
        company_name = company_config.name
        
        # Get filter parameters
        vin_filter = request.args.get('vin', '')
        dealership_filter = request.args.get('dealership', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        claim_type = request.args.get('claim_type', '')
        
        # Get warranty claims data
        claims_data = []
        
        if vin_filter:
            claims_data = WarrantyClaim.get_claims_by_vin(vin_filter, company_id=current_user.company_id)
        else:
            # Get all warranty claims with filters
            db = DealershipDatabase(company_id=current_user.company_id)
            with sqlite3.connect(db.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                query = """
                    SELECT * FROM warranty_claims 
                    WHERE 1=1
                """
                params = []
                
                if dealership_filter:
                    query += " AND dealership_name = ?"
                    params.append(dealership_filter)
                
                if date_from:
                    query += " AND claim_date >= ?"
                    params.append(date_from)
                    
                if date_to:
                    query += " AND claim_date <= ?"
                    params.append(date_to)
                
                if claim_type:
                    query += " AND claim_type = ?"
                    params.append(claim_type)
                
                query += " ORDER BY claim_date DESC"
                
                cursor.execute(query, params)
                claims_data = [dict(row) for row in cursor.fetchall()]
        
        # Debug logging
        dealership_logger.info(f"Found {len(claims_data)} warranty claims for {company_name}")
        if claims_data:
            dealership_logger.info(f"Sample claim data: {claims_data[0]}")
        
        # Get most complained VINs
        top_complained_vins = WarrantyClaim.get_most_complained_vins(10, company_id=current_user.company_id)
        dealership_logger.info(f"Found {len(top_complained_vins)} top complained VINs")
        
        return render_template(
            'dealership/warranty_claims.html',
            claims=claims_data,
            top_vins=top_complained_vins,
            filters={
                'vin': vin_filter,
                'dealership': dealership_filter,
                'date_from': date_from,
                'date_to': date_to,
                'claim_type': claim_type
            },
            user=current_user,
            company_name=company_name,
            company_config=company_config
        )
        
    except Exception as e:
        dealership_logger.error(f"Error loading warranty claims: {str(e)}")
        flash('Error loading warranty claims data', 'error')
        return render_template('dealership/warranty_claims.html', claims=[], user=current_user,
                             company_name=current_user.company_id.title(), company_config=None)

@log_function_call(dealership_logger)
def campaign_reports():
    """Campaign reports management page"""
    try:
        # Get company information
        from config import get_company_config
        company_config = get_company_config(current_user.company_id)
        company_name = company_config.name
        
        # Get filter parameters
        campaign_filter = request.args.get('campaign', '')
        dealership_filter = request.args.get('dealership', '')
        
        # Get campaign statistics
        db = DealershipDatabase(company_id=current_user.company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get all campaigns with service counts
            query = """
                SELECT c.campaign_id, c.campaign_name, c.campaign_type, 
                       c.start_date, c.end_date, c.description,
                       COUNT(cs.id) as services_count,
                       COUNT(DISTINCT cs.dealership_name) as dealerships_count,
                       COUNT(DISTINCT cs.vin_number) as vehicles_count
                FROM campaigns c
                LEFT JOIN campaign_services cs ON c.campaign_id = cs.campaign_id
                WHERE 1=1
            """
            params = []
            
            if campaign_filter:
                query += " AND c.campaign_id = ?"
                params.append(campaign_filter)
                
            if dealership_filter:
                query += " AND cs.dealership_name = ?"
                params.append(dealership_filter)
            
            query += " GROUP BY c.campaign_id ORDER BY c.start_date DESC"
            
            cursor.execute(query, params)
            campaign_stats = [dict(row) for row in cursor.fetchall()]
            
            # Get campaign services details
            services_query = """
                SELECT cs.*, c.campaign_name, c.campaign_type
                FROM campaign_services cs
                JOIN campaigns c ON cs.campaign_id = c.campaign_id
                WHERE 1=1
            """
            services_params = []
            
            if campaign_filter:
                services_query += " AND cs.campaign_id = ?"
                services_params.append(campaign_filter)
                
            if dealership_filter:
                services_query += " AND cs.dealership_name = ?"
                services_params.append(dealership_filter)
            
            services_query += " ORDER BY cs.service_date DESC LIMIT 100"
            
            cursor.execute(services_query, services_params)
            campaign_services = [dict(row) for row in cursor.fetchall()]
            
            # Get available campaigns for filter
            cursor.execute("SELECT DISTINCT campaign_id, campaign_name FROM campaigns ORDER BY campaign_name")
            available_campaigns = [dict(row) for row in cursor.fetchall()]
        
        dealership_logger.info(f"Found {len(campaign_stats)} campaigns and {len(campaign_services)} services for {company_name}")
        
        return render_template(
            'dealership/campaign_reports.html',
            campaigns=campaign_stats,
            services=campaign_services,
            available_campaigns=available_campaigns,
            filters={
                'campaign': campaign_filter,
                'dealership': dealership_filter
            },
            user=current_user,
            company_name=company_name,
            company_config=company_config
        )
        
    except Exception as e:
        dealership_logger.error(f"Error loading campaign reports: {str(e)}")
        flash('Error loading campaign reports data', 'error')
        return render_template('dealership/campaign_reports.html', campaigns=[], services=[], user=current_user,
                             company_name=current_user.company_id.title(), company_config=None)

@log_function_call(dealership_logger)
def ffs_inspections():
    """FFS inspections management page"""
    try:
        # Get company information
        from config import get_company_config
        company_config = get_company_config(current_user.company_id)
        company_name = company_config.name
        
        # Get filter parameters
        vin_filter = request.args.get('vin', '')
        dealership_filter = request.args.get('dealership', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # Get FFS inspection data
        db = DealershipDatabase(company_id=current_user.company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM ffs_inspections 
                WHERE 1=1
            """
            params = []
            
            if vin_filter:
                query += " AND vin_number = ?"
                params.append(vin_filter)
                
            if dealership_filter:
                query += " AND dealership_name = ?"
                params.append(dealership_filter)
            
            if date_from:
                query += " AND inspection_date >= ?"
                params.append(date_from)
                
            if date_to:
                query += " AND inspection_date <= ?"
                params.append(date_to)
            
            query += " ORDER BY inspection_date DESC"
            
            cursor.execute(query, params)
            inspections = [dict(row) for row in cursor.fetchall()]
            
            # Get summary statistics
            cursor.execute("SELECT COUNT(*) as total FROM ffs_inspections")
            total_inspections = cursor.fetchone()['total']
            
            cursor.execute("""
                SELECT dealership_name, COUNT(*) as count 
                FROM ffs_inspections 
                GROUP BY dealership_name 
                ORDER BY count DESC 
                LIMIT 5
            """)
            top_dealerships = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("""
                SELECT AVG(cost) as avg_cost 
                FROM ffs_inspections 
                WHERE cost > 0
            """)
            avg_cost = cursor.fetchone()['avg_cost'] or 0
        
        summary_stats = {
            'total_inspections': total_inspections,
            'avg_cost': avg_cost,
            'top_dealerships': top_dealerships
        }
        
        dealership_logger.info(f"Found {len(inspections)} FFS inspections for {company_name}")
        
        return render_template(
            'dealership/ffs_inspections.html',
            inspections=inspections,
            stats=summary_stats,
            filters={
                'vin': vin_filter,
                'dealership': dealership_filter,
                'date_from': date_from,
                'date_to': date_to
            },
            user=current_user,
            company_name=company_name,
            company_config=company_config
        )
        
    except Exception as e:
        dealership_logger.error(f"Error loading FFS inspections: {str(e)}")
        flash('Error loading FFS inspections data', 'error')
        return render_template('dealership/ffs_inspections.html', inspections=[], stats={}, user=current_user,
                             company_name=current_user.company_id.title(), company_config=None)

@log_function_call(dealership_logger)
def sfs_inspections():
    """SFS inspections management page"""
    try:
        # Get company information
        from config import get_company_config
        company_config = get_company_config(current_user.company_id)
        company_name = company_config.name
        
        # Get filter parameters
        vin_filter = request.args.get('vin', '')
        dealership_filter = request.args.get('dealership', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # Get SFS inspection data
        db = DealershipDatabase(company_id=current_user.company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM sfs_inspections 
                WHERE 1=1
            """
            params = []
            
            if vin_filter:
                query += " AND vin_number = ?"
                params.append(vin_filter)
                
            if dealership_filter:
                query += " AND dealership_name = ?"
                params.append(dealership_filter)
            
            if date_from:
                query += " AND inspection_date >= ?"
                params.append(date_from)
                
            if date_to:
                query += " AND inspection_date <= ?"
                params.append(date_to)
            
            query += " ORDER BY inspection_date DESC"
            
            cursor.execute(query, params)
            inspections = [dict(row) for row in cursor.fetchall()]
            
            # Get summary statistics
            cursor.execute("SELECT COUNT(*) as total FROM sfs_inspections")
            total_inspections = cursor.fetchone()['total']
            
            cursor.execute("""
                SELECT dealership_name, COUNT(*) as count 
                FROM sfs_inspections 
                GROUP BY dealership_name 
                ORDER BY count DESC 
                LIMIT 5
            """)
            top_dealerships = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("""
                SELECT AVG(cost) as avg_cost 
                FROM sfs_inspections 
                WHERE cost > 0
            """)
            avg_cost = cursor.fetchone()['avg_cost'] or 0
            
            cursor.execute("""
                SELECT AVG(odometer_reading) as avg_mileage 
                FROM sfs_inspections 
                WHERE odometer_reading > 0
            """)
            avg_mileage = cursor.fetchone()['avg_mileage'] or 0
        
        summary_stats = {
            'total_inspections': total_inspections,
            'avg_cost': avg_cost,
            'avg_mileage': avg_mileage,
            'top_dealerships': top_dealerships
        }
        
        dealership_logger.info(f"Found {len(inspections)} SFS inspections for {company_name}")
        
        return render_template(
            'dealership/sfs_inspections.html',
            inspections=inspections,
            stats=summary_stats,
            filters={
                'vin': vin_filter,
                'dealership': dealership_filter,
                'date_from': date_from,
                'date_to': date_to
            },
            user=current_user,
            company_name=company_name,
            company_config=company_config
        )
        
    except Exception as e:
        dealership_logger.error(f"Error loading SFS inspections: {str(e)}")
        flash('Error loading SFS inspections data', 'error')
        return render_template('dealership/sfs_inspections.html', inspections=[], stats={}, user=current_user,
                             company_name=current_user.company_id.title(), company_config=None)

@log_function_call(dealership_logger)
def pdi_inspections():
    """PDI inspections management page"""
    try:
        # Get company information
        from config import get_company_config
        company_config = get_company_config(current_user.company_id)
        company_name = company_config.name
        
        # Get filter parameters
        dealership_filter = request.args.get('dealership', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # Get PDI statistics
        pdi_stats = InspectionService.get_pdi_statistics(
            dealership_name=dealership_filter if dealership_filter else None,
            date_from=date_from if date_from else None,
            date_to=date_to if date_to else None,
            company_id=current_user.company_id
        )
        
        return render_template(
            'dealership/pdi_inspections.html',
            pdi_stats=pdi_stats,
            filters={
                'dealership': dealership_filter,
                'date_from': date_from,
                'date_to': date_to
            },
            user=current_user,
            company_name=company_name,
            company_config=company_config
        )
        
    except Exception as e:
        dealership_logger.error(f"Error loading PDI inspections: {str(e)}")
        flash('Error loading PDI inspections data', 'error')
        return render_template('dealership/pdi_inspections.html', pdi_stats={}, user=current_user,
                             company_name=current_user.company_id.title(), company_config=None)

@log_function_call(dealership_logger)
def repair_orders():
    """Repair orders management page"""
    try:
        # Get company information
        from config import get_company_config
        company_config = get_company_config(current_user.company_id)
        company_name = company_config.name
        
        # Get filter parameters
        vin_filter = request.args.get('vin', '')
        ro_filter = request.args.get('ro_number', '')
        dealership_filter = request.args.get('dealership', '')
        status_filter = request.args.get('status', '')
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        
        # Get repair order data
        db = DealershipDatabase(company_id=current_user.company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT * FROM repair_orders 
                WHERE 1=1
            """
            params = []
            
            if vin_filter:
                query += " AND vin_number = ?"
                params.append(vin_filter)
                
            if ro_filter:
                query += " AND ro_number LIKE ?"
                params.append(f"%{ro_filter}%")
                
            if dealership_filter:
                query += " AND dealership_name = ?"
                params.append(dealership_filter)
                
            if status_filter:
                query += " AND status = ?"
                params.append(status_filter)
            
            if date_from:
                query += " AND ro_date >= ?"
                params.append(date_from)
                
            if date_to:
                query += " AND ro_date <= ?"
                params.append(date_to)
            
            query += " ORDER BY ro_date DESC"
            
            cursor.execute(query, params)
            repair_orders = [dict(row) for row in cursor.fetchall()]
            
            # Get summary statistics
            cursor.execute("SELECT COUNT(*) as total FROM repair_orders")
            total_ros = cursor.fetchone()['total']
            
            cursor.execute("""
                SELECT COUNT(*) as warranty_count 
                FROM repair_orders 
                WHERE warranty_applicable = 1
            """)
            warranty_ros = cursor.fetchone()['warranty_count']
            
            cursor.execute("""
                SELECT AVG(total_cost) as avg_cost 
                FROM repair_orders 
                WHERE total_cost > 0
            """)
            avg_cost = cursor.fetchone()['avg_cost'] or 0
            
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM repair_orders 
                GROUP BY status 
                ORDER BY count DESC
            """)
            status_breakdown = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("""
                SELECT dealership_name, COUNT(*) as count, AVG(total_cost) as avg_cost
                FROM repair_orders 
                GROUP BY dealership_name 
                ORDER BY count DESC 
                LIMIT 5
            """)
            top_dealerships = [dict(row) for row in cursor.fetchall()]
        
        summary_stats = {
            'total_ros': total_ros,
            'warranty_ros': warranty_ros,
            'avg_cost': avg_cost,
            'status_breakdown': status_breakdown,
            'top_dealerships': top_dealerships
        }
        
        dealership_logger.info(f"Found {len(repair_orders)} repair orders for {company_name}")
        
        return render_template(
            'dealership/repair_orders.html',
            repair_orders=repair_orders,
            stats=summary_stats,
            filters={
                'vin': vin_filter,
                'ro_number': ro_filter,
                'dealership': dealership_filter,
                'status': status_filter,
                'date_from': date_from,
                'date_to': date_to
            },
            user=current_user,
            company_name=company_name,
            company_config=company_config
        )
        
    except Exception as e:
        dealership_logger.error(f"Error loading repair orders: {str(e)}")
        flash('Error loading repair orders data', 'error')
        return render_template('dealership/repair_orders.html', repair_orders=[], stats={}, user=current_user,
                             company_name=current_user.company_id.title(), company_config=None)

@log_function_call(dealership_logger)
def vin_history():
    """Complete VIN history page"""
    try:
        # Get company information
        from config import get_company_config
        company_config = get_company_config(current_user.company_id)
        company_name = company_config.name
        
        vin_number = request.args.get('vin', '').strip().upper()
        
        if not vin_number:
            return render_template(
                'dealership/vin_history.html',
                history=None,
                vin_number='',
                user=current_user,
                company_name=company_name,
                company_config=company_config
            )
        
        # Get complete history for VIN
        history = InspectionService.get_vin_complete_history(vin_number, company_id=current_user.company_id)
        
        return render_template(
            'dealership/vin_history.html',
            history=history,
            vin_number=vin_number,
            user=current_user,
            company_name=company_name,
            company_config=company_config
        )
        
    except Exception as e:
        dealership_logger.error(f"Error loading VIN history: {str(e)}")
        flash('Error loading VIN history data', 'error')
        return render_template('dealership/vin_history.html', history=None, user=current_user,
                             company_name=current_user.company_id.title(), company_config=None)

# API Endpoints for AJAX requests

@log_function_call(dealership_logger)
def api_tyre_complaints():
    """API endpoint for tyre complaints data"""
    try:
        year = int(request.args.get('year', datetime.now().year))
        month = int(request.args.get('month', datetime.now().month))
        
        tyre_data = WarrantyClaim.get_tyre_complaints_by_month(year, month, company_id=current_user.company_id)
        
        return jsonify({
            'success': True,
            'data': tyre_data
        })
        
    except Exception as e:
        dealership_logger.error(f"Error getting tyre complaints: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@log_function_call(dealership_logger)
def api_dealership_stats():
    """API endpoint for dealership statistics"""
    try:
        dealership_name = request.args.get('dealership')
        
        # Get various statistics for the dealership
        warranty_stats = WarrantyClaim.get_dealership_complaints(dealership_name, company_id=current_user.company_id)
        ro_stats = RepairOrder.get_ro_statistics(dealership_name, company_id=current_user.company_id)
        
        return jsonify({
            'success': True,
            'warranty_stats': warranty_stats,
            'ro_stats': ro_stats
        })
        
    except Exception as e:
        dealership_logger.error(f"Error getting dealership stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@log_function_call(dealership_logger)
def export_data():
    """Export dealership data to CSV"""
    try:
        data_type = request.args.get('type', 'warranty_claims')
        
        # Create CSV data based on type
        output = io.StringIO()
        writer = csv.writer(output)
        
        if data_type == 'warranty_claims':
            # Export warranty claims
            writer.writerow(['VIN', 'Dealership', 'Car Model', 'Claim Date', 'Problem', 'Status', 'Cost'])
            # Add actual data here
            
        elif data_type == 'pdi_inspections':
            # Export PDI inspections
            writer.writerow(['VIN', 'Dealership', 'Car Model', 'Inspection Date', 'Status', 'Objections'])
            # Add actual data here
        
        output.seek(0)
        
        return jsonify({
            'success': True,
            'csv_data': output.getvalue()
        })
        
    except Exception as e:
        dealership_logger.error(f"Error exporting data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500