"""
Content Calendar Router - Content calendar endpoints
"""
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/content", tags=["content"])


class ContentItemCreate(BaseModel):
    date: str  # YYYY-MM-DD format
    title: str
    type: str = "video"  # 'video' or 'photo'
    platforms: List[str] = Field(default_factory=list)  # List of platform names
    status: str = "To Shoot"
    visualIdea: Optional[str] = None


class ContentItemUpdate(BaseModel):
    date: Optional[str] = None
    title: Optional[str] = None
    type: Optional[str] = None
    platforms: Optional[List[str]] = None
    status: Optional[str] = None
    visualIdea: Optional[str] = None


@router.get("")
def get_content_items(
    date_from: str = None,
    date_to: str = None
):
    """Returns all content calendar items, optionally filtered by date range"""
    from database import SessionLocal, ContentItem
    
    db = SessionLocal()
    try:
        query = db.query(ContentItem).order_by(ContentItem.date.asc())
        
        # Filter by date range if provided
        if date_from:
            query = query.filter(ContentItem.date >= date_from)
        if date_to:
            query = query.filter(ContentItem.date <= date_to)
        
        items = query.all()
        
        result = []
        for item in items:
            # Parse platforms from JSON string
            try:
                platforms = json.loads(item.platforms) if item.platforms else []
            except:
                platforms = []
            
            result.append({
                "id": item.id,
                "date": item.date,
                "title": item.title,
                "type": item.content_type,
                "platforms": platforms,
                "status": item.status,
                "visualIdea": item.visual_idea,
                "created_at": item.created_at.isoformat() if item.created_at else None,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None
            })
        
        return {"data": result, "total": len(result)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch content items: {str(e)}")
    finally:
        db.close()


@router.post("")
def create_content_item(item: ContentItemCreate):
    """Create a new content calendar item"""
    from database import SessionLocal, ContentItem
    
    db = SessionLocal()
    try:
        new_item = ContentItem(
            date=item.date,
            title=item.title,
            content_type=item.type,
            platforms=json.dumps(item.platforms),
            status=item.status,
            visual_idea=item.visualIdea
        )
        
        db.add(new_item)
        db.commit()
        db.refresh(new_item)
        
        return {
            "id": new_item.id,
            "date": new_item.date,
            "title": new_item.title,
            "type": new_item.content_type,
            "platforms": item.platforms,
            "status": new_item.status,
            "visualIdea": new_item.visual_idea,
            "created_at": new_item.created_at.isoformat() if new_item.created_at else None
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create content item: {str(e)}")
    finally:
        db.close()


@router.put("/{item_id}")
def update_content_item(item_id: int, item_update: ContentItemUpdate):
    """Update an existing content calendar item"""
    from database import SessionLocal, ContentItem
    from datetime import datetime
    
    db = SessionLocal()
    try:
        item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Content item not found")
        
        # Update fields if provided
        if item_update.date is not None:
            item.date = item_update.date
        if item_update.title is not None:
            item.title = item_update.title
        if item_update.type is not None:
            item.content_type = item_update.type
        if item_update.platforms is not None:
            item.platforms = json.dumps(item_update.platforms)
        if item_update.status is not None:
            item.status = item_update.status
        if item_update.visualIdea is not None:
            item.visual_idea = item_update.visualIdea
        
        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        
        # Parse platforms for response
        try:
            platforms = json.loads(item.platforms) if item.platforms else []
        except:
            platforms = []
        
        return {
            "id": item.id,
            "date": item.date,
            "title": item.title,
            "type": item.content_type,
            "platforms": platforms,
            "status": item.status,
            "visualIdea": item.visual_idea,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update content item: {str(e)}")
    finally:
        db.close()


@router.delete("/{item_id}")
def delete_content_item(item_id: int):
    """Delete a content calendar item permanently"""
    from database import SessionLocal, ContentItem
    
    db = SessionLocal()
    try:
        item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Content item not found")
        
        db.delete(item)
        db.commit()
        
        return {"message": "Content item deleted successfully", "id": item_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete content item: {str(e)}")
    finally:
        db.close()


@router.patch("/{item_id}/move")
def move_content_item(item_id: int, new_date: str):
    """Move a content item to a new date (for drag & drop)"""
    from database import SessionLocal, ContentItem
    from datetime import datetime
    
    db = SessionLocal()
    try:
        item = db.query(ContentItem).filter(ContentItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Content item not found")
        
        item.date = new_date
        item.updated_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Content item moved", "id": item_id, "new_date": new_date}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to move content item: {str(e)}")
    finally:
        db.close()
