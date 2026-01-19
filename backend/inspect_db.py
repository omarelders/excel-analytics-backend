from sqlalchemy import inspect
from database import engine

def check_columns():
    inspector = inspect(engine)
    columns = inspector.get_columns('shipments')
    print("--- 🔍 Shipments Table Columns ---")
    for col in columns:
        print(f"✅ {col['name']}")

if __name__ == "__main__":
    check_columns()
