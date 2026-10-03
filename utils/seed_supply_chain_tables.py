"""
Supply Chain Table Seeder Script
Creates new supply chain tables and inserts 10 sample rows for each in haval_supply_chain.db
"""
import random
import sqlite3
from datetime import datetime, timedelta


def seed_dealer_orders(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS DealerOrders (
            OrderID INTEGER PRIMARY KEY AUTOINCREMENT,
            DealerID INTEGER,
            DealerName TEXT,
            VehicleModel TEXT,
            Variant TEXT,
            PartType TEXT,
            OrderQty INTEGER,
            Quarter TEXT,
            AllocatedQty INTEGER,
            DeliveryStatus TEXT,
            CampaignType TEXT
        )
    """)
    dealers = ["Haval Central", "Haval Lahore", "Haval Karachi", "Haval Islamabad", "Haval Faisalabad", "Haval Multan"]
    models = ["H6 PHEV", "H6", "Jolion"]
    variants = ["Premium", "Ultra", "Active"]
    parts = ["Rims", "Battery", "Engine", "Fuel Pump", "Dashboard"]
    quarters = ["Q1 2026", "Q2 2026"]
    statuses = ["Pending", "Delivered", "Delayed"]
    campaigns = ["Leasing", "Financing", "None"]
    for i in range(10):
        conn.execute("""
            INSERT INTO DealerOrders (DealerID, DealerName, VehicleModel, Variant, PartType, OrderQty, Quarter, AllocatedQty, DeliveryStatus, CampaignType)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            i+1,
            random.choice(dealers),
            random.choice(models),
            random.choice(variants),
            random.choice(parts),
            random.randint(5, 50),
            random.choice(quarters),
            random.randint(0, 50),
            random.choice(statuses),
            random.choice(campaigns)
        ))

def seed_suppliers(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Suppliers (
            SupplierID INTEGER PRIMARY KEY AUTOINCREMENT,
            SupplierName TEXT,
            PartType TEXT,
            OnTimeDeliveryRate REAL,
            QualityScore REAL,
            PendingConfirmation TEXT,
            CancellationStatus TEXT,
            IssueDescription TEXT
        )
    """)
    names = ["Zhongcan Junda", "Chongqing Jinyu", "Henan Ruijie", "Qingdao CSD", "Tianjin Zhonghuide", "Chongqing Shiwei", "Taizhou CINA", "Chongqing Yonghong", "CATL Battery", "Great Wall Motors"]
    parts = ["Rims", "Engine", "Battery", "Fuel Pump", "Dashboard"]
    for i in range(10):
        conn.execute("""
            INSERT INTO Suppliers (SupplierName, PartType, OnTimeDeliveryRate, QualityScore, PendingConfirmation, CancellationStatus, IssueDescription)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            names[i],
            random.choice(parts),
            round(random.uniform(85, 100), 2),
            round(random.uniform(7, 10), 2),
            random.choice(["Yes", "No"]),
            random.choice(["None", "Cancelled", "Delayed"]),
            random.choice(["", "Delay due to customs", "Quality issue resolved", "Pending confirmation"])
        ))

def seed_safety_stock(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS SafetyStockLevels (
            PartID INTEGER PRIMARY KEY AUTOINCREMENT,
            PartName TEXT,
            Criticality TEXT,
            SafetyStock INTEGER,
            BufferStock INTEGER,
            ServiceLevel REAL
        )
    """)
    parts = ["Engine", "Transmission", "Battery", "Fuel Pump", "Dashboard", "Bumper", "Oil Filter", "Rims", "PHEV Battery", "CKD Kit"]
    for i, part in enumerate(parts):
        conn.execute("""
            INSERT INTO SafetyStockLevels (PartName, Criticality, SafetyStock, BufferStock, ServiceLevel)
            VALUES (?, ?, ?, ?, ?)
        """, (
            part,
            random.choice(["High", "Medium", "Low"]),
            random.randint(10, 100),
            random.randint(5, 50),
            round(random.uniform(0.90, 0.99), 2)
        ))

def seed_shipments(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Shipments (
            ShipmentID INTEGER PRIMARY KEY AUTOINCREMENT,
            PartType TEXT,
            ExpectedArrival TEXT,
            ActualArrival TEXT,
            DelayDays INTEGER,
            ConfirmationStatus TEXT,
            CancellationStatus TEXT,
            ProductionImpact TEXT
        )
    """)
    parts = ["Engine", "Battery", "Fuel Pump", "Dashboard", "Rims"]
    for i in range(10):
        expected = datetime.now() + timedelta(days=random.randint(1, 30))
        actual = expected + timedelta(days=random.randint(-2, 10))
        delay = (actual - expected).days
        conn.execute("""
            INSERT INTO Shipments (PartType, ExpectedArrival, ActualArrival, DelayDays, ConfirmationStatus, CancellationStatus, ProductionImpact)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            random.choice(parts),
            expected.strftime('%Y-%m-%d'),
            actual.strftime('%Y-%m-%d'),
            delay,
            random.choice(["Confirmed", "Pending"]),
            random.choice(["None", "Cancelled", "Delayed"]),
            random.choice(["No impact", "Production delayed", "Cash flow affected"])
        ))

def seed_imports(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS Imports (
            ImportID INTEGER PRIMARY KEY AUTOINCREMENT,
            PartID INTEGER,
            PartName TEXT,
            ImportCost REAL,
            Duties REAL,
            Freight REAL,
            LandedCost REAL,
            Quarter TEXT
        )
    """)
    parts = ["Bumper", "Rims", "Fuel Pump", "Dashboard"]
    for i, part in enumerate(parts):
        import_cost = round(random.uniform(1000, 5000), 2)
        duties = round(import_cost * random.uniform(0.15, 0.25), 2)
        freight = round(import_cost * random.uniform(0.05, 0.10), 2)
        landed = import_cost + duties + freight
        conn.execute("""
            INSERT INTO Imports (PartID, PartName, ImportCost, Duties, Freight, LandedCost, Quarter)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            i+1,
            part,
            import_cost,
            duties,
            freight,
            landed,
            random.choice(["Q1 2026", "Q2 2026"])
        ))
    # Add more rows for diversity
    for i in range(6):
        part = random.choice(parts)
        import_cost = round(random.uniform(1000, 5000), 2)
        duties = round(import_cost * random.uniform(0.15, 0.25), 2)
        freight = round(import_cost * random.uniform(0.05, 0.10), 2)
        landed = import_cost + duties + freight
        conn.execute("""
            INSERT INTO Imports (PartID, PartName, ImportCost, Duties, Freight, LandedCost, Quarter)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            random.randint(1, 10),
            part,
            import_cost,
            duties,
            freight,
            landed,
            random.choice(["Q1 2026", "Q2 2026"])
        ))

def seed_kpis(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS KPIs (
            KPIID INTEGER PRIMARY KEY AUTOINCREMENT,
            KPIName TEXT,
            Target REAL,
            Actual REAL,
            Deviation REAL,
            Week TEXT
        )
    """)
    kpis = ["Production Volume", "Inventory Turnover", "Assembly Line Uptime", "Service Level", "Order Fulfillment"]
    for i in range(10):
        kpi = random.choice(kpis)
        target = round(random.uniform(80, 100), 2)
        actual = round(target + random.uniform(-10, 10), 2)
        deviation = actual - target
        week = f"2026-W{random.randint(1, 12)}"
        conn.execute("""
            INSERT INTO KPIs (KPIName, Target, Actual, Deviation, Week)
            VALUES (?, ?, ?, ?, ?)
        """, (
            kpi,
            target,
            actual,
            deviation,
            week
        ))

def main():
    db_path = "data/haval_supply_chain.db"
    conn = sqlite3.connect(db_path)
    seed_dealer_orders(conn)
    seed_suppliers(conn)
    seed_safety_stock(conn)
    seed_shipments(conn)
    seed_imports(conn)
    seed_kpis(conn)
    conn.commit()
    conn.close()
    print("✅ Supply chain tables seeded with sample data in haval_supply_chain.db")

if __name__ == "__main__":
    main()
