"""
Shipments Router - All shipment-related endpoints
"""
import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from constants import CHANGEABLE_STATUSES, TARGET_STATUSES
from dependencies import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

# Configuration
UPLOAD_DIR = "uploads"
MAX_FILE_SIZE_MB = 10
ALLOWED_EXTENSIONS = [".xlsx"]


@router.get("/shipments")
def get_shipments(
    limit: int = 20,
    offset: int = 0,
    search: str = None,
    status: str = None,
    date_from: str = None,
    date_to: str = None
):
    from database import SessionLocal, Shipment
    from sqlalchemy import or_, func
    from datetime import datetime
    
    db = SessionLocal()
    try:
        # Base query - exclude soft deleted records
        query = db.query(Shipment).filter(Shipment.is_deleted == False)
        
        # Apply search filter (searches code, client, recipient, city, description)
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Shipment.shipment_code.ilike(search_term),
                    Shipment.client_name.ilike(search_term),
                    Shipment.recipient_name.ilike(search_term),
                    Shipment.recipient_city.ilike(search_term),
                    Shipment.description.ilike(search_term)
                )
            )
        
        # Apply status filter
        if status:
            query = query.filter(Shipment.status == status)
        
        # Apply date filters
        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(func.date(Shipment.date) >= from_date)
            except ValueError:
                pass  # Invalid date format, skip filter
        
        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                query = query.filter(func.date(Shipment.date) <= to_date)
            except ValueError:
                pass  # Invalid date format, skip filter
        
        # Get total count before pagination
        total_count = query.count()
        
        # Apply pagination - Sort by Date desc, then ID desc (for consistency)
        shipments = query.order_by(Shipment.date.desc(), Shipment.id.desc()).offset(offset).limit(limit).all()
        
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


@router.delete("/shipments/{shipment_code}")
def delete_shipment(shipment_code: str):
    """Soft delete a specific shipment by its code."""
    from database import SessionLocal, Shipment
    from datetime import datetime
    
    db = SessionLocal()
    try:
        shipment = db.query(Shipment).filter(
            Shipment.shipment_code == shipment_code,
            Shipment.is_deleted == False
        ).first()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        # Soft delete instead of hard delete
        shipment.is_deleted = True
        shipment.deleted_at = datetime.utcnow()
        db.commit()
        return {"message": "Shipment deleted successfully", "deleted_code": shipment_code}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting shipment: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete shipment")
    finally:
        db.close()


@router.post("/shipments/{shipment_code}/restore")
def restore_shipment(shipment_code: str):
    """Restore a soft-deleted shipment."""
    from database import SessionLocal, Shipment
    
    db = SessionLocal()
    try:
        # Find the deleted shipment
        shipment = db.query(Shipment).filter(
            Shipment.shipment_code == shipment_code,
            Shipment.is_deleted == True
        ).first()
        
        if not shipment:
            raise HTTPException(status_code=404, detail="Deleted shipment not found")
        
        # Restore the shipment
        shipment.is_deleted = False
        shipment.deleted_at = None
        db.commit()
        
        return {"message": "Shipment restored successfully", "restored_code": shipment_code}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error restoring shipment: {e}")
        raise HTTPException(status_code=500, detail="Failed to restore shipment")
    finally:
        db.close()


@router.get("/shipments/deleted")
def get_deleted_shipments(limit: int = 50, offset: int = 0):
    """Returns list of soft-deleted shipments for recovery."""
    from database import SessionLocal, Shipment
    
    db = SessionLocal()
    try:
        query = db.query(Shipment).filter(Shipment.is_deleted == True)
        
        total_count = query.count()
        shipments = query.order_by(Shipment.deleted_at.desc()).offset(offset).limit(limit).all()
        
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
                "تاريخ الحذف": str(s.deleted_at) if s.deleted_at else None
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


@router.get("/shipments/days")
def get_shipping_days():
    """Returns list of unique shipping dates (most recent first)"""
    from database import SessionLocal, Shipment
    from sqlalchemy import func
    
    db = SessionLocal()
    try:
        dates = db.query(func.distinct(func.date(Shipment.date)))\
            .filter(Shipment.date.isnot(None))\
            .filter(Shipment.is_deleted == False)\
            .order_by(func.date(Shipment.date).desc())\
            .limit(100)\
            .all()
        
        return {"days": [str(d[0]) for d in dates if d[0]]}
    finally:
        db.close()


@router.get("/shipments/by-day")
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
        
        # Query shipments for that date (exclude deleted)
        shipments = db.query(Shipment)\
            .filter(func.date(Shipment.date) == target_date)\
            .filter(Shipment.is_deleted == False)\
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


@router.get("/shipments/search")
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
            .filter(Shipment.is_deleted == False)\
            .filter(
                or_(
                    Shipment.shipment_code.ilike(search_term),
                    Shipment.client_name.ilike(search_term),
                    Shipment.recipient_name.ilike(search_term),
                    Shipment.recipient_city.ilike(search_term),
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


@router.get("/shipments/autocomplete")
def autocomplete_shipments(query: str, limit: int = 10):
    """
    Autocomplete search for code, client, recipient, and city.
    Returns categorized suggestions.
    """
    from database import SessionLocal, Shipment

    if not query:
        return {"suggestions": [], "categories": {}}

    db = SessionLocal()
    try:
        search_pattern = f"%{query}%"
        
        suggestions = []
        categories = {}
        
        # Helper to add suggestions (exclude deleted)
        def add_suggestions(field, type_name, label, icon_name="Package"):
            results = db.query(getattr(Shipment, field))\
                .filter(Shipment.is_deleted == False)\
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
                        "count": ""
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


@router.get("/api/analytics")
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
        # 1. Summary Stats (exclude deleted)
        total_shipments = db.query(Shipment).filter(Shipment.is_deleted == False).count()
        
        # Total Value (sum of amount) - excluding returned orders (مرتجع) and deleted
        total_value = db.query(func.sum(Shipment.amount)).filter(
            Shipment.status != 'مرتجع',
            Shipment.is_deleted == False
        ).scalar() or 0
        
        # Delivered Count
        delivered_count = db.query(Shipment).filter(
            Shipment.status == 'تم التسليم',
            Shipment.is_deleted == False
        ).count()
        
        # Delivery Rate
        delivery_rate = 0
        if total_shipments > 0:
            delivery_rate = round((delivered_count / total_shipments) * 100, 1)
            
        # Top Client
        top_client_data = db.query(
            Shipment.client_name, 
            func.count(Shipment.id).label('count')
        ).filter(Shipment.is_deleted == False).group_by(Shipment.client_name).order_by(desc('count')).first()

        # Distinct totals for dashboard KPIs
        unique_clients = db.query(func.count(func.distinct(Shipment.client_name))).filter(
            Shipment.is_deleted == False,
            Shipment.client_name.isnot(None),
            Shipment.client_name != ''
        ).scalar() or 0

        unique_cities = db.query(func.count(func.distinct(Shipment.recipient_city))).filter(
            Shipment.is_deleted == False,
            Shipment.recipient_city.isnot(None),
            Shipment.recipient_city != ''
        ).scalar() or 0
        
        # 2. Status Distribution
        status_dist = db.query(
            Shipment.status,
            func.count(Shipment.id).label('count')
        ).filter(Shipment.is_deleted == False).group_by(Shipment.status).all()
        
        status_distribution = [
            {"status": s[0], "count": s[1]} for s in status_dist if s[0]
        ]
        
        # 3. Top Cities
        cities_dist = db.query(
            Shipment.recipient_city,
            func.count(Shipment.id).label('count')
        ).filter(Shipment.recipient_city.isnot(None))\
         .filter(Shipment.is_deleted == False)\
         .group_by(Shipment.recipient_city)\
         .order_by(desc('count'))\
         .limit(10)\
         .all()
         
        top_cities = [
            {"city": c[0], "count": c[1]} for c in cities_dist
        ]
        
        # 4. Daily Trends (Most recent 30 days)
        daily_trends_data = db.query(
            func.date(Shipment.date).label('date'),
            func.count(Shipment.id).label('count')
        ).filter(Shipment.date.isnot(None))\
         .filter(Shipment.is_deleted == False)\
         .group_by(func.date(Shipment.date))\
         .order_by(func.date(Shipment.date).desc())\
         .limit(30)\
         .all()

        # Return oldest->newest for chart rendering while still using latest 30 days.
        daily_trends_data = list(reversed(daily_trends_data))

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
                "top_client_count": top_client_data[1] if top_client_data else 0,
                "unique_clients": unique_clients,
                "unique_cities": unique_cities,
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


@router.patch("/shipments/{shipment_code}/status")
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
        # Find the shipment (exclude deleted)
        shipment = db.query(Shipment).filter(
            Shipment.shipment_code == shipment_code,
            Shipment.is_deleted == False
        ).first()
        
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
        print(f"Error updating status: {e}")
        raise HTTPException(status_code=500, detail="Failed to update status")
    finally:
        db.close()


@router.patch("/shipments/{shipment_code}")
def update_shipment(shipment_code: str, amount: float = None, description: str = None):
    """Update shipment amount and/or description."""
    from database import SessionLocal, Shipment
    
    # Validate that at least one field is provided
    if amount is None and description is None:
        raise HTTPException(
            status_code=400, 
            detail="At least one field (amount or description) must be provided"
        )
    
    db = SessionLocal()
    try:
        # Find the shipment (exclude deleted)
        shipment = db.query(Shipment).filter(
            Shipment.shipment_code == shipment_code,
            Shipment.is_deleted == False
        ).first()
        
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")
        
        # Track what was updated
        updated_fields = []
        
        # Update amount if provided
        if amount is not None:
            shipment.amount = amount
            updated_fields.append("amount")
        
        # Update description if provided
        if description is not None:
            shipment.description = description
            updated_fields.append("description")
        
        db.commit()
        
        return {
            "success": True,
            "shipment_code": shipment_code,
            "updated_fields": updated_fields,
            "message": f"Successfully updated: {', '.join(updated_fields)}"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error updating shipment: {e}")
        raise HTTPException(status_code=500, detail="Failed to update shipment")
    finally:
        db.close()


@router.post("/upload")
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
        print(f"Error processing file: {e}")
        return {"filename": file.filename, "status": "error", "message": "Error processing file"}


# ========== SHIPMENT FILES ENDPOINTS ==========

@router.get("/upload/files")
def get_uploaded_files():
    """Returns list of uploaded shipment files with record counts"""
    from database import SessionLocal, UploadedFile, Shipment
    from sqlalchemy import func
    
    db = SessionLocal()
    try:
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


@router.delete("/upload/files/{file_id}")
def delete_uploaded_file(file_id: int):
    """Delete an uploaded file and all its shipments (cascading)"""
    from database import SessionLocal, UploadedFile
    
    db = SessionLocal()
    try:
        file = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
            
        filename = file.filename
        db.delete(file)  # Cascades to shipments due to relationship
        db.commit()
        
        return {"message": f"Deleted file {filename} and its shipments", "file_id": file_id}
    except Exception as e:
        db.rollback()
        print(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete file")
    finally:
        db.close()


@router.get("/shipments/file/{file_id}")
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
            
        query = db.query(Shipment).filter(
            Shipment.file_id == file_id,
            Shipment.is_deleted == False
        )
        
        if search:
            search_term = f"%{search}%"
            query = query.filter(
                or_(
                    Shipment.shipment_code.ilike(search_term),
                    Shipment.client_name.ilike(search_term),
                    Shipment.recipient_name.ilike(search_term),
                    Shipment.recipient_city.ilike(search_term),
                    Shipment.description.ilike(search_term)
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
