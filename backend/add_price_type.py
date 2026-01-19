"""
Add the 'نوع السعر' column to the shipments table.
Run this script once to update the database schema.
"""
from database import engine
from sqlalchemy import text

def add_price_type_column():
    with engine.connect() as conn:
        try:
            # Add the new column if it doesn't exist
            conn.execute(text("""
                ALTER TABLE shipments 
                ADD COLUMN IF NOT EXISTS "نوع السعر" VARCHAR;
            """))
            conn.commit()
            print("✅ Column 'نوع السعر' added successfully!")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    add_price_type_column()
