"""
Auth Dependencies — reusable get_current_user, require_admin, and rate limiter
"""
import hashlib
import os
from datetime import datetime
from fastapi import Request, HTTPException, Depends
from slowapi import Limiter

# ============================================================================
# Rate limiting: key on the real client, not on the proxy in front of the app
# ============================================================================
# Every request reaches the app through a reverse proxy (the platform router on
# Heroku, an ALB or nginx elsewhere), so the transport peer of each request is
# the proxy. Keying the limiter on that address puts the entire user base into
# one bucket: the 5/minute login limit becomes 5 logins per minute for everybody.
#
# The client's own address can only be recovered from X-Forwarded-For, and only
# the portion of that header written by hops we control can be believed. How
# many such hops sit in front of the app is declared in the environment:
#
#   unset -> DEFAULT_TRUSTED_PROXY_COUNT (exactly one proxy, the platform router)
#   0     -> nothing in front is ours; do not believe any forwarded header
#   N     -> N trusted proxies, each appending the address it received from
TRUSTED_PROXY_COUNT_ENV = "TRUSTED_PROXY_COUNT"
DEFAULT_TRUSTED_PROXY_COUNT = 1

# Bucket key for a request whose client cannot be attributed: no peer address at
# all, or a forwarded header that the trusted chain cannot account for.
UNKNOWN_CLIENT_KEY = "unknown"


def _parse_trusted_proxy_count(raw):
    """Turn a raw TRUSTED_PROXY_COUNT value into a non-negative int, or raise."""
    try:
        count = int(str(raw).strip())
    except (TypeError, ValueError):
        raise RuntimeError(
            f"{TRUSTED_PROXY_COUNT_ENV} must be a non-negative integer number of trusted "
            f"reverse proxies in front of the app, got {raw!r}"
        )
    if count < 0:
        raise RuntimeError(
            f"{TRUSTED_PROXY_COUNT_ENV} must be a non-negative integer, got {count}"
        )
    return count


def get_trusted_proxy_count():
    """The trusted hop count as configured right now (see TRUSTED_PROXY_COUNT_ENV)."""
    raw = os.environ.get(TRUSTED_PROXY_COUNT_ENV)
    if raw is None:
        return DEFAULT_TRUSTED_PROXY_COUNT
    return _parse_trusted_proxy_count(raw)


def configure_proxy_trust():
    """Validate the proxy topology at startup and return the trusted hop count.

    An undeclared count falls back to one trusted proxy, except under
    ENV=production where it is a hard error: a production deploy that has not
    declared its proxy chain is precisely the misconfiguration that throttles the
    whole user base as one bucket, so it must refuse to boot instead. An explicit
    "0" is a declaration, not an omission, and is accepted (it means "no proxy in
    front", a different risk that the operator chose on purpose).
    """
    raw = os.environ.get(TRUSTED_PROXY_COUNT_ENV)
    if raw is None:
        if os.getenv("ENV") == "production":
            raise RuntimeError(
                f"ENV=production requires {TRUSTED_PROXY_COUNT_ENV} to be set explicitly. "
                "It is the number of reverse proxies in front of the app, and the login "
                "rate limiter is keyed on it: without it every request is bucketed under "
                "the proxy's own address and the entire user base shares one 5/minute "
                "login limit. Set 0 only if the app is really exposed directly, or N for N "
                "trusted proxies (Heroku's router is 1)."
            )
        return DEFAULT_TRUSTED_PROXY_COUNT
    return _parse_trusted_proxy_count(raw)


def get_client_key(request: Request) -> str:
    """slowapi key_func — the rate-limit bucket of the real client, not the proxy.

    X-Forwarded-For grows rightwards: every hop appends the address it received
    the request from. The right-most entries were therefore written by the hops
    we trust, and the left-most of those is the client as the proxy chain
    actually observed it — a value the client itself cannot rewrite. Everything
    further left was supplied by whoever connected, or by proxies we do not
    control, so it is ignored and rotating it cannot open a fresh bucket.

    With no trusted hop (TRUSTED_PROXY_COUNT=0) the header is outside our trust
    boundary entirely and the transport peer address is used instead. That is
    safe only because both launchers restrict uvicorn's forwarded-header trust to
    loopback (see ProxyHeadersMiddleware's "client_host in self.trusted_hosts"
    gate), so scope["client"] is never rewritten from a client-supplied header
    for a request that really came through a router - it stays the peer.

    A header shorter than the proxy chain we were told to trust leaves nothing in
    it attributable to a hop, which is a misconfiguration rather than a client,
    so every such request shares one bucket the client cannot rotate. Falling
    back to request.client there would be a second policy decision: under a
    blanket forwarded-allow-ips the peer could itself have come from the header.
    """
    peer = request.client.host if request.client else None

    trusted = get_trusted_proxy_count()
    if trusted == 0:
        return peer or UNKNOWN_CLIENT_KEY

    entries = [
        entry.strip()
        for entry in request.headers.get("x-forwarded-for", "").split(",")
        if entry.strip()
    ]
    index = len(entries) - trusted
    if index < 0:
        return UNKNOWN_CLIENT_KEY
    return entries[index]


# NOTE (storage): slowapi's default storage is in-process memory, so with the
# `gunicorn -w 4` launcher in the Dockerfile each worker counts separately and the
# effective limit is 4x the configured one, and every restart (deploy, dyno cycle)
# zeroes the counters. Enforcing a true cross-worker limit needs shared storage
# (Redis); the remediation plan deliberately does not add that dependency, so the
# caveat lives here until it does.
limiter = Limiter(key_func=get_client_key)


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
