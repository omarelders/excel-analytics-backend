"""
Payments Router - Payment processing endpoints
"""
import os
import uuid
import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException

router = APIRouter(prefix="/payments", tags=["payments"])

# Configuration
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = [".xlsx"]


@router.get("/files")
def get_payment_files():
    """Returns list of all uploaded payment files for grid display"""
    from database import SessionLocal, PaymentFile
    
    db = SessionLocal()
    try:
        files = db.query(PaymentFile).order_by(PaymentFile.upload_date.desc()).all()
        return {
            "files": [
                {
                    "id": f.id,
                    "filename": f.filename,
                    "upload_date": str(f.upload_date) if f.upload_date else None,
                    "record_count": f.record_count
                }
                for f in files
            ]
        }
    finally:
        db.close()


@router.delete("/files/{file_id}")
def delete_payment_file(file_id: int):
    """Delete a payment file and all its records"""
    from database import SessionLocal, PaymentFile, PaymentRecord
    
    db = SessionLocal()
    try:
        # Check if file exists
        file = db.query(PaymentFile).filter(PaymentFile.id == file_id).first()
        if not file:
            raise HTTPException(status_code=404, detail="Payment file not found")
        
        filename = file.filename
        
        # Delete all records for this file first
        deleted_records = db.query(PaymentRecord).filter(PaymentRecord.file_id == file_id).delete()
        
        # Delete the file record
        db.delete(file)
        db.commit()
        
        print(f"🗑️ Deleted payment file: {filename} ({deleted_records} records)")
        
        return {
            "status": "success",
            "message": f"Deleted {filename} and {deleted_records} records"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete: {str(e)}")
    finally:
        db.close()


@router.get("/files/{file_id}/data")
def get_payment_file_data(
    file_id: int,
    limit: int = 20,
    offset: int = 0,
    search: str = None
):
    """Returns records from a specific payment file with pagination, search, and stats"""
    from database import SessionLocal, PaymentFile, PaymentRecord
    from sqlalchemy import or_, func
    
    db = SessionLocal()
    try:
        # Check if file exists
        file = db.query(PaymentFile).filter(PaymentFile.id == file_id).first()
        if not file:
            raise HTTPException(status_code=404, detail="Payment file not found")
        
        # Base query
        query = db.query(PaymentRecord).filter(PaymentRecord.file_id == file_id)
        
        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    PaymentRecord.code.ilike(search_term),
                    PaymentRecord.recipient_name.ilike(search_term),
                    PaymentRecord.sender_name.ilike(search_term),
                    PaymentRecord.client_name.ilike(search_term),
                    PaymentRecord.reference_number.ilike(search_term),
                    PaymentRecord.description.ilike(search_term)
                )
            )
        
        # Get total count before pagination
        total_count = query.count()
        
        # Calculate totals for all matching records (before pagination)
        totals = db.query(
            func.sum(PaymentRecord.delivery_value).label('total_delivery_value'),
            func.sum(PaymentRecord.due_fees).label('total_due_fees'),
            func.sum(PaymentRecord.net_package_price).label('total_net_package_price'),
            func.sum(PaymentRecord.amount_due).label('total_amount_due')
        ).filter(PaymentRecord.file_id == file_id)
        
        if search:
            search_term = f"%{search}%"
            totals = totals.filter(
                or_(
                    PaymentRecord.code.ilike(search_term),
                    PaymentRecord.recipient_name.ilike(search_term),
                    PaymentRecord.sender_name.ilike(search_term),
                    PaymentRecord.client_name.ilike(search_term),
                    PaymentRecord.reference_number.ilike(search_term),
                    PaymentRecord.description.ilike(search_term)
                )
            )
        
        totals_result = totals.first()
        
        # Apply pagination
        records = query.order_by(PaymentRecord.id.desc()).offset(offset).limit(limit).all()
        
        result = []
        for r in records:
            result.append({
                "المستحق": r.amount_due,
                "الكود": r.code,
                "التاريخ": str(r.date) if r.date else None,
                "الحالة": r.status,
                "الفرع": r.branch,
                "فرع المنشأ": r.origin_branch,
                "الخدمة": r.service,
                "اسم الراسل": r.sender_name,
                "مدينة الراسل": r.sender_city,
                "منطقة الراسل": r.sender_area,
                "الرمز البريدي للراسل": r.sender_postal_code,
                "الرقم المرجعي": r.reference_number,
                "المستلم": r.recipient_name,
                "مدينة المستلم": r.recipient_city,
                "منطقة المستلم": r.recipient_area,
                "عنوان المستلم": r.recipient_address,
                "الرمز البريدي للمستلم": r.recipient_postal_code,
                "هاتف المستلم": r.recipient_phone,
                "موبايل المستلم": r.recipient_mobile,
                "الوصف": r.description,
                "الوزن": r.weight,
                "عدد القطع": r.pieces_count,
                "قيمة الطرد": r.package_value,
                "الرسوم": r.fees,
                "صافي سعر الطرد": r.net_package_price,
                "القيمة الإجمالية": r.total_value,
                "قيمة التسليم": r.delivery_value,
                "الرسوم المحصلة": r.collected_fees,
                "الرسوم المستحقة": r.due_fees,
                "نوع الدفع": r.payment_type,
                "نوع السعر": r.price_type,
                "نوع التسليم": r.delivery_type,
                "نوع المرتجع للراسل": r.return_type,
                "مندوب الشحن": r.shipping_agent,
                "تم التحصيل": r.is_collected,
                "تم السداد للعميل": r.paid_to_client,
                "ملاحظات": r.notes,
                "امكانية فتح الطرد": r.can_open_package,
                "العميل": r.client_name,
                "سبب الإرجاع": r.return_reason,
                "نوع الطلب": r.order_type,
                "تاريخ التسليم/الإلغاء": str(r.delivery_cancel_date) if r.delivery_cancel_date else None,
                "قيمة المرتجع": r.return_value,
                "عدد المحاولات": r.attempts_count,
                "تاريخ التوصيل": str(r.delivery_date) if r.delivery_date else None,
                "تم الإلغاء": r.is_cancelled,
                "تاريخ أخر حركة": str(r.last_movement_date) if r.last_movement_date else None,
                "سداد مستحقات العملاء": r.client_dues_payment
            })
        
        return {
            "file_id": file_id,
            "filename": file.filename,
            "total": total_count,
            "count": len(result),
            "limit": limit,
            "offset": offset,
            "totals": {
                "delivery_value": float(totals_result.total_delivery_value or 0),
                "due_fees": float(totals_result.total_due_fees or 0),
                "net_package_price": float(totals_result.total_net_package_price or 0),
                "amount_due": float(totals_result.total_amount_due or 0),
                "net_due": float(totals_result.total_delivery_value or 0) - float(totals_result.total_due_fees or 0)
            },
            "data": result
        }
    finally:
        db.close()


@router.post("/upload")
async def upload_payment_file(file: UploadFile = File(...)):
    """Upload and parse a payment Excel file"""
    from database import SessionLocal, PaymentFile, PaymentRecord
    from datetime import datetime
    import traceback
    
    print(f"\n{'='*50}")
    print(f"📤 PAYMENT UPLOAD STARTED: {file.filename}")
    print(f"{'='*50}")
    
    # 1. Validate file extension
    print("Step 1: Validating file extension...")
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        print(f"❌ Invalid file type: {file_ext}")
        raise HTTPException(status_code=400, detail=f"Invalid file type. Only {', '.join(ALLOWED_EXTENSIONS)} files are allowed.")
    print(f"✅ File extension OK: {file_ext}")
    
    # 2. Check file size
    print("Step 2: Checking file size...")
    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    print(f"   File size: {file_size_mb:.2f} MB")
    if file_size_mb > MAX_FILE_SIZE_MB:
        print(f"❌ File too large")
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.")
    print("✅ File size OK")
    
    # 3. Save file to disk
    print("Step 3: Saving file to disk...")
    unique_id = str(uuid.uuid4())[:8]
    safe_filename = f"payment_{unique_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(contents)
        print(f"✅ File saved: {file_path}")
    except Exception as e:
        print(f"❌ Failed to save file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # 4. Parse Excel
    print("Step 4: Parsing Excel file...")
    try:
        df = pd.read_excel(file_path)
        print(f"✅ Excel parsed: {len(df)} rows, {len(df.columns)} columns")
        print(f"   Columns: {list(df.columns)[:5]}... (showing first 5)")
    except Exception as e:
        print(f"❌ Failed to parse Excel: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse Excel: {str(e)}")
    
    # 5. Save to database
    print("Step 5: Saving to database...")
    db = SessionLocal()
    try:
        # Create payment file record
        print("   Creating PaymentFile record...")
        payment_file = PaymentFile(
            filename=file.filename,
            record_count=len(df)
        )
        db.add(payment_file)
        db.flush()
        print(f"✅ PaymentFile created with ID: {payment_file.id}")
        
        # Column mapping (Arabic to model attribute) - ALL 48 columns
        column_map = {
            "المستحق": "amount_due",
            "الكود": "code",
            "التاريخ": "date",
            "الحالة": "status",
            "الفرع": "branch",
            "فرع المنشأ": "origin_branch",
            "الخدمة": "service",
            "اسم الراسل": "sender_name",
            "مدينة الراسل": "sender_city",
            "منطقة الراسل": "sender_area",
            "الرمز البريدي للراسل": "sender_postal_code",
            "الرقم المرجعي": "reference_number",
            "المستلم": "recipient_name",
            "مدينة المستلم": "recipient_city",
            "منطقة المستلم": "recipient_area",
            "عنوان المستلم": "recipient_address",
            "الرمز البريدي للمستلم": "recipient_postal_code",
            "هاتف المستلم": "recipient_phone",
            "موبايل المستلم": "recipient_mobile",
            "الوصف": "description",
            "الوزن": "weight",
            "عدد القطع": "pieces_count",
            "قيمة الطرد": "package_value",
            "الرسوم": "fees",
            "صافي سعر الطرد": "net_package_price",
            "القيمة الإجمالية": "total_value",
            "قيمة التسليم": "delivery_value",
            "الرسوم المحصلة": "collected_fees",
            "الرسوم المستحقة": "due_fees",
            "نوع الدفع": "payment_type",
            "نوع السعر": "price_type",
            "نوع التسليم": "delivery_type",
            "نوع المرتجع للراسل": "return_type",
            "مندوب الشحن": "shipping_agent",
            "تم التحصيل": "is_collected",
            "تم السداد للعميل": "paid_to_client",
            "ملاحظات": "notes",
            "امكانية فتح الطرد": "can_open_package",
            "العميل": "client_name",
            "سبب الإرجاع": "return_reason",
            "نوع الطلب": "order_type",
            "تاريخ التسليم/الإلغاء": "delivery_cancel_date",
            "قيمة المرتجع": "return_value",
            "عدد المحاولات": "attempts_count",
            "تاريخ التوصيل": "delivery_date",
            "تم الإلغاء": "is_cancelled",
            "تاريخ أخر حركة": "last_movement_date",
            "سداد مستحقات العملاء": "client_dues_payment"
        }
        
        # Date columns that need special handling
        date_columns = {"date", "delivery_cancel_date", "delivery_date", "last_movement_date"}
        
        # Insert records
        print(f"   Inserting {len(df)} records...")
        for idx, row in df.iterrows():
            record_data = {"file_id": payment_file.id}
            
            for arabic_col, attr_name in column_map.items():
                if arabic_col in df.columns:
                    value = row[arabic_col]
                    
                    # Handle NaN values
                    if pd.isna(value):
                        value = None
                    # Handle date columns - convert to None if not a valid date
                    elif attr_name in date_columns and value is not None:
                        try:
                            if isinstance(value, str):
                                # Try to parse string date
                                value = pd.to_datetime(value)
                            elif not isinstance(value, (datetime, pd.Timestamp)):
                                value = None
                        except:
                            value = None
                    # Convert numpy types to Python types
                    elif hasattr(value, 'item'):
                        value = value.item()
                    
                    record_data[attr_name] = value
            
            try:
                record = PaymentRecord(**record_data)
                db.add(record)
            except Exception as e:
                print(f"❌ Error on row {idx}: {e}")
                print(f"   Data: {record_data}")
                raise
            
            # Progress every 100 rows
            if (idx + 1) % 100 == 0:
                print(f"   Processed {idx + 1}/{len(df)} rows...")
        
        print("   Committing to database...")
        db.commit()
        print(f"✅ SUCCESS! Inserted {len(df)} records")
        
        return {
            "filename": file.filename,
            "status": "success",
            "message": "Payment file uploaded successfully!",
            "file_id": payment_file.id,
            "rows_inserted": len(df)
        }
        
    except Exception as e:
        db.rollback()
        print(f"❌ DATABASE ERROR: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        db.close()
