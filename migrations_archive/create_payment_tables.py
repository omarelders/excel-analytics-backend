"""
Recreate payment tables with all 48 columns.
This will DROP and recreate the payment tables (data will be lost).
"""
from database import engine, PaymentFile, PaymentRecord
from sqlalchemy import text

def recreate_payment_tables():
    print("⏳ Connecting to database...")
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Connected!")

        # Drop payment tables
        print("⏳ Dropping payment tables...")
        with engine.connect() as conn:
            conn.execute(text("DROP TABLE IF EXISTS payment_records CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS payment_files CASCADE"))
            conn.commit()
        print("✅ Tables dropped!")

        # Create payment tables with new schema
        print("⏳ Creating payment tables with all 48 columns...")
        PaymentFile.__table__.create(bind=engine)
        PaymentRecord.__table__.create(bind=engine)
        print("✅ Tables created!")
        
        # Verify
        print("⏳ Verifying...")
        with engine.connect() as conn:
            result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
            tables = [row[0] for row in result]
            print(f"📊 Current Tables in DB: {tables}")
            
            if "payment_files" in tables and "payment_records" in tables:
                print("🎉 SUCCESS: Payment tables exist with new schema!")
            else:
                print("❌ ERROR: Payment tables are missing!")

    except Exception as e:
        print(f"❌ FATAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    recreate_payment_tables()
