import shutil
import os
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from constants import CHANGEABLE_STATUSES, TARGET_STATUSES, ALL_STATUSES, STATUS_COLORS

app = FastAPI(title="Gold Road API")

@app.on_event("startup")
def on_startup():
    from database import create_tables
    create_tables()

# CORS Configuration - allows frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins like ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create 'uploads' folder if it doesn't exist
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Configuration
MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = [".xlsx"]

@app.get("/health")
def read_health():
    return {"status": "ok"}

@app.get("/statuses")
def get_statuses():
    """Returns all status constants for frontend use - single source of truth"""
    return {
        "changeable_statuses": CHANGEABLE_STATUSES,
        "target_statuses": TARGET_STATUSES,
        "all_statuses": ALL_STATUSES,
        "status_colors": STATUS_COLORS
    }

@app.get("/shipments")
def get_shipments(
    limit: int = 20,
    offset: int = 0,
    search: str = None,
    status: str = None
):
    from database import SessionLocal, Shipment
    from sqlalchemy import or_
    
    db = SessionLocal()
    try:
        # Base query
        query = db.query(Shipment)
        
        # Apply search filter (searches code, client, recipient)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Shipment.shipment_code.ilike(search_term),
                    Shipment.client_name.ilike(search_term),
                    Shipment.recipient_name.ilike(search_term)
                )
            )
        
        # Apply status filter
        if status:
            query = query.filter(Shipment.status == status)
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination
        shipments = query.order_by(Shipment.id.desc()).offset(offset).limit(limit).all()
        
        result = []
        for s in shipments:
            result.append({
                "الكود": s.shipment_code,
                "التاريخ": str(s.date) if s.date else None,
                "العميل": s.client_name,
                "الوصف": s.description,
                "الحالة": s.status,
                "المستلم": s.recipient_name,
                "مدينة المستلم": s.recipient_city,
                "قيمة الطرد": s.amount,
                "نوع السعر": s.price_type,
                "الوزن": s.weight
            })
        
        return {
            "data": result,
            "count": len(result),
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    finally:
        db.close()

@app.delete("/shipments/{shipment_code}")
def delete_shipment(shipment_code: str):
    """Delete a specific shipment by its code."""
    from database import SessionLocal, Shipment
    
    db = SessionLocal()
    try:
        shipment = db.query(Shipment).filter(Shipment.shipment_code == shipment_code).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        db.delete(shipment)
        db.commit()
        return {"message": "Shipment deleted successfully", "deleted_code": shipment_code}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete shipment: {str(e)}")
    finally:
        db.close()

@app.get("/shipments/days")
def get_shipping_days():
    """Returns list of unique shipping dates (most recent first)"""
    from database import SessionLocal, Shipment
    from sqlalchemy import func
    
    db = SessionLocal()
    try:
        dates = db.query(func.distinct(func.date(Shipment.date)))\
            .filter(Shipment.date.isnot(None))\
            .order_by(func.date(Shipment.date).desc())\
            .limit(30)\
            .all()
        
        return {"days": [str(d[0]) for d in dates if d[0]]}
    finally:
        db.close()

@app.get("/shipments/by-day")
def get_shipments_by_day(date: str):
    """Returns all orders for a specific date (YYYY-MM-DD format)"""
    from database import SessionLocal, Shipment
    from sqlalchemy import func
    from datetime import datetime
    
    db = SessionLocal()
    try:
        # Parse the date
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
        
        # Query shipments for that date
        shipments = db.query(Shipment)\
            .filter(func.date(Shipment.date) == target_date)\
            .order_by(Shipment.id.desc())\
            .all()
        
        result = []
        for s in shipments:
            result.append({
                "الكود": s.shipment_code,
                "التاريخ": str(s.date) if s.date else None,
                "العميل": s.client_name,
                "الوصف": s.description,
                "الحالة": s.status,
                "المستلم": s.recipient_name,
                "مدينة المستلم": s.recipient_city,
                "قيمة الطرد": s.amount,
                "نوع السعر": s.price_type,
                "الوزن": s.weight
            })
        
        return {
            "date": date,
            "count": len(result),
            "data": result
        }
    finally:
        db.close()

@app.get("/shipments/search")
def search_shipments_global(query: str, limit: int = 50):
    """Search shipments across all days by code, client, recipient, or description"""
    from database import SessionLocal, Shipment
    from sqlalchemy import or_
    
    if not query or len(query) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters")
    
    db = SessionLocal()
    try:
        search_term = f"%{query}%"
        shipments = db.query(Shipment)\
            .filter(
                or_(
                    Shipment.shipment_code.ilike(search_term),
                    Shipment.client_name.ilike(search_term),
                    Shipment.recipient_name.ilike(search_term),
                    Shipment.description.ilike(search_term)
                )
            )\
            .order_by(Shipment.date.desc())\
            .limit(limit)\
            .all()
        
        result = []
        for s in shipments:
            result.append({
                "الكود": s.shipment_code,
                "التاريخ": str(s.date) if s.date else None,
                "العميل": s.client_name,
                "الوصف": s.description,
                "الحالة": s.status,
                "المستلم": s.recipient_name,
                "مدينة المستلم": s.recipient_city,
                "قيمة الطرد": s.amount,
                "نوع السعر": s.price_type,
                "الوزن": s.weight
            })
        
        return {
            "query": query,
            "count": len(result),
            "data": result
        }
    finally:
        db.close()

@app.get("/shipments/autocomplete")
def autocomplete_shipments(query: str, limit: int = 10):
    """
    Autocomplete search for code, client, recipient, and city.
    Returns categorized suggestions.
    """
    from database import SessionLocal, Shipment
    from sqlalchemy import or_, text

    if not query:
        return {"suggestions": [], "categories": {}}

    db = SessionLocal()
    try:
        search_pattern = f"%{query}%"
        
        # We need to find distinct values for each category that match the query
        # This is a bit more complex than a simple search
        
        suggestions = []
        categories = {}
        
        # Helper to add suggestions
        def add_suggestions(field, type_name, label, icon_name="Package"):
            results = db.query(getattr(Shipment, field))\
                .filter(getattr(Shipment, field).ilike(search_pattern))\
                .distinct()\
                .limit(5)\
                .all()
            
            count = 0
            for r in results:
                val = r[0]
                if val:
                    suggestions.append({
                        "value": str(val),
                        "type": type_name,
                        "count": "" # We could get count if needed
                    })
                    count += 1
            if count > 0:
                categories[type_name] = {
                    "label": label,
                    "count": count
                }

        # 1. Code
        add_suggestions("shipment_code", "code", "الكود")
        
        # 2. Client
        add_suggestions("client_name", "client", "العميل")
        
        # 3. Recipient
        add_suggestions("recipient_name", "recipient", "المستلم")
        
        # 4. City (recipient_city)
        add_suggestions("recipient_city", "city", "المدينة")
        
        return {
            "query": query,
            "suggestions": suggestions,
            "categories": categories
        }
    except Exception as e:
        print(f"Autocomplete error: {e}")
        return {"suggestions": [], "categories": {}}
    finally:
        db.close()


@app.get("/api/analytics")
def get_analytics():
    """
    aggregated analytics data for the dashboard:
    - Status distribution
    - Top cities
    - Daily trend
    - Summary stats
    """
    from database import SessionLocal, Shipment
    from sqlalchemy import func, desc
    
    db = SessionLocal()
    try:
        # 1. Summary Stats
        total_shipments = db.query(Shipment).count()
        
        # Total Value (sum of amount)
        total_value = db.query(func.sum(Shipment.amount)).scalar() or 0
        
        # Delivered Count
        delivered_count = db.query(Shipment).filter(Shipment.status == 'تم التسليم').count()
        
        # Delivery Rate
        delivery_rate = 0
        if total_shipments > 0:
            delivery_rate = round((delivered_count / total_shipments) * 100, 1)
            
        # Top Client
        top_client_data = db.query(
            Shipment.client_name, 
            func.count(Shipment.id).label('count')
        ).group_by(Shipment.client_name).order_by(desc('count')).first()
        
        # 2. Status Distribution
        status_dist = db.query(
            Shipment.status,
            func.count(Shipment.id).label('count')
        ).group_by(Shipment.status).all()
        
        status_distribution = [
            {"status": s[0], "count": s[1]} for s in status_dist if s[0]
        ]
        
        # 3. Top Cities
        cities_dist = db.query(
            Shipment.recipient_city,
            func.count(Shipment.id).label('count')
        ).filter(Shipment.recipient_city.isnot(None))\
         .group_by(Shipment.recipient_city)\
         .order_by(desc('count'))\
         .limit(10)\
         .all()
         
        top_cities = [
            {"city": c[0], "count": c[1]} for c in cities_dist
        ]
        
        # 4. Daily Trends (Last 30 days)
        daily_trends_data = db.query(
            func.date(Shipment.date).label('date'),
            func.count(Shipment.id).label('count')
        ).filter(Shipment.date.isnot(None))\
         .group_by(func.date(Shipment.date))\
         .order_by(func.date(Shipment.date))\
         .limit(30)\
         .all()
         
        daily_trends = [
            {"date": str(d[0]), "count": d[1]} for d in daily_trends_data
        ]

        return {
            "summary": {
                "total_shipments": total_shipments,
                "total_value": total_value,
                "delivery_rate": delivery_rate,
                "delivered_count": delivered_count,
                "top_client": top_client_data[0] if top_client_data else None,
                "top_client_count": top_client_data[1] if top_client_data else 0
            },
            "status_distribution": status_distribution,
            "top_cities": top_cities,
            "daily_trends": daily_trends
        }
    except Exception as e:
        print(f"Analytics Error: {e}")
        return {
            "summary": {},
            "status_distribution": [],
            "top_cities": [],
            "daily_trends": []
        }
    finally:
        db.close()


@app.patch("/shipments/{shipment_code}/status")
def update_shipment_status(shipment_code: str, new_status: str):
    """Update the status of a shipment. Only allows specific status transitions."""
    from database import SessionLocal, Shipment
    
    # Use centralized constants
    if new_status not in TARGET_STATUSES:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid target status. Allowed: {', '.join(TARGET_STATUSES)}"
        )
    
    db = SessionLocal()
    try:
        # Find the shipment
        shipment = db.query(Shipment).filter(Shipment.shipment_code == shipment_code).first()
        
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        # Check if current status allows update
        if shipment.status not in CHANGEABLE_STATUSES:
            raise HTTPException(
                status_code=400, 
                detail=f"Cannot change status from '{shipment.status}'. Only orders with status '{', '.join(CHANGEABLE_STATUSES)}' can be updated."
            )
        
        # Update the status
        old_status = shipment.status
        shipment.status = new_status
        db.commit()
        
        return {
            "success": True,
            "shipment_code": shipment_code,
            "old_status": old_status,
            "new_status": new_status
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update status: {str(e)}")
    finally:
        db.close()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    # 1. Validate file extension
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Only {', '.join(ALLOWED_EXTENSIONS)} files are allowed.")
    
    # 2. Check file size (read content to check size)
    contents = await file.read()
    file_size_mb = len(contents) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB.")
    
    # 3. Generate unique filename to avoid overwrites
    unique_id = str(uuid.uuid4())[:8]
    safe_filename = f"{unique_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    # 4. Save the file to disk
    with open(file_path, "wb") as buffer:
        buffer.write(contents)
        
    # Parse the file
    try:
        from parser import parse_excel
        from database import SessionLocal
        import crud
        
        # 1. Parsing
        result = parse_excel(file_path)
        parsed_data = result["preview_data"] 
        
        # A) Get DB Session
        db = SessionLocal()
        try:
            # B) Save to DB
            result = crud.save_upload(db, file.filename, parsed_data)
            return {
                "file_id": result["file_id"],
                "filename": file.filename,
                "status": "success", 
                "message": "File uploaded and data inserted successfully!",
                "rows_inserted": result["inserted"],
                "duplicates_skipped": result["skipped_duplicates"]
            }
        finally:
            db.close()

    except Exception as e:
        return {"filename": file.filename, "status": "error", "message": f"Error processing file: {str(e)}"}



# ========== SHIPMENT FILES ENDPOINTS ==========

@app.get("/upload/files")
def get_uploaded_files():
    """Returns list of uploaded shipment files with record counts"""
    from database import SessionLocal, UploadedFile, Shipment
    from sqlalchemy import func
    
    db = SessionLocal()
    try:
        # distinct count of shipments per file
        # Using a subquery or join to get counts
        files = db.query(UploadedFile).order_by(UploadedFile.upload_date.desc()).all()
        
        result = []
        for f in files:
            count = db.query(func.count(Shipment.id)).filter(Shipment.file_id == f.id).scalar()
            result.append({
                "id": f.id,
                "filename": f.filename,
                "upload_date": str(f.upload_date) if f.upload_date else None,
                "record_count": count or 0
            })
            
        return {"files": result}
    finally:
        db.close()

@app.delete("/upload/files/{file_id}")
def delete_uploaded_file(file_id: int):
    """Delete an uploaded file and all its shipments (cascading)"""
    from database import SessionLocal, UploadedFile
    
    db = SessionLocal()
    try:
        file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
            
        filename = file.filename
        db.delete(file) # Cascades to shipments due to relationship
        db.commit()
        
        return {"message": f"Deleted file {filename} and its shipments", "file_id": file_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")
    finally:
        db.close()

@app.get("/shipments/file/{file_id}")
def get_shipments_by_file(
    file_id: int,
    limit: int = 50,
    offset: int = 0,
    search: str = None
):
    """Get shipments belonging to a specific file"""
    from database import SessionLocal, Shipment, UploadedFile
    from sqlalchemy import or_
    
    db = SessionLocal()
    try:
        # Check if file exists
        file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
            
        query = db.query(Shipment).filter(Shipment.file_id == file_id)
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Shipment.shipment_code.ilike(search_term),
                    Shipment.client_name.ilike(search_term),
                    Shipment.recipient_name.ilike(search_term)
                )
            )
            
        total_count = query.count()
        shipments = query.order_by(Shipment.id.asc()).offset(offset).limit(limit).all()
        
        result = []
        for s in shipments:
            result.append({
                "الكود": s.shipment_code,
                "التاريخ": str(s.date) if s.date else None,
                "العميل": s.client_name,
                "الوصف": s.description,
                "الحالة": s.status,
                "المستلم": s.recipient_name,
                "مدينة المستلم": s.recipient_city,
                "قيمة الطرد": s.amount,
                "نوع السعر": s.price_type,
                "الوزن": s.weight
            })
            
        return {
            "file_id": file_id,
            "filename": file.filename,
            "data": result,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    finally:
        db.close()


# ========== PAYMENT PROCESSING ENDPOINTS ==========

@app.get("/payments/files")
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


@app.delete("/payments/files/{file_id}")
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


@app.get("/payments/files/{file_id}/data")
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


@app.post("/payments/upload")
async def upload_payment_file(file: UploadFile = File(...)):
    """Upload and parse a payment Excel file"""
    import pandas as pd
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


