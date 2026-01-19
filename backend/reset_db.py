from database import engine, Base, UploadedFile, Shipment
from sqlalchemy import text

def reset_database():
    print("⏳ Connecting to database...")
    try:
        # 1. Test Connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ Connected!")

        # 2. Drop Tables
        print("⏳ Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        print("✅ Tables dropped!")

        # 3. Create Tables
        print("⏳ Creating tables...")
        Base.metadata.create_all(bind=engine)
        print("✅ Tables created!")
        
        # 4. Verify
        print("⏳ Verifying...")
        with engine.connect() as conn:
            # Check if tables exist in information_schema
            result = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
            tables = [row[0] for row in result]
            print(f"📊 Current Tables in DB: {tables}")
            
            if "uploaded_files" in tables and "shipments" in tables:
                print("🎉 SUCCESS: Both tables exist!")
            else:
                print("❌ ERROR: Tables are missing!")

    except Exception as e:
        print(f"❌ FATAL ERROR: {str(e)}")

if __name__ == "__main__":
    reset_database()
