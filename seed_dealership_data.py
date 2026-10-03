#!/usr/bin/env python3
"""
Dealership Data Seeder Script
Run this script to populate the dealership database with sample data
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.dealership_seeder import DealershipSeeder
from utils.logger import dealership_logger

def main():
    """Main function to run the seeder"""
    dealership_logger.info("🏢 Dealership Data Seeder")
    dealership_logger.info("=" * 50)
    
    try:
        seeder = DealershipSeeder()
        
        dealership_logger.info("Starting to seed dealership database with sample data...")
        dealership_logger.info("This will create:")
        dealership_logger.info("- 6 Dealerships")
        dealership_logger.info("- 100 Vehicles")
        dealership_logger.info("- 80 PDI Inspections")
        dealership_logger.info("- 50 Warranty Claims")
        dealership_logger.info("- 4 Campaigns with 100 Services")
        dealership_logger.info("- 60 FFS Inspections")
        dealership_logger.info("- 40 SFS Inspections")
        dealership_logger.info("- 30 Repair Orders")
        dealership_logger.info("")
        
        # For interactive mode, still use print for user input
        confirm = input("Do you want to proceed? (y/N): ").lower().strip()
        
        if confirm == 'y' or confirm == 'yes':
            dealership_logger.info("🚀 Starting seeding process...")
            seeder.seed_all()
            dealership_logger.info("✅ Seeding completed successfully!")
            dealership_logger.info("You can now:")
            dealership_logger.info("1. Visit /dealership to see the dashboard")
            dealership_logger.info("2. Explore different sections like warranty claims, PDI inspections, etc.")
            dealership_logger.info("3. Use VIN search to see complete vehicle history")
            dealership_logger.info("4. View analytics and reports")
        else:
            dealership_logger.info("❌ Seeding cancelled.")
            
    except Exception as e:
        dealership_logger.error(f"❌ Error during seeding: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()