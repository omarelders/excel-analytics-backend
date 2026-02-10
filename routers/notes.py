"""
Notes Router - Notes/Ideas endpoints
"""
import base64
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from dependencies import get_current_user

router = APIRouter(prefix="/api/notes", tags=["notes"], dependencies=[Depends(get_current_user)])


class NoteCreate(BaseModel):
    title: str
    content: Optional[str] = None
    audio_data: Optional[str] = None  # Base64 encoded audio
    audio_duration: Optional[float] = None
    note_type: str = "text"  # 'text' or 'voice'
    color: str = "yellow"


class NoteUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    audio_data: Optional[str] = None
    audio_duration: Optional[float] = None
    color: Optional[str] = None


@router.get("")
def get_notes(
    favorites_only: bool = False,
    limit: int = 100,
    offset: int = 0
):
    """Returns list of all notes with optional favorites filter"""
    from database import SessionLocal, Note
    
    db = SessionLocal()
    try:
        query = db.query(Note)
        
        if favorites_only:
            query = query.filter(Note.is_favorite == True)
        
        total_count = query.count()
        notes = query.order_by(Note.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for note in notes:
            note_data = {
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "note_type": note.note_type,
                "color": note.color,
                "is_favorite": note.is_favorite,
                "audio_duration": note.audio_duration,
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "updated_at": note.updated_at.isoformat() if note.updated_at else None
            }
            # Include audio data as base64 for voice notes
            if note.note_type == "voice" and note.audio_data:
                note_data["audio_data"] = base64.b64encode(note.audio_data).decode('utf-8')
            result.append(note_data)
        
        return {
            "data": result,
            "count": len(result),
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    finally:
        db.close()


@router.post("")
def create_note(note: NoteCreate):
    """Create a new note (text or voice)"""
    from database import SessionLocal, Note
    from datetime import datetime
    
    db = SessionLocal()
    try:
        # Prepare audio data if present
        audio_bytes = None
        if note.audio_data:
            try:
                audio_bytes = base64.b64decode(note.audio_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid audio data: {str(e)}")
        
        new_note = Note(
            title=note.title,
            content=note.content,
            audio_data=audio_bytes,
            audio_duration=note.audio_duration,
            note_type=note.note_type,
            color=note.color,
            is_favorite=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_note)
        db.commit()
        db.refresh(new_note)
        
        response_data = {
            "id": new_note.id,
            "title": new_note.title,
            "content": new_note.content,
            "note_type": new_note.note_type,
            "color": new_note.color,
            "is_favorite": new_note.is_favorite,
            "audio_duration": new_note.audio_duration,
            "created_at": new_note.created_at.isoformat() if new_note.created_at else None,
            "updated_at": new_note.updated_at.isoformat() if new_note.updated_at else None
        }
        
        if new_note.note_type == "voice" and new_note.audio_data:
            response_data["audio_data"] = base64.b64encode(new_note.audio_data).decode('utf-8')
        
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error creating note: {e}")
        raise HTTPException(status_code=500, detail="Failed to create note")
    finally:
        db.close()


@router.get("/{note_id}")
def get_note(note_id: int):
    """Get a single note by ID"""
    from database import SessionLocal, Note
    
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        
        response_data = {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "note_type": note.note_type,
            "color": note.color,
            "is_favorite": note.is_favorite,
            "audio_duration": note.audio_duration,
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None
        }
        
        if note.note_type == "voice" and note.audio_data:
            response_data["audio_data"] = base64.b64encode(note.audio_data).decode('utf-8')
        
        return response_data
    finally:
        db.close()


@router.put("/{note_id}")
def update_note(note_id: int, note_update: NoteUpdate):
    """Update an existing note"""
    from database import SessionLocal, Note
    from datetime import datetime
    
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        
        # Update fields if provided
        if note_update.title is not None:
            note.title = note_update.title
        if note_update.content is not None:
            note.content = note_update.content
        if note_update.color is not None:
            note.color = note_update.color
        if note_update.audio_data is not None:
            try:
                note.audio_data = base64.b64decode(note_update.audio_data)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid audio data: {str(e)}")
        if note_update.audio_duration is not None:
            note.audio_duration = note_update.audio_duration
        
        note.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(note)
        
        response_data = {
            "id": note.id,
            "title": note.title,
            "content": note.content,
            "note_type": note.note_type,
            "color": note.color,
            "is_favorite": note.is_favorite,
            "audio_duration": note.audio_duration,
            "created_at": note.created_at.isoformat() if note.created_at else None,
            "updated_at": note.updated_at.isoformat() if note.updated_at else None
        }
        
        if note.note_type == "voice" and note.audio_data:
            response_data["audio_data"] = base64.b64encode(note.audio_data).decode('utf-8')
        
        return response_data
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error updating note: {e}")
        raise HTTPException(status_code=500, detail="Failed to update note")
    finally:
        db.close()


@router.delete("/{note_id}")
def delete_note(note_id: int):
    """Delete a note permanently"""
    from database import SessionLocal, Note
    
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        
        db.delete(note)
        db.commit()
        
        return {"message": "Note deleted successfully", "note_id": note_id}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error deleting note: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete note")
    finally:
        db.close()


@router.patch("/{note_id}/favorite")
def toggle_note_favorite(note_id: int):
    """Toggle the favorite status of a note"""
    from database import SessionLocal, Note
    from datetime import datetime
    
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            raise HTTPException(status_code=404, detail="Note not found")
        
        note.is_favorite = not note.is_favorite
        note.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "note_id": note_id,
            "is_favorite": note.is_favorite,
            "message": "Added to favorites" if note.is_favorite else "Removed from favorites"
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Error toggling favorite: {e}")
        raise HTTPException(status_code=500, detail="Failed to toggle favorite")
    finally:
        db.close()
