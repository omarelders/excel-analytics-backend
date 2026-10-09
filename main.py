"""
Gold Road API - Main Application
Refactored to use modular routers for better maintainability
"""
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from constants import CHANGEABLE_STATUSES, TARGET_STATUSES, ALL_STATUSES, STATUS_COLORS
from dependencies import limiter, configure_proxy_trust

# Import routers
from routers import shipments, payments, notes, content, notifications, auth

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan context manager for startup/shutdown events"""
    # Defuse XML standard library to prevent XXE attacks
    try:
        import defusedxml
        defusedxml.defuse_stdlib()
    except Exception:
        pass

    # Startup: Create database tables
    from database import create_tables
    create_tables()
    yield
    # Shutdown: cleanup code would go here if needed


app = FastAPI(title="Gold Road API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration: localhost origins only when ENV != 'production'
is_production = os.getenv("ENV") == "production"

# How many reverse proxies sit in front of the app (Heroku: 1). Read here, at
# import time, for the same reason as is_production above: the rate limiter's key
# function is keyed on it, so a production deploy that has not declared its proxy
# chain has to fail loudly here instead of silently keying every request on the
# router's address and throttling the whole user base as one bucket.
trusted_proxy_count = configure_proxy_trust()
logger.info(
    "Rate limiter keyed on the client IP behind %d trusted proxy hop(s)",
    trusted_proxy_count,
)

if not is_production:
    cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://roadtoonemillion.me",
        "https://www.roadtoonemillion.me",
    ]
else:
    cors_origins = [
        "https://roadtoonemillion.me",
        "https://www.roadtoonemillion.me",
    ]

# Add extra origins from environment variable if configured
extra_origins = os.environ.get("CORS_ORIGINS", "")
if extra_origins:
    cors_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "Cookie",
    ],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: https://fastapi.tiangolo.com; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "connect-src 'self' https://roadtoonemillion.me https://www.roadtoonemillion.me;"
        )
        response.headers["Cache-Control"] = "no-store"
        return response


app.add_middleware(SecurityHeadersMiddleware)


# Global Exception Handler — hide internal error traces from clients
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, RateLimitExceeded):
        return _rate_limit_exceeded_handler(request, exc)
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    if isinstance(exc, RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()},
        )
    logger.exception(f"Unhandled server error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# Create 'uploads' folder if it doesn't exist
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ========== CORE ENDPOINTS ==========

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


# ========== REGISTER ROUTERS ==========

# Shipments router - includes all shipment, upload, file, and analytics endpoints
app.include_router(shipments.router)

# Payments router - payment file processing
app.include_router(payments.router)

# Notes router - ideas/notes endpoints
app.include_router(notes.router)

# Content router - content calendar endpoints
app.include_router(content.router)

# Notifications router - push notifications
app.include_router(notifications.router)
app.include_router(notifications.router, prefix="/api")

# Auth router - login/logout/session management
app.include_router(auth.router)
