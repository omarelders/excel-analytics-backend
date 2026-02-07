"""
Clear all shipments data and re-upload fresh.
This allows the نوع السعر column to be populated.
"""
from database import SessionLocal, Shipment, UploadedFile

def clear_all_data():
    db = SessionLocal()
    try:
        # Delete all shipments
        deleted_shipments = db.query(Shipment).delete()
        # Delete all upload records
        deleted_files = db.query(UploadedFile).delete()
        db.commit()
        print(f"✅ Deleted {deleted_shipments} shipments")
        print(f"✅ Deleted {deleted_files} upload records")
        print("\nNow re-upload your Excel file to populate نوع السعر!")
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    confirm = input("This will DELETE ALL data. Type 'yes' to confirm: ")
    if confirm.lower() == 'yes':
        clear_all_data()
    else:
        print("Cancelled.")
