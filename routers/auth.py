"""
Auth Router — Login / Logout / Me endpoints
Supports multi-device sessions via per-token rows in user_sessions table.
"""
import os
import uuid
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Response, Request, Form, Depends

from dependencies import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Check environment - Default to False (Development) if not set
IS_PRODUCTION = os.getenv("ENV") == "production"

# Session durations
REMEMBER_ME_SECONDS = 315_360_000  # 10 years
DEFAULT_SESSION_SECONDS = 86_400   # 1 day


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using bcrypt"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


@router.post("/login")
def login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    remember_me: Optional[bool] = Form(False),
):
    """
    Validate credentials → create session row → set HttpOnly cookie.
    Does NOT invalidate existing sessions on other devices.
    """
    from database import SessionLocal, User, UserSession

    db = SessionLocal()
    try:
        # 1. Find user
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # 2. Verify password
        if not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # 2.5. Cleanup: Remove expired sessions for this user to keep DB clean
        # This prevents the table from growing efficiently without a background job
        db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.expires_at < datetime.utcnow()
        ).delete()

        # 3. Generate session token
        token = str(uuid.uuid4())

        # 4. Calculate expiry
        if remember_me:
            duration = timedelta(seconds=REMEMBER_ME_SECONDS)
        else:
            duration = timedelta(seconds=DEFAULT_SESSION_SECONDS)

        expires_at = datetime.utcnow() + duration

        # 5. Store session in DB
        session = UserSession(
            token=token,
            user_id=user.id,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
        )
        db.add(session)
        db.commit()

        # 6. Set HttpOnly cookie
        max_age = REMEMBER_ME_SECONDS if remember_me else DEFAULT_SESSION_SECONDS
        
        # NOTE: secure=True is required for HTTPS (production), but breaks HTTP (local dev)
        # We use IS_PRODUCTION to toggle this automatically.
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            secure=IS_PRODUCTION,
            samesite="lax",
            max_age=max_age,
            path="/",
        )

        return {
            "message": "Login successful",
            "username": user.username,
            "expires_at": expires_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")
    finally:
        db.close()


@router.post("/logout")
def logout(request: Request, response: Response):
    """
    Delete ONLY the current session token from DB (other devices stay logged in).
    Clear the cookie.
    """
    from database import SessionLocal, UserSession

    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="No session cookie found")

    db = SessionLocal()
    try:
        session = db.query(UserSession).filter(UserSession.token == token).first()
        if session:
            db.delete(session)
            db.commit()

        # Always clear the cookie regardless
        response.delete_cookie(
            key="session_token",
            path="/",
            httponly=True,
            secure=IS_PRODUCTION,
            samesite="lax",
        )

        return {"message": "Logged out successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")
    finally:
        db.close()


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """
    Protected endpoint — returns info about the currently logged-in user.
    """
    return {
        "id": current_user["id"],
        "username": current_user["username"],
    }
