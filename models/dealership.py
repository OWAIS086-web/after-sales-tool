"""
Dealership Management Models
Handles all dealership-related data including warranty claims, campaigns, inspections, and repair orders.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from utils.logger import dealership_logger, log_function_call
import json
import re

class DealershipDatabase:
    """Database operations for dealership management system"""
    
    def __init__(self, db_path: str = None, company_id: str = None):
        if db_path:
            self.db_path = db_path
        elif company_id:
            # Use company-specific database
            if company_id == "kia":
                self.db_path = "data/dealership_kia.db"
            else:  # Default to Haval
                self.db_path = "data/dealership.db"
        else:
            # Fallback to default
            self.db_path = "data/dealership.db"
        self.init_database()
    
    @log_function_call(dealership_logger)
    def init_database(self):
        """Initialize all dealership-related tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Technical Reports / Warranty Claims Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS warranty_claims (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vin_number TEXT NOT NULL,
                    dealership_name TEXT NOT NULL,
                    car_model TEXT NOT NULL,
                    variant TEXT,
                    claim_date DATE NOT NULL,
                    problem_description TEXT,
                    problem_cause_analysis TEXT,
                    claim_type TEXT, -- 'tyre', 'engine', 'electrical', etc.
                    status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
                    cost DECIMAL(10,2),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Campaign Reports Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT UNIQUE NOT NULL,
                    campaign_name TEXT NOT NULL,
                    campaign_type TEXT, -- 'free_service', 'recall', 'inspection'
                    start_date DATE,
                    end_date DATE,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Campaign Services Table (Many-to-Many relationship)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS campaign_services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    campaign_id TEXT NOT NULL,
                    vin_number TEXT NOT NULL,
                    dealership_name TEXT NOT NULL,
                    car_model TEXT NOT NULL,
                    service_date DATE,
                    service_type TEXT,
                    status TEXT DEFAULT 'completed',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
                )
            """)
            
            # FFS Inspections Table (First Free Service after 1k km)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ffs_inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vin_number TEXT NOT NULL,
                    dealership_name TEXT NOT NULL,
                    car_model TEXT NOT NULL,
                    variant TEXT,
                    inspection_date DATE NOT NULL,
                    odometer_reading INTEGER,
                    inspection_type TEXT DEFAULT 'FFS', -- 'FFS', 'SFS'
                    findings TEXT,
                    recommendations TEXT,
                    cost DECIMAL(10,2) DEFAULT 0.00,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # SFS Inspections Table (Second Free Service at 5000km)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sfs_inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vin_number TEXT NOT NULL,
                    dealership_name TEXT NOT NULL,
                    car_model TEXT NOT NULL,
                    variant TEXT,
                    inspection_date DATE NOT NULL,
                    odometer_reading INTEGER,
                    findings TEXT,
                    recommendations TEXT,
                    cost DECIMAL(10,2) DEFAULT 0.00,
                    status TEXT DEFAULT 'completed',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # PDI Inspections Table (Pre-Delivery Inspection)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pdi_inspections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vin_number TEXT UNIQUE NOT NULL,
                    dealership_name TEXT NOT NULL,
                    car_model TEXT NOT NULL,
                    variant TEXT,
                    inspection_date DATE NOT NULL,
                    factory_delivery_date DATE,
                    pdi_status TEXT, -- 'passed', 'failed', 'objection'
                    objections TEXT, -- JSON array of objections
                    objection_count INTEGER DEFAULT 0,
                    delivery_status TEXT, -- 'delivered', 'pending', 'rejected'
                    inspector_name TEXT,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Repair Orders Table (RO List - Major Section)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS repair_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ro_number TEXT UNIQUE NOT NULL,
                    vin_number TEXT NOT NULL,
                    chassis_number TEXT,
                    dealership_name TEXT NOT NULL,
                    car_model TEXT NOT NULL,
                    variant TEXT,
                    customer_name TEXT,
                    customer_phone TEXT,
                    issue_description TEXT,
                    repair_description TEXT,
                    parts_used TEXT, -- JSON array
                    labor_hours DECIMAL(4,2),
                    parts_cost DECIMAL(10,2),
                    labor_cost DECIMAL(10,2),
                    total_cost DECIMAL(10,2),
                    ro_date DATE NOT NULL,
                    completion_date DATE,
                    status TEXT DEFAULT 'open', -- 'open', 'in_progress', 'completed', 'cancelled'
                    warranty_applicable BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Dealerships Master Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dealerships (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dealership_code TEXT UNIQUE NOT NULL,
                    dealership_name TEXT NOT NULL,
                    city TEXT,
                    region TEXT,
                    contact_person TEXT,
                    phone TEXT,
                    email TEXT,
                    address TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Vehicle Master Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vehicles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vin_number TEXT UNIQUE NOT NULL,
                    chassis_number TEXT,
                    engine_number TEXT,
                    car_model TEXT NOT NULL,
                    variant TEXT,
                    model_year INTEGER,
                    color TEXT,
                    manufacturing_date DATE,
                    delivery_date DATE,
                    dealership_name TEXT,
                    customer_name TEXT,
                    status TEXT DEFAULT 'active', -- 'active', 'warranty_terminated'
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_warranty_vin ON warranty_claims(vin_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_warranty_dealership ON warranty_claims(dealership_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_warranty_date ON warranty_claims(claim_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_campaign_services_vin ON campaign_services(vin_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ffs_vin ON ffs_inspections(vin_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_sfs_vin ON sfs_inspections(vin_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pdi_vin ON pdi_inspections(vin_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ro_vin ON repair_orders(vin_number)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ro_number ON repair_orders(ro_number)")
            
            conn.commit()
            dealership_logger.info("Dealership database initialized successfully")

class WarrantyClaim:
    """Warranty Claims operations"""
    
    @staticmethod
    @log_function_call(dealership_logger)
    def get_claims_by_vin(vin_number: str, company_id: str = None) -> List[Dict]:
        """Get all warranty claims for a specific VIN"""
        db = DealershipDatabase(company_id=company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM warranty_claims 
                WHERE vin_number = ? 
                ORDER BY claim_date DESC
            """, (vin_number,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    @log_function_call(dealership_logger)
    def get_most_complained_vins(limit: int = 10, company_id: str = None) -> List[Dict]:
        """Get VIN numbers with most complaints"""
        db = DealershipDatabase(company_id=company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT vin_number, car_model, dealership_name, 
                       COUNT(*) as complaint_count,
                       GROUP_CONCAT(DISTINCT claim_type) as claim_types
                FROM warranty_claims 
                GROUP BY vin_number 
                ORDER BY complaint_count DESC 
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    @log_function_call(dealership_logger)
    def get_dealership_complaints(dealership_name: str = None, date_from: str = None, date_to: str = None, company_id: str = None) -> List[Dict]:
        """Get complaints by dealership with optional date filtering"""
        db = DealershipDatabase(company_id=company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT dealership_name, COUNT(*) as complaint_count,
                       GROUP_CONCAT(DISTINCT claim_type) as claim_types,
                       AVG(cost) as avg_cost
                FROM warranty_claims 
                WHERE 1=1
            """
            params = []
            
            if dealership_name:
                query += " AND dealership_name = ?"
                params.append(dealership_name)
            
            if date_from:
                query += " AND claim_date >= ?"
                params.append(date_from)
                
            if date_to:
                query += " AND claim_date <= ?"
                params.append(date_to)
            
            query += " GROUP BY dealership_name ORDER BY complaint_count DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    @log_function_call(dealership_logger)
    def get_tyre_complaints_by_month(year: int, month: int, company_id: str = None) -> Dict:
        """Get tyre-related complaints for specific month"""
        db = DealershipDatabase(company_id=company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) as tyre_complaints,
                       GROUP_CONCAT(DISTINCT dealership_name) as dealerships,
                       GROUP_CONCAT(DISTINCT car_model) as models
                FROM warranty_claims 
                WHERE claim_type LIKE '%tyre%' 
                AND strftime('%Y', claim_date) = ? 
                AND strftime('%m', claim_date) = ?
            """, (str(year), f"{month:02d}"))
            
            result = cursor.fetchone()
            return dict(result) if result else {}

class CampaignService:
    """Campaign Services operations"""
    
    @staticmethod
    @log_function_call(dealership_logger)
    def get_campaign_stats(campaign_id: str = None, dealership_name: str = None, company_id: str = None) -> Dict:
        """Get campaign statistics"""
        db = DealershipDatabase(company_id=company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT cs.dealership_name, cs.car_model,
                       COUNT(*) as services_count,
                       c.campaign_name, c.campaign_type
                FROM campaign_services cs
                JOIN campaigns c ON cs.campaign_id = c.campaign_id
                WHERE 1=1
            """
            params = []
            
            if campaign_id:
                query += " AND cs.campaign_id = ?"
                params.append(campaign_id)
                
            if dealership_name:
                query += " AND cs.dealership_name = ?"
                params.append(dealership_name)
            
            query += " GROUP BY cs.dealership_name, cs.car_model, cs.campaign_id"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

class InspectionService:
    """Inspection Services (FFS, SFS, PDI) operations"""
    
    @staticmethod
    @log_function_call(dealership_logger)
    def get_vin_complete_history(vin_number: str, company_id: str = None) -> Dict:
        """Get complete history for a VIN number"""
        db = DealershipDatabase(company_id=company_id)
        history = {
            'vin_number': vin_number,
            'vehicle_info': {},
            'warranty_claims': [],
            'campaigns': [],
            'ffs_inspections': [],
            'sfs_inspections': [],
            'pdi_inspection': {},
            'repair_orders': []
        }
        
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Vehicle info
            cursor.execute("SELECT * FROM vehicles WHERE vin_number = ?", (vin_number,))
            vehicle = cursor.fetchone()
            if vehicle:
                history['vehicle_info'] = dict(vehicle)
            
            # Warranty claims
            cursor.execute("SELECT * FROM warranty_claims WHERE vin_number = ? ORDER BY claim_date DESC", (vin_number,))
            history['warranty_claims'] = [dict(row) for row in cursor.fetchall()]
            
            # Campaign services
            cursor.execute("""
                SELECT cs.*, c.campaign_name, c.campaign_type 
                FROM campaign_services cs
                JOIN campaigns c ON cs.campaign_id = c.campaign_id
                WHERE cs.vin_number = ? 
                ORDER BY cs.service_date DESC
            """, (vin_number,))
            history['campaigns'] = [dict(row) for row in cursor.fetchall()]
            
            # FFS inspections
            cursor.execute("SELECT * FROM ffs_inspections WHERE vin_number = ? ORDER BY inspection_date DESC", (vin_number,))
            history['ffs_inspections'] = [dict(row) for row in cursor.fetchall()]
            
            # SFS inspections
            cursor.execute("SELECT * FROM sfs_inspections WHERE vin_number = ? ORDER BY inspection_date DESC", (vin_number,))
            history['sfs_inspections'] = [dict(row) for row in cursor.fetchall()]
            
            # PDI inspection
            cursor.execute("SELECT * FROM pdi_inspections WHERE vin_number = ?", (vin_number,))
            pdi = cursor.fetchone()
            if pdi:
                history['pdi_inspection'] = dict(pdi)
            
            # Repair orders
            cursor.execute("SELECT * FROM repair_orders WHERE vin_number = ? ORDER BY ro_date DESC", (vin_number,))
            history['repair_orders'] = [dict(row) for row in cursor.fetchall()]
        
        return history
    
    @staticmethod
    @log_function_call(dealership_logger)
    def get_pdi_statistics(dealership_name: str = None, date_from: str = None, date_to: str = None, company_id: str = None) -> Dict:
        """Get PDI inspection statistics"""
        db = DealershipDatabase(company_id=company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Base query for PDI stats
            base_query = "FROM pdi_inspections WHERE 1=1"
            params = []
            
            if dealership_name:
                base_query += " AND dealership_name = ?"
                params.append(dealership_name)
            
            if date_from:
                base_query += " AND inspection_date >= ?"
                params.append(date_from)
                
            if date_to:
                base_query += " AND inspection_date <= ?"
                params.append(date_to)
            
            # Total PDIs
            cursor.execute(f"SELECT COUNT(*) as total_pdis {base_query}", params)
            total_pdis = cursor.fetchone()['total_pdis']
            
            # PDIs with objections
            cursor.execute(f"SELECT COUNT(*) as objection_pdis {base_query} AND pdi_status = 'objection'", params)
            objection_pdis = cursor.fetchone()['objection_pdis']
            
            # PDIs by dealership
            cursor.execute(f"""
                SELECT dealership_name, COUNT(*) as pdi_count,
                       SUM(CASE WHEN pdi_status = 'objection' THEN 1 ELSE 0 END) as objection_count
                {base_query}
                GROUP BY dealership_name 
                ORDER BY pdi_count DESC
            """, params)
            dealership_stats = [dict(row) for row in cursor.fetchall()]
            
            return {
                'total_pdis': total_pdis,
                'objection_pdis': objection_pdis,
                'objection_percentage': round((objection_pdis / total_pdis * 100) if total_pdis > 0 else 0, 2),
                'dealership_stats': dealership_stats
            }

class RepairOrder:
    """Repair Orders operations"""
    
    @staticmethod
    @log_function_call(dealership_logger)
    def get_ro_by_vin(vin_number: str, company_id: str = None) -> List[Dict]:
        """Get all repair orders for a VIN"""
        db = DealershipDatabase(company_id=company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT * FROM repair_orders 
                WHERE vin_number = ? 
                ORDER BY ro_date DESC
            """, (vin_number,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    @staticmethod
    @log_function_call(dealership_logger)
    def get_ro_statistics(dealership_name: str = None, company_id: str = None) -> Dict:
        """Get repair order statistics"""
        db = DealershipDatabase(company_id=company_id)
        with sqlite3.connect(db.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = """
                SELECT dealership_name, COUNT(*) as ro_count,
                       AVG(total_cost) as avg_cost,
                       SUM(CASE WHEN warranty_applicable = 1 THEN 1 ELSE 0 END) as warranty_ros
                FROM repair_orders
            """
            params = []
            
            if dealership_name:
                query += " WHERE dealership_name = ?"
                params.append(dealership_name)
            
            query += " GROUP BY dealership_name ORDER BY ro_count DESC"
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]