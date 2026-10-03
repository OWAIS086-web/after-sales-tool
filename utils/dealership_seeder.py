"""
Dealership Data Seeder
Populates the dealership database with sample data for demonstration
"""

import sqlite3
import random
from datetime import datetime, timedelta
from models.dealership import DealershipDatabase
from utils.logger import dealership_logger

class DealershipSeeder:
    """Seed dealership database with sample data"""
    
    def __init__(self):
        self.db = DealershipDatabase()
        
        # Sample data
        self.dealerships = [
            'Haval Central',
            'Haval Lahore', 
            'Haval Karachi',
            'Haval Islamabad',
            'Haval Faisalabad',
            'Haval Multan'
        ]
        
        self.car_models = [
            'Haval H6',
            'Haval Jolion',
            'Haval H6 PHEV'
        ]
        
        self.variants = {
            'Haval H6': ['Active', 'Premium', 'Ultra'],
            'Haval Jolion': ['Active', 'Premium'],
            'Haval H6 PHEV': ['Premium', 'Ultra']
        }
        
        self.colors = ['White', 'Black', 'Silver', 'Red', 'Blue', 'Gray']
        
        self.claim_types = ['tyre', 'engine', 'electrical', 'transmission', 'brake', 'suspension']
        
        self.campaign_types = ['free_service', 'recall', 'inspection', 'maintenance']
        
        self.customer_names = [
            'Ahmed Ali', 'Fatima Khan', 'Muhammad Hassan', 'Ayesha Ahmed',
            'Ali Raza', 'Zainab Shah', 'Omar Malik', 'Sana Tariq',
            'Bilal Ahmed', 'Mariam Siddique', 'Usman Ghani', 'Hira Nawaz'
        ]
        
        self.phone_numbers = [
            '03001234567', '03211234567', '03331234567', '03451234567',
            '03009876543', '03219876543', '03339876543', '03459876543'
        ]
    
    def generate_vin(self):
        """Generate a sample VIN number"""
        chars = 'ABCDEFGHJKLMNPRSTUVWXYZ0123456789'
        return 'LGWEF4A59LG' + ''.join(random.choices(chars, k=6))
    
    def generate_ro_number(self):
        """Generate a sample RO number"""
        return f"RO{random.randint(100000, 999999)}"
    
    def generate_campaign_id(self):
        """Generate a sample campaign ID"""
        return f"CAMP{random.randint(1000, 9999)}"
    
    def seed_dealerships(self):
        """Seed dealerships master data"""
        dealership_logger.info("Seeding dealerships...")
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            for i, dealership in enumerate(self.dealerships):
                cursor.execute("""
                    INSERT OR IGNORE INTO dealerships 
                    (dealership_code, dealership_name, city, region, contact_person, phone, email, address)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    f"DLR{i+1:03d}",
                    dealership,
                    dealership.split(' ')[1] if ' ' in dealership else 'Lahore',
                    'Punjab',
                    f"Manager {i+1}",
                    f"042123456{i+1:02d}",
                    f"manager{i+1}@haval.com.pk",
                    f"Address {i+1}, {dealership.split(' ')[1] if ' ' in dealership else 'Lahore'}"
                ))
            
            conn.commit()
            dealership_logger.info(f"Seeded {len(self.dealerships)} dealerships")
    
    def seed_vehicles(self, count=100):
        """Seed vehicles master data"""
        dealership_logger.info(f"Seeding {count} vehicles...")
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            for _ in range(count):
                car_model = random.choice(self.car_models)
                variant = random.choice(self.variants[car_model])
                vin = self.generate_vin()
                
                manufacturing_date = datetime.now() - timedelta(days=random.randint(30, 365))
                delivery_date = manufacturing_date + timedelta(days=random.randint(7, 60))
                
                cursor.execute("""
                    INSERT OR IGNORE INTO vehicles 
                    (vin_number, chassis_number, engine_number, car_model, variant, 
                     model_year, color, manufacturing_date, delivery_date, 
                     dealership_name, customer_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vin,
                    f"CH{random.randint(100000, 999999)}",
                    f"EN{random.randint(100000, 999999)}",
                    car_model,
                    variant,
                    2024,
                    random.choice(self.colors),
                    manufacturing_date.strftime('%Y-%m-%d'),
                    delivery_date.strftime('%Y-%m-%d'),
                    random.choice(self.dealerships),
                    random.choice(self.customer_names)
                ))
            
            conn.commit()
            dealership_logger.info(f"Seeded {count} vehicles")
    
    def seed_pdi_inspections(self, count=80):
        """Seed PDI inspections"""
        dealership_logger.info(f"Seeding {count} PDI inspections...")
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            # Get some VINs
            cursor.execute("SELECT vin_number, car_model, dealership_name FROM vehicles LIMIT ?", (count,))
            vehicles = cursor.fetchall()
            
            for vin, car_model, dealership in vehicles:
                inspection_date = datetime.now() - timedelta(days=random.randint(1, 180))
                factory_delivery = inspection_date - timedelta(days=random.randint(1, 7))
                
                # 20% chance of objections
                has_objections = random.random() < 0.2
                pdi_status = 'objection' if has_objections else 'passed'
                objection_count = random.randint(1, 3) if has_objections else 0
                
                objections = []
                if has_objections:
                    possible_objections = [
                        'Paint scratches on door',
                        'Interior trim loose',
                        'Tire pressure low',
                        'Battery terminals corroded',
                        'Headlight alignment off'
                    ]
                    objections = random.sample(possible_objections, objection_count)
                
                cursor.execute("""
                    INSERT OR IGNORE INTO pdi_inspections 
                    (vin_number, dealership_name, car_model, inspection_date, 
                     factory_delivery_date, pdi_status, objections, objection_count,
                     delivery_status, inspector_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vin,
                    dealership,
                    car_model,
                    inspection_date.strftime('%Y-%m-%d'),
                    factory_delivery.strftime('%Y-%m-%d'),
                    pdi_status,
                    str(objections) if objections else None,
                    objection_count,
                    'delivered' if not has_objections else 'pending',
                    f"Inspector {random.randint(1, 10)}"
                ))
            
            conn.commit()
            dealership_logger.info(f"Seeded {len(vehicles)} PDI inspections")
    
    def seed_warranty_claims(self, count=50):
        """Seed warranty claims"""
        dealership_logger.info(f"Seeding {count} warranty claims...")
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            # Get some VINs
            cursor.execute("SELECT vin_number, car_model, dealership_name FROM vehicles LIMIT ?", (count,))
            vehicles = cursor.fetchall()
            
            for vin, car_model, dealership in vehicles:
                claim_date = datetime.now() - timedelta(days=random.randint(1, 365))
                claim_type = random.choice(self.claim_types)
                
                problems = {
                    'tyre': 'Premature tire wear on front wheels',
                    'engine': 'Engine making unusual noise during startup',
                    'electrical': 'Dashboard warning lights intermittent',
                    'transmission': 'Gear shifting rough in cold weather',
                    'brake': 'Brake pedal feels spongy',
                    'suspension': 'Suspension noise over bumps'
                }
                
                causes = {
                    'tyre': 'Manufacturing defect in tire compound',
                    'engine': 'Timing chain tensioner issue',
                    'electrical': 'Loose connection in wiring harness',
                    'transmission': 'Transmission fluid viscosity issue',
                    'brake': 'Air in brake lines',
                    'suspension': 'Worn suspension bushings'
                }
                
                cursor.execute("""
                    INSERT INTO warranty_claims 
                    (vin_number, dealership_name, car_model, claim_date, 
                     problem_description, problem_cause_analysis, claim_type, 
                     status, cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vin,
                    dealership,
                    car_model,
                    claim_date.strftime('%Y-%m-%d'),
                    problems[claim_type],
                    causes[claim_type],
                    claim_type,
                    random.choice(['pending', 'approved', 'rejected']),
                    random.randint(5000, 50000)
                ))
            
            conn.commit()
            dealership_logger.info(f"Seeded {count} warranty claims")
    
    def seed_campaigns(self):
        """Seed campaigns"""
        dealership_logger.info("Seeding campaigns...")
        
        campaigns = [
            ('CAMP2024001', 'Free Service Campaign 2024', 'free_service', '2024-01-01', '2024-12-31'),
            ('CAMP2024002', 'Brake System Recall', 'recall', '2024-03-01', '2024-06-30'),
            ('CAMP2024003', 'Summer Inspection Drive', 'inspection', '2024-06-01', '2024-08-31'),
            ('CAMP2024004', 'Winter Maintenance Package', 'maintenance', '2024-11-01', '2024-12-31')
        ]
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            for campaign_id, name, camp_type, start_date, end_date in campaigns:
                cursor.execute("""
                    INSERT OR IGNORE INTO campaigns 
                    (campaign_id, campaign_name, campaign_type, start_date, end_date, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    campaign_id,
                    name,
                    camp_type,
                    start_date,
                    end_date,
                    f"Description for {name}"
                ))
            
            conn.commit()
            dealership_logger.info(f"Seeded {len(campaigns)} campaigns")
    
    def seed_campaign_services(self, count=100):
        """Seed campaign services"""
        dealership_logger.info(f"Seeding {count} campaign services...")
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            # Get campaigns and vehicles
            cursor.execute("SELECT campaign_id FROM campaigns")
            campaigns = [row[0] for row in cursor.fetchall()]
            
            cursor.execute("SELECT vin_number, car_model, dealership_name FROM vehicles LIMIT ?", (count,))
            vehicles = cursor.fetchall()
            
            for vin, car_model, dealership in vehicles:
                campaign_id = random.choice(campaigns)
                service_date = datetime.now() - timedelta(days=random.randint(1, 180))
                
                cursor.execute("""
                    INSERT INTO campaign_services 
                    (campaign_id, vin_number, dealership_name, car_model, 
                     service_date, service_type, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    campaign_id,
                    vin,
                    dealership,
                    car_model,
                    service_date.strftime('%Y-%m-%d'),
                    random.choice(['inspection', 'repair', 'replacement', 'maintenance']),
                    'completed'
                ))
            
            conn.commit()
            dealership_logger.info(f"Seeded {count} campaign services")
    
    def seed_ffs_inspections(self, count=60):
        """Seed FFS inspections"""
        dealership_logger.info(f"Seeding {count} FFS inspections...")
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT vin_number, car_model, dealership_name FROM vehicles LIMIT ?", (count,))
            vehicles = cursor.fetchall()
            
            for vin, car_model, dealership in vehicles:
                inspection_date = datetime.now() - timedelta(days=random.randint(30, 120))
                odometer = random.randint(800, 1200)
                
                findings = [
                    'All systems functioning normally',
                    'Minor oil leak detected, sealed',
                    'Tire pressure adjusted',
                    'Battery terminals cleaned',
                    'Air filter replaced'
                ]
                
                cursor.execute("""
                    INSERT INTO ffs_inspections 
                    (vin_number, dealership_name, car_model, inspection_date, 
                     odometer_reading, findings, recommendations, cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vin,
                    dealership,
                    car_model,
                    inspection_date.strftime('%Y-%m-%d'),
                    odometer,
                    random.choice(findings),
                    'Continue regular maintenance schedule',
                    0.00
                ))
            
            conn.commit()
            dealership_logger.info(f"Seeded {count} FFS inspections")
    
    def seed_sfs_inspections(self, count=40):
        """Seed SFS inspections"""
        dealership_logger.info(f"Seeding {count} SFS inspections...")
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT vin_number, car_model, dealership_name FROM vehicles LIMIT ?", (count,))
            vehicles = cursor.fetchall()
            
            for vin, car_model, dealership in vehicles:
                inspection_date = datetime.now() - timedelta(days=random.randint(60, 200))
                odometer = random.randint(4500, 5500)
                
                findings = [
                    'All systems functioning normally',
                    'Brake pads showing normal wear',
                    'Engine oil changed',
                    'Transmission fluid checked',
                    'Suspension components inspected'
                ]
                
                cursor.execute("""
                    INSERT INTO sfs_inspections 
                    (vin_number, dealership_name, car_model, inspection_date, 
                     odometer_reading, findings, recommendations, cost)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    vin,
                    dealership,
                    car_model,
                    inspection_date.strftime('%Y-%m-%d'),
                    odometer,
                    random.choice(findings),
                    'Schedule next service at 10,000 km',
                    0.00
                ))
            
            conn.commit()
            dealership_logger.info(f"Seeded {count} SFS inspections")
    
    def seed_repair_orders(self, count=30):
        """Seed repair orders"""
        dealership_logger.info(f"Seeding {count} repair orders...")
        
        with sqlite3.connect(self.db.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT vin_number, car_model, dealership_name FROM vehicles LIMIT ?", (count,))
            vehicles = cursor.fetchall()
            
            for vin, car_model, dealership in vehicles:
                ro_date = datetime.now() - timedelta(days=random.randint(1, 90))
                
                issues = [
                    'Air conditioning not cooling properly',
                    'Strange noise from engine bay',
                    'Dashboard warning light on',
                    'Steering wheel vibration',
                    'Brake pedal feels soft'
                ]
                
                repairs = [
                    'Replaced AC compressor',
                    'Adjusted engine belt tension',
                    'Reset ECU error codes',
                    'Balanced wheels and aligned',
                    'Bled brake system'
                ]
                
                parts_cost = random.randint(5000, 25000)
                labor_cost = random.randint(2000, 8000)
                
                cursor.execute("""
                    INSERT INTO repair_orders 
                    (ro_number, vin_number, dealership_name, car_model, 
                     customer_name, customer_phone, issue_description, 
                     repair_description, parts_cost, labor_cost, total_cost,
                     ro_date, completion_date, status, warranty_applicable)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    self.generate_ro_number(),
                    vin,
                    dealership,
                    car_model,
                    random.choice(self.customer_names),
                    random.choice(self.phone_numbers),
                    random.choice(issues),
                    random.choice(repairs),
                    parts_cost,
                    labor_cost,
                    parts_cost + labor_cost,
                    ro_date.strftime('%Y-%m-%d'),
                    (ro_date + timedelta(days=random.randint(1, 5))).strftime('%Y-%m-%d'),
                    random.choice(['completed', 'in_progress', 'open']),
                    random.choice([True, False])
                ))
            
            conn.commit()
            dealership_logger.info(f"Seeded {count} repair orders")
    
    def seed_all(self):
        """Seed all dealership data"""
        dealership_logger.info("Starting dealership data seeding...")
        
        try:
            self.seed_dealerships()
            self.seed_vehicles(100)
            self.seed_pdi_inspections(80)
            self.seed_warranty_claims(50)
            self.seed_campaigns()
            self.seed_campaign_services(100)
            self.seed_ffs_inspections(60)
            self.seed_sfs_inspections(40)
            self.seed_repair_orders(30)
            
            dealership_logger.info("✅ Dealership data seeding completed successfully!")
            
        except Exception as e:
            dealership_logger.error(f"❌ Error during seeding: {str(e)}")
            raise

if __name__ == "__main__":
    seeder = DealershipSeeder()
    seeder.seed_all()