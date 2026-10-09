"""
Auth Router — Login / Logout / Me endpoints
Supports multi-device sessions via per-token rows in user_sessions table.
"""
import os
import uuid
import hashlib
import bcrypt
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Response, Request, Form, Depends

from dependencies import get_current_user, limiter

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Secure cookies default to True unless explicitly running in development
def is_secure_cookie() -> bool:
    return os.getenv("ENV") != "development"

# Module-level alias for backward compatibility
SECURE_COOKIE = is_secure_cookie()

# Session durations
REMEMBER_ME_SECONDS = 2_592_000   # 30 days
DEFAULT_SESSION_SECONDS = 86_400   # 1 day

# Dummy bcrypt hash for timing attack mitigation on non-existent users
DUMMY_BCRYPT_HASH = "$2b$12$k8Y6iX2t6tQk2tQk2tQk2e7k8Y6iX2t6tQk2tQk2tQk2e7k8Y6iX2"


# ============================================================================
# Password length: bcrypt's 72-byte limit
# ============================================================================
# bcrypt reads - and hashes - only the first 72 bytes of a password and raises
# on anything longer, so truncating to those bytes is what keeps login from
# crashing on "A" * 100. It is spelled out once, here, because a limit that
# lives as an inline literal in two files is a limit that drifts: the seed
# script's hashing must truncate to exactly the bytes this verifier reads, or a
# seeded password and the login that follows it disagree about what the
# password is.
MAX_PASSWORD_BYTES = 72


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash using bcrypt with 72-byte truncation safety.

    The truncation stays on the login path on purpose, and must not become a
    length check: a login that answers a too-long password differently from a
    wrong one tells an attacker which of their guesses landed within a few
    bytes of the limit, which is the very oracle the constant-time path below
    is there to close. Calling code therefore never sees an exception here -
    an over-long, malformed or unhashable password is simply not a match.
    """
    try:
        pw_bytes = plain_password.encode('utf-8')[:MAX_PASSWORD_BYTES]
        return bcrypt.checkpw(pw_bytes, hashed_password.encode('utf-8'))
    except Exception:
        return False


@router.post("/login")
@limiter.limit("5/minute")
def login(
    request: Request,
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

    db = None
    try:
        db = SessionLocal()
        # 1. Find user
        user = db.query(User).filter(User.username == username).first()
        if not user:
            # Equalize verification latency to prevent username enumeration via timing attacks
            verify_password(password, DUMMY_BCRYPT_HASH)
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # 2. Verify password
        if not verify_password(password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        # 2.5. Cleanup: Remove expired sessions for this user to keep DB clean
        db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.expires_at < datetime.utcnow()
        ).delete()

        # 3. Generate session token & hash for database storage
        raw_token = str(uuid.uuid4())
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        # 4. Calculate expiry
        if remember_me:
            duration = timedelta(seconds=REMEMBER_ME_SECONDS)
        else:
            duration = timedelta(seconds=DEFAULT_SESSION_SECONDS)

        expires_at = datetime.utcnow() + duration

        # 5. Store session in DB using hashed token
        session = UserSession(
            token=token_hash,
            user_id=user.id,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
        )
        db.add(session)
        db.commit()

        # 6. Set HttpOnly cookie
        max_age = REMEMBER_ME_SECONDS if remember_me else DEFAULT_SESSION_SECONDS
        response.set_cookie(
            key="session_token",
            value=raw_token,
            httponly=True,
            secure=is_secure_cookie(),
            samesite="strict",
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
    except Exception:
        if db:
            db.rollback()
        raise HTTPException(status_code=500, detail="Login failed")
    finally:
        if db:
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

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    db = None
    try:
        db = SessionLocal()
        session = db.query(UserSession).filter(UserSession.token == token_hash).first()
        if session:
            db.delete(session)
            db.commit()

        # Always clear the cookie regardless
        response.delete_cookie(
            key="session_token",
            path="/",
            httponly=True,
            secure=is_secure_cookie(),
            samesite="strict",
        )

        return {"message": "Logged out successfully"}
    except HTTPException:
        raise
    except Exception:
        if db:
            db.rollback()
        raise HTTPException(status_code=500, detail="Logout failed")
    finally:
        if db:
            db.close()


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """
    Protected endpoint — returns info about the currently logged-in user.
    """
    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "role": current_user.get("role", "user"),
        "is_admin": current_user.get("is_admin", False),
    }
