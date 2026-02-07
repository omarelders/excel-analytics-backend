"""
Migration script to add soft delete columns to shipments and payment_records tables.
Run this script to update your existing database.

Usage:
    python add_soft_delete_columns.py
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Render/SQLAlchemy fix for postgres:// vs postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    print("[ERROR] DATABASE_URL not found in .env file!")
    exit(1)

def run_migration():
    engine = create_engine(DATABASE_URL)
    
    print("[INFO] Running soft delete migration...")
    
    with engine.connect() as conn:
        # Check if columns already exist in shipments
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'shipments' AND column_name = 'is_deleted'
        """))
        
        if result.fetchone():
            print("[OK] Shipments table already has soft delete columns")
        else:
            print("Adding is_deleted and deleted_at columns to shipments...")
            conn.execute(text("""
                ALTER TABLE shipments 
                ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE
            """))
            conn.execute(text("""
                ALTER TABLE shipments 
                ADD COLUMN deleted_at TIMESTAMP
            """))
            # Create index for performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_shipments_is_deleted 
                ON shipments(is_deleted)
            """))
            print("[DONE] Added soft delete columns to shipments")
        
        # Check if columns already exist in payment_records
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'payment_records' AND column_name = 'is_deleted'
        """))
        
        if result.fetchone():
            print("[OK] Payment_records table already has soft delete columns")
        else:
            print("Adding is_deleted and deleted_at columns to payment_records...")
            conn.execute(text("""
                ALTER TABLE payment_records 
                ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE
            """))
            conn.execute(text("""
                ALTER TABLE payment_records 
                ADD COLUMN deleted_at TIMESTAMP
            """))
            # Create index for performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_payment_records_is_deleted 
                ON payment_records(is_deleted)
            """))
            print("[DONE] Added soft delete columns to payment_records")
        
        conn.commit()
    
    print("\n[SUCCESS] Migration completed successfully!")
    print("Your data is now protected with soft delete functionality.")

if __name__ == "__main__":
    run_migration()
