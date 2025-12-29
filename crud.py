from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from database import UploadedFile, Shipment
from datetime import datetime
import pandas as pd

def save_upload(db: Session, filename: str, data: list):
    """
    Saves upload record and shipments to database.
    Uses transaction to ensure all-or-nothing insertion.
    Skips duplicate shipments based on shipment_code.
    Skips rows where status is 'تم التسليم' (Delivered).
    """
    # 1. Create the File Record
    db_file = UploadedFile(filename=filename)
    db.add(db_file)
    db.flush()  # Get the ID without committing yet
    
    # 2. Prepare Shipments (with duplicate and delivered detection)
    shipments_to_insert = []
    skipped_duplicates = 0
    skipped_delivered = 0
    
    # Get existing shipment codes to check for duplicates
    existing_codes = set(
        code[0] for code in db.query(Shipment.shipment_code).all() if code[0]
    )
    
    for row in data:
        # Skip rows where status is "تم التسليم" (Delivered)
        if row.get("الحالة") == "تم التسليم":
            skipped_delivered += 1
            continue
        
        shipment_code = row.get("الكود")
        
        # Skip if shipment code is missing (prevents empty rows)
        if not shipment_code:
            continue
            
        # Skip if this shipment code already exists in DB
        if shipment_code and shipment_code in existing_codes:
            skipped_duplicates += 1
            continue
        
        # Add to existing codes set to catch duplicates within same file
        if shipment_code:
            existing_codes.add(shipment_code)
        
        shipment = Shipment(
            file_id=db_file.id,
            
            # Core Info
            shipment_code=shipment_code,
            date=parse_date(row.get("التاريخ")),
            client_name=row.get("العميل"),
            branch_name=row.get("الفرع"),
            status=row.get("الحالة"),
            
            # Sender
            sender_name=row.get("اسم الراسل"),
            sender_city=row.get("مدينة الراسل"),
            
            # Recipient
            recipient_name=row.get("المستلم"),
            recipient_city=row.get("مدينة المستلم"),
            recipient_area=row.get("منطقة المستلم"),
            recipient_address=row.get("عنوان المستلم"),
            recipient_phone=clean_str(row.get("هاتف المستلم")),
            recipient_mobile=clean_str(row.get("موبايل المستلم")),
            
            # Financials
            amount=clean_float(row.get("قيمة الطرد")),
            shipping_fee=clean_float(row.get("الرسوم")),
            net_price=clean_float(row.get("صافي سعر الطرد")),
            total_value=clean_float(row.get("القيمة الإجمالية")),
            price_type=row.get("نوع السعر"),
            
            # Logistics
            weight=clean_float(row.get("الوزن")),
            pieces_count=clean_int(row.get("عدد القطع")),
            description=row.get("الوصف"),
            notes=row.get("ملاحظات")
        )
        shipments_to_insert.append(shipment)
    
    # 3. Check if any valid shipments remain
    if len(shipments_to_insert) == 0:
        db.rollback()
        raise Exception("No valid shipments to upload. All rows are either delivered or duplicates.")
    
    # 4. Bulk Insert with transaction safety
    try:
        db.add_all(shipments_to_insert)
        db.commit()  # Commits both file record and all shipments atomically
    except Exception as e:
        db.rollback()  # Rollback everything if anything fails
        raise Exception(f"Database error: {str(e)}. All changes rolled back.")
    
    return {
        "file_id": db_file.id,
        "inserted": len(shipments_to_insert),
        "skipped_duplicates": skipped_duplicates,
        "skipped_delivered": skipped_delivered
    }



def parse_date(date_val):
    """
    Robustly parse date from various formats.
    Handles: pandas Timestamp, datetime, string dates.
    """
    if date_val is None:
        return None
    
    # Already a datetime
    if isinstance(date_val, datetime):
        return date_val
    
    # Pandas Timestamp
    if isinstance(date_val, pd.Timestamp):
        return date_val.to_pydatetime()
    
    # String date - try common formats
    if isinstance(date_val, str):
        date_formats = [
            "%Y-%m-%d %H:%M:%S",  # 2025-12-28 18:42:52
            "%Y-%m-%d",           # 2025-12-28
            "%d-%m-%Y %H:%M:%S",  # 28-12-2025 18:42:52
            "%d-%m-%Y",           # 28-12-2025
            "%d/%m/%Y %H:%M:%S",  # 28/12/2025 18:42:52
            "%d/%m/%Y",           # 28/12/2025
        ]
        for fmt in date_formats:
            try:
                return datetime.strptime(date_val, fmt)
            except ValueError:
                continue
        # If no format matched, return None
        return None
    
    # Unknown type, return None
    return None


def clean_float(val):
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def clean_int(val):
    if val is None:
        return 0
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def clean_str(val):
    if val is None:
        return None
    return str(val)
