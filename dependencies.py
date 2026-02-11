"""
Auth Dependencies — reusable get_current_user for protecting endpoints
"""
from datetime import datetime
from fastapi import Request, HTTPException


def get_current_user(request: Request):
    """
    FastAPI dependency that validates session cookies.
    Usage: user = Depends(get_current_user)
    """
    from sqlalchemy.orm import joinedload
    from database import SessionLocal, UserSession

    token = request.cookies.get("session_token")
    print(f"DEBUG: Checking session token from cookie: {token}")

    if not token:
        print("DEBUG: No session token found in cookies")
        raise HTTPException(status_code=401, detail="Not authenticated — no session cookie")

    db = SessionLocal()
    try:
        # Optimize: Fetch Session + User in one query using joinedload
        session = db.query(UserSession).options(joinedload(UserSession.user)).filter(UserSession.token == token).first()

        if not session:
            print(f"DEBUG: Session token {token} not found in DB")
            raise HTTPException(status_code=401, detail="Invalid session token")

        # Check expiration
        if session.expires_at < datetime.utcnow():
            print(f"DEBUG: Session token {token} expired at {session.expires_at}")
            # Clean up expired session
            db.delete(session)
            db.commit()
            raise HTTPException(status_code=401, detail="Session expired — please log in again")

        # Return the user object (already loaded)
        user = session.user
        print(f"DEBUG: User {user.username} authenticated successfully")
        return {
            "id": user.id,
            "username": user.username
        }
    finally:
        db.close()
