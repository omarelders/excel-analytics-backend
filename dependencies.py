"""
Auth Dependencies — reusable get_current_user, require_admin, and rate limiter
"""
import hashlib
from datetime import datetime
from fastapi import Request, HTTPException, Depends
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)


def get_current_user(request: Request):
    """
    FastAPI dependency that validates session cookies.
    Usage: user = Depends(get_current_user)
    """
    from sqlalchemy.orm import joinedload
    from database import SessionLocal, UserSession

    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated — no session cookie")

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    db = SessionLocal()
    try:
        # Optimize: Fetch Session + User in one query using joinedload
        session = db.query(UserSession).options(joinedload(UserSession.user)).filter(UserSession.token == token_hash).first()

        if not session:
            raise HTTPException(status_code=401, detail="Invalid session token")

        # Check expiration
        if session.expires_at < datetime.utcnow():
            # Clean up expired session
            db.delete(session)
            db.commit()
            raise HTTPException(status_code=401, detail="Session expired — please log in again")

        # Return the user object (already loaded)
        user = session.user
        role = getattr(user, "role", "user") or "user"
        is_admin = bool(getattr(user, "is_admin", False) or role == "admin")
        return {
            "id": user.id,
            "username": user.username,
            "role": role,
            "is_admin": is_admin,
        }
    finally:
        db.close()


def require_admin(current_user: dict = Depends(get_current_user)):
    """
    FastAPI dependency that verifies the user has admin role or privileges.
    Usage: user = Depends(require_admin)
    """
    if not current_user.get("is_admin") and current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user
