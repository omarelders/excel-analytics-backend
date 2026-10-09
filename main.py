"""
Gold Road API - Main Application
Refactored to use modular routers for better maintainability
"""
import os
import logging
import ipaddress
import socket
from contextlib import asynccontextmanager
from urllib.parse import urlsplit
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

# Read once, at import time: the allow-list below is frozen with the app, and
# the secure-cookie default in routers/auth.py reads the same variable.
is_production = os.getenv("ENV") == "production"

# ============================================================================
# CORS Configuration: localhost origins only when ENV != 'production'
# ============================================================================
# The allow-list is built by a function rather than assembled in place, because
# of how the environment override used to be applied: it was appended *after*
# the production restriction, so a stale or stray CORS_ORIGINS entry silently
# put http://localhost:5173 back into the production allow-list. The
# restriction now lives inside the construction, where every env entry is
# either accepted or refused with a message naming the entry it refused.

# What counts as "this machine" is decided from the parsed origin's hostname and
# never as a substring of the raw string: "https://notlocalhost.example.com" and
# "http://localhost.evil.com" both contain "localhost" while pointing at somebody
# else's server.


def _is_loopback_ip(host: str) -> bool:
    """True for an IP literal that resolves to this machine.

    The address is parsed rather than prefix-matched, because "127." catches
    only one of loopback's spellings: 127.55.55.55, ::1 and 0177.0.0.1 all reach
    this machine and none of them starts with "127.". ipaddress parses the
    decimal forms and deliberately refuses the ambiguous ones (leading zeros,
    short forms, a bare integer), so socket.inet_aton is the fallback for those
    - it is what a resolver accepts, and "0177.0.0.1" is octal for 127.0.0.1.

    A hostname that neither parser accepts is not an IP at all, which is the
    normal case ("example.com", "roadtoonemillion.me") and is not loopback.
    """
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            address = ipaddress.IPv4Address(socket.inet_aton(host))
        except OSError:
            return False

    # 0.0.0.0 is "unspecified" rather than loopback, but it names this host's
    # own interfaces, so it is no more usable in a production allow-list.
    return address.is_loopback or address.is_unspecified


def _is_local_origin(origin: str) -> bool:
    """True when the origin can only refer to the machine the app runs on."""
    host = urlsplit(origin).hostname
    if not host:
        # Not an absolute origin at all - "", "localhost:5173", "example.com" -
        # so it cannot be a browser's Origin. Treating it as unallowable is the
        # only reading that cannot add something unintended.
        return True
    host = host.lower()

    # RFC 6761: every name ending in ".localhost" resolves to loopback, so
    # "app.localhost" is this machine exactly as "localhost" is.
    if host == "localhost" or host.endswith(".localhost"):
        return True

    return _is_loopback_ip(host)


def build_cors_origins(is_production: bool, extra_origins: str = "") -> list:
    """Assemble the CORS allow-list for this deployment.

    `extra_origins` is the raw comma-separated CORS_ORIGINS value. In production
    an entry that resolves to localhost/loopback is refused with a warning
    instead of being appended: a loopback origin in the production allow-list is
    either a leftover development value or an attempt to make another machine's
    traffic look first-party, and nothing legitimate in production needs one.
    In development the same entries are accepted - that is what the local
    frontend on :5173 talks to.
    """
    if is_production:
        origins = [
            "https://roadtoonemillion.me",
            "https://www.roadtoonemillion.me",
        ]
    else:
        origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://roadtoonemillion.me",
            "https://www.roadtoonemillion.me",
        ]

    for raw in (extra_origins or "").split(","):
        origin = raw.strip()
        if not origin:
            continue
        if is_production and _is_local_origin(origin):
            logger.warning(
                "Refusing CORS_ORIGINS entry %r: localhost/loopback origins are not allowed in "
                "the production CORS allow-list. Remove it from CORS_ORIGINS - production "
                "allows the built-in roadtoonemillion.me origins plus any non-loopback "
                "origins listed there.",
                origin,
            )
            continue
        origins.append(origin)

    return origins

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

cors_origins = build_cors_origins(is_production, os.environ.get("CORS_ORIGINS", ""))

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


# ============================================================================
# Response header policy — the API surface and the docs pages need opposite
# policies, so a single header for everything cannot be right for either.
# ============================================================================
# Every response that is not a docs page — the /api/* endpoints and the bare
# JSON endpoints next to them — is never rendered as a document. Its policy
# therefore has no 'unsafe-inline' in script-src: a script-src that lets any
# inline script run is not a working XSS defence, and the only consumer of
# that carve-out was the docs page below.
#
# The docs pages are the only HTML this app serves, and they are generated by
# FastAPI's own templates. What those templates reference was read off the
# installed fastapi 0.142.2 (fastapi/openapi/docs.py) rather than guessed:
#
#   /docs     swagger-ui.css and swagger-ui-bundle.js from cdn.jsdelivr.net, a
#             favicon from fastapi.tiangolo.com, and an *inline* <script> that
#             calls SwaggerUIBundle({...}). The app does not own that template,
#             so no allowlist of origins can replace the inline block — dropping
#             'unsafe-inline' here breaks /docs outright, which is why it is
#             permitted on these paths only.
#   /redoc    redoc.standalone.js from cdn.jsdelivr.net, Montserrat/Roboto from
#             fonts.googleapis.com, whose CSS in turn fetches the font files
#             themselves from fonts.gstatic.com.
#   /openapi.json  the schema Swagger UI fetches at runtime; 'self' covers it
#             under connect-src, so it needs nothing extra.
#
# Both policies are spelled out in full instead of being composed from a shared
# prefix because CSP is last-directive-wins: a merged img-src would silently
# override the stricter one depending on the order the pieces were joined in.
API_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'"
)

DOCS_CSP = (
    "default-src 'self'; "
    # 'unsafe-inline' here, and only here: Swagger UI's bootstrap block is
    # inline in FastAPI's template and cannot be re-hosted or hashed by us.
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; "
    "font-src 'self' https://fonts.gstatic.com; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'"
)


def _is_docs_path(path: str) -> bool:
    """True for the HTML documents FastAPI's docs templates serve, and only those."""
    return path == "/docs" or path.startswith("/docs/") or path == "/redoc"


def _is_docs_surface(path: str) -> bool:
    """True for the cacheable surface: the docs pages, the schema they fetch at
    runtime (/openapi.json), and static assets. This app mounts no static
    directory, so today the surface is the docs pages plus that one schema.

    Every other response is a session-bearing API read and must not be kept
    by the browser — which is why no-store is keyed on being outside this
    surface rather than on being under one prefix: /shipments, /payments/*,
    /upload/files, /statuses and /notifications/* read the session exactly
    like the /api/* endpoints do, and they carried no-store before it was
    scoped to /api/ and silently dropped from them.
    """
    return _is_docs_path(path) or path == "/openapi.json"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Content-Security-Policy"] = (
            DOCS_CSP if _is_docs_path(request.url.path) else API_CSP
        )
        # Everything outside the docs surface is a session-bearing API
        # response, so it stays no-store. Scoping the header to /api/ instead
        # would quietly drop it from the bare endpoints, which read the same
        # session. The docs pages and the schema they fetch are the cacheable
        # exceptions: when this was set on every response the Swagger UI page
        # and the assets it loads were re-downloaded on every visit.
        if not _is_docs_surface(request.url.path):
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
#
# ONE registration, on the bare prefix the frontend calls (its Settings page
# posts to /notifications/send; a grep of the frontend for "notifications"
# finds only that prefix). It must not be registered a second time under
# /api: slowapi buckets a limit on the request path, so two registrations of
# this router's 1/minute broadcast endpoint are two buckets, and an admin
# gets two broadcasts a minute instead of one. An alias route serving
# /api/notifications/* by redirect was tried and removed: it broke clients
# that send the session cookie per request (httpx and curl drop an
# explicitly-set Cookie header when following the redirect), and nothing in
# the frontend calls that prefix.
app.include_router(notifications.router)

# Auth router - login/logout/session management
app.include_router(auth.router)
