"""
Gold Road API - Main Application
Refactored to use modular routers for better maintainability
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from constants import CHANGEABLE_STATUSES, TARGET_STATUSES, ALL_STATUSES, STATUS_COLORS

# Import routers
from routers import shipments, payments, notes, content, notifications, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan context manager for startup/shutdown events"""
    # Startup: Create database tables
    from database import create_tables
    create_tables()
    yield
    # Shutdown: cleanup code would go here if needed


app = FastAPI(title="Gold Road API", lifespan=lifespan)

# CORS Configuration - allows frontend to communicate with backend
# Read additional origins from environment (comma-separated)
cors_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://roadtoonemillion.me",
    "https://www.roadtoonemillion.me",
]

# Add deployed frontend URL from environment variable
extra_origins = os.environ.get("CORS_ORIGINS", "")
if extra_origins:
    cors_origins.extend([o.strip() for o in extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

# Auth router - login/logout/session management
app.include_router(auth.router)
