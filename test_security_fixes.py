"""
Comprehensive verification test suite for Priority 0 and Priority 1 backend security fixes.
"""
import io
import os
import hashlib
import subprocess
import sys
import importlib.util
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text, event, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import bcrypt
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext

# Setup test environment
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["ENV"] = "production"

# Bind in-memory SQLite database with StaticPool so all connections share the same memory DB
test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

import database
database.engine = test_engine
database.SessionLocal = TestSessionLocal

from database import Base, User, UserSession
import dependencies
from main import app
import seed_users


@pytest.fixture(autouse=True)
def setup_db(monkeypatch):
    dependencies.limiter.reset()
    app.dependency_overrides.clear()
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", TestSessionLocal)
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    dependencies.limiter.reset()
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.clear()
    if os.path.exists("uploads"):
        for f in os.listdir("uploads"):
            if f.endswith(".xlsx"):
                try:
                    os.remove(os.path.join("uploads", f))
                except OSError:
                    pass


def test_dead_files_deleted():
    """Verify dead/insecure code files are completely removed from repo root"""
    assert not os.path.exists("main_backup.py"), "main_backup.py must be deleted"
    assert not os.path.exists("fix_shipments.py"), "fix_shipments.py must be deleted"
    assert not os.path.exists("force_create_content_table.py"), "force_create_content_table.py must be deleted"


def test_procfile_and_dockerfile():
    """Verify Procfile and Dockerfile no longer call seed_users.py on deployment"""
    with open("Procfile", "r", encoding="utf-8") as f:
        procfile_content = f.read()
    assert "seed_users.py" not in procfile_content, "Procfile must not execute seed_users.py"

    with open("Dockerfile", "r", encoding="utf-8") as f:
        dockerfile_content = f.read()
    assert "python seed_users.py" not in dockerfile_content, "Dockerfile must not execute seed_users.py"


def test_seed_users_no_hardcoded_passwords_and_skip_overwrite(monkeypatch):
    """Verify seed_users requires env vars, never overwrites existing users, and has no hardcoded passwords"""
    # 1. Inspect file source to ensure passwords stripped
    with open("seed_users.py", "r", encoding="utf-8") as f:
        seed_code = f.read()
    assert "omarelders1968$$" not in seed_code
    assert "mariamelders1968$$" not in seed_code

    # 2. Test seeding without env vars -> does not insert anything
    monkeypatch.delenv("SEED_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_OMAR_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_MARIAM_PASSWORD", raising=False)
    seed_users.seed()

    db = TestSessionLocal()
    assert db.query(User).count() == 0
    db.close()

    # 3. Test seeding with env vars
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "SuperSecurePassword123!")
    seed_users.seed()

    db = TestSessionLocal()
    users = db.query(User).all()
    assert len(users) == 2
    omar = db.query(User).filter(User.username == "omar").first()
    assert omar is not None
    assert omar.role == "admin"
    assert omar.is_admin is True
    original_hash = omar.password_hash
    db.close()

    # 4. Test re-seed with a DIFFERENT password -> MUST NOT OVERWRITE
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "NewAttemptedPassword999!")
    seed_users.seed()

    db = TestSessionLocal()
    omar_after = db.query(User).filter(User.username == "omar").first()
    assert omar_after.password_hash == original_hash, "Seeding must not overwrite existing user password"
    db.close()


def test_security_headers_and_cors(monkeypatch):
    """Verify security headers are attached to responses and CORS restricts non-production domains"""
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "Strict-Transport-Security" in headers
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert headers.get("Permissions-Policy") == "geolocation=(), microphone=(), camera=()"
    assert "Content-Security-Policy" in headers
    assert "default-src 'self'" in headers.get("Content-Security-Policy")

    # Allowed production origin gets Access-Control-Allow-Origin
    res_allowed = client.get("/health", headers={"Origin": "https://roadtoonemillion.me"})
    assert res_allowed.headers.get("access-control-allow-origin") == "https://roadtoonemillion.me"

    # Disallowed origin does NOT receive Access-Control-Allow-Origin
    res_blocked = client.get("/health", headers={"Origin": "http://malicious-site.example.com"})
    assert "access-control-allow-origin" not in res_blocked.headers

    # When in production, localhost origin is rejected
    monkeypatch.setenv("ENV", "production")
    res_local_blocked = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in res_local_blocked.headers


def test_global_exception_handler():
    """Verify unhandled exceptions return HTTP 500 with generic detail and no stack trace"""
    from fastapi import APIRouter
    test_router = APIRouter()

    @test_router.get("/api/test-crash")
    def crash_endpoint():
        raise RuntimeError("SecretDatabaseInternalConnectionError at 192.168.1.1:5432")

    app.include_router(test_router)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/api/test-crash")
    assert response.status_code == 500
    data = response.json()
    assert data == {"detail": "Internal server error"}
    assert "SecretDatabaseInternalConnectionError" not in str(data)


def test_auth_session_hashing_and_cookie_security(monkeypatch):
    """Verify session tokens are hashed in DB, cookies are secure, and get_current_user works with hash"""
    monkeypatch.setenv("ENV", "production")
    client = TestClient(app)

    # 1. Create a user
    salt = bcrypt.gensalt()
    pw_hash = bcrypt.hashpw(b"mysecretpassword", salt).decode("utf-8")
    db = TestSessionLocal()
    test_user = User(username="testuser", password_hash=pw_hash)
    db.add(test_user)
    db.commit()
    db.close()

    # 2. Login
    login_res = client.post("/api/auth/login", data={"username": "testuser", "password": "mysecretpassword"})
    assert login_res.status_code == 200
    
    # Check cookie
    assert "session_token" in login_res.cookies
    raw_cookie_token = login_res.cookies["session_token"]
    assert len(raw_cookie_token) > 0

    # Verify cookie flags from Set-Cookie header
    set_cookie_header = login_res.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie_header
    assert "samesite=strict" in set_cookie_header
    assert "secure" in set_cookie_header

    # Verify raw token is NOT in database; only SHA-256 hash is in database
    expected_hash = hashlib.sha256(raw_cookie_token.encode("utf-8")).hexdigest()
    db = TestSessionLocal()
    session_row = db.query(UserSession).first()
    assert session_row is not None
    assert session_row.token == expected_hash, "Database must store SHA-256 hash of token, not raw token"
    assert session_row.token != raw_cookie_token
    db.close()

    # 3. Call protected endpoint /api/auth/me
    me_res = client.get("/api/auth/me", cookies={"session_token": raw_cookie_token})
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "testuser"

    # 4. Calling with an invalid or expired cookie fails
    bad_res = client.get("/api/auth/me", cookies={"session_token": "invalid_fake_token"})
    assert bad_res.status_code == 401

    # 5. Logout
    logout_res = client.post("/api/auth/logout", cookies={"session_token": raw_cookie_token})
    assert logout_res.status_code == 200
    
    # Session row must be deleted from DB
    db = TestSessionLocal()
    assert db.query(UserSession).count() == 0
    db.close()


def test_upload_magic_bytes_and_chunked_validation():
    """Verify file uploads check ZIP magic bytes (50 4B 03 04) and reject invalid/fake Excel files"""
    # 1. Setup authenticated user
    client = TestClient(app)
    salt = bcrypt.gensalt()
    pw_hash = bcrypt.hashpw(b"validpass123", salt).decode("utf-8")
    db = TestSessionLocal()
    test_user = User(username="uploader_user", password_hash=pw_hash)
    db.add(test_user)
    db.commit()
    db.close()

    login_res = client.post("/api/auth/login", data={"username": "uploader_user", "password": "validpass123"})
    assert login_res.status_code == 200
    auth_cookies = {"session_token": login_res.cookies["session_token"]}

    # 2. Invalid signature (e.g. text file pretending to be .xlsx)
    fake_xlsx_content = b"This is not a real zip or xlsx file"
    fake_file = io.BytesIO(fake_xlsx_content)
    res = client.post(
        "/upload",
        files={"file": ("fake.xlsx", fake_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies=auth_cookies
    )
    assert res.status_code == 400
    assert "Invalid Excel file format" in res.json()["detail"] or "signature" in res.json()["detail"]

    # 3. Payment upload with invalid signature
    fake_payment_file = io.BytesIO(b"Fake content with xlsx extension")
    res_pay = client.post(
        "/payments/upload",
        files={"file": ("fake_payment.xlsx", fake_payment_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies=auth_cookies
    )
    assert res_pay.status_code == 400
    assert "Invalid Excel file format" in res_pay.json()["detail"]

    # 4. Valid zip magic bytes (50 4B 03 04)
    import pandas as pd
    excel_io = io.BytesIO()
    df = pd.DataFrame([{"الكود": "C01", "العميل": "Client1", "الحالة": "جديد", "قيمة الطرد": 50, "الرسوم": 5}])
    df.to_excel(excel_io, index=False)
    excel_bytes = excel_io.getvalue()
    assert excel_bytes.startswith(b"\x50\x4b\x03\x04")

    excel_io.seek(0)
    res_valid = client.post(
        "/upload",
        files={"file": ("valid.xlsx", excel_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies=auth_cookies
    )
    assert res_valid.status_code == 200
    assert res_valid.json()["status"] == "success"


def test_upload_size_limit_and_empty_file():
    """Verify upload size guard rejects oversized files (> 10MB) and empty files without leaking files on disk"""
    client = TestClient(app)
    salt = bcrypt.gensalt()
    pw_hash = bcrypt.hashpw(b"securepass99", salt).decode("utf-8")
    db = TestSessionLocal()
    test_user = User(username="size_user", password_hash=pw_hash)
    db.add(test_user)
    db.commit()
    db.close()

    login_res = client.post("/api/auth/login", data={"username": "size_user", "password": "securepass99"})
    auth_cookies = {"session_token": login_res.cookies["session_token"]}

    # 1. Test empty file (0 bytes)
    empty_file = io.BytesIO(b"")
    res_empty = client.post(
        "/upload",
        files={"file": ("empty.xlsx", empty_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies=auth_cookies
    )
    assert res_empty.status_code == 400

    # 2. Test oversized file (> 10MB) with valid magic header
    # 11 MB file starting with ZIP header
    oversized_data = b"\x50\x4b\x03\x04" + b"\x00" * (11 * 1024 * 1024)
    oversized_file = io.BytesIO(oversized_data)
    
    files_before = set(os.listdir("uploads")) if os.path.exists("uploads") else set()
    res_oversized = client.post(
        "/upload",
        files={"file": ("oversized.xlsx", oversized_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies=auth_cookies
    )
    assert res_oversized.status_code == 400
    assert "File too large" in res_oversized.json()["detail"]

    # Verify no leaked residual file left in uploads folder
    files_after = set(os.listdir("uploads")) if os.path.exists("uploads") else set()
    assert files_after == files_before, "Oversized upload must clean up and not leave leaked file on disk"


def test_login_exception_hiding(monkeypatch):
    """Verify internal database exceptions during login do not leak raw exception messages"""
    client = TestClient(app, raise_server_exceptions=False)
    
    # Force SessionLocal to throw unexpected error
    def faulty_session():
        raise RuntimeError("FATAL_INTERNAL_DB_CRASH_SECRET_CONNECTION_STRING")

    monkeypatch.setattr(database, "SessionLocal", faulty_session)
    
    res = client.post("/api/auth/login", data={"username": "any", "password": "any"})
    assert res.status_code == 500
    assert res.json() == {"detail": "Login failed"}
    assert "FATAL_INTERNAL_DB_CRASH_SECRET_CONNECTION_STRING" not in res.text


def test_corrupt_zip_upload_cleanup():
    """Verify corrupt zip starting with magic bytes 50 4B 03 04 is rejected without leaking file on disk"""
    client = TestClient(app)
    salt = bcrypt.gensalt()
    pw_hash = bcrypt.hashpw(b"securepass99", salt).decode("utf-8")
    db = TestSessionLocal()
    test_user = User(username="corrupt_tester", password_hash=pw_hash)
    db.add(test_user)
    db.commit()
    db.close()

    login_res = client.post("/api/auth/login", data={"username": "corrupt_tester", "password": "securepass99"})
    auth_cookies = {"session_token": login_res.cookies["session_token"]}

    # Valid ZIP header followed by invalid/corrupted records
    corrupt_zip = b"\x50\x4b\x03\x04\x00\x00\x00\x00corrupt_payload_data_not_valid_openxml"
    corrupt_file = io.BytesIO(corrupt_zip)

    files_before = set(os.listdir("uploads")) if os.path.exists("uploads") else set()
    res = client.post(
        "/upload",
        files={"file": ("corrupt.xlsx", corrupt_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies=auth_cookies
    )
    # Endpoints report error and must NOT leave the corrupted file on disk
    files_after = set(os.listdir("uploads")) if os.path.exists("uploads") else set()
    assert files_after == files_before, f"Corrupted file must be cleaned up from disk, leaked: {files_after - files_before}"

    # Also test payments upload endpoint with corrupt zip
    corrupt_payment = io.BytesIO(corrupt_zip)
    res_pay = client.post(
        "/payments/upload",
        files={"file": ("corrupt_payment.xlsx", corrupt_payment, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        cookies=auth_cookies
    )
    files_after_pay = set(os.listdir("uploads")) if os.path.exists("uploads") else set()
    assert files_after_pay == files_before, f"Corrupted payment file must be cleaned up from disk, leaked: {files_after_pay - files_before}"


def test_seed_users_no_unicode_crash(monkeypatch):
    """Verify seed_users.seed() prints safely without UnicodeEncodeError in non-UTF8 consoles"""
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "SecretPw123!")
    # Must run without throwing UnicodeEncodeError or any other exception
    seed_users.seed()

    db = TestSessionLocal()
    assert db.query(User).filter(User.username == "omar").first() is not None
    db.close()


def test_rate_limiting_login_and_notifications():
    """Verify slowapi rate limits: login (5/min), file uploads (5/min), and push notifications (1/min)"""
    client = TestClient(app)
    dependencies.limiter.reset()

    # 1. Login rate limit (5 allowed per minute, 6th rejected with 429)
    for _ in range(5):
        res = client.post("/api/auth/login", data={"username": "nonexistent", "password": "any"})
        assert res.status_code == 401

    res_blocked = client.post("/api/auth/login", data={"username": "nonexistent", "password": "any"})
    assert res_blocked.status_code == 429, "6th login attempt must be rate-limited with HTTP 429"

    # Reset limiter for next test
    dependencies.limiter.reset()

    # 2. File uploads rate limit (5 allowed per minute, 6th rejected with 429)
    app.dependency_overrides[dependencies.get_current_user] = lambda: {"id": 1, "username": "admin", "role": "admin", "is_admin": True}
    try:
        dummy_excel = io.BytesIO(b"\x50\x4b\x03\x04\x00\x00\x00\x00")
        for _ in range(5):
            res_up = client.post(
                "/upload",
                files={"file": ("rate_test.xlsx", io.BytesIO(dummy_excel.getvalue()), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
            assert res_up.status_code in (200, 400)

        res_up_blocked = client.post(
            "/upload",
            files={"file": ("rate_test.xlsx", io.BytesIO(dummy_excel.getvalue()), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        assert res_up_blocked.status_code == 429, "6th file upload attempt must be rate-limited with HTTP 429"
    finally:
        dependencies.limiter.reset()
        app.dependency_overrides.clear()

    # 3. Push notifications rate limit (1 allowed per minute, 2nd rejected with 429)
    app.dependency_overrides[dependencies.get_current_user] = lambda: {"id": 1, "username": "admin", "role": "admin", "is_admin": True}
    try:
        res1 = client.post("/notifications/send", json={"title": "Notice 1", "body": "Body 1"})
        assert res1.status_code == 200

        res2 = client.post("/notifications/send", json={"title": "Notice 2", "body": "Body 2"})
        assert res2.status_code == 429, "2nd notification send within 1 minute must be rate-limited with HTTP 429"
    finally:
        app.dependency_overrides.clear()
        dependencies.limiter.reset()


def test_session_expiry_reduced_to_30_days(monkeypatch):
    """Verify 'Remember Me' session duration is reduced to 30 days (2,592,000s) instead of 10 years"""
    from routers.auth import REMEMBER_ME_SECONDS
    assert REMEMBER_ME_SECONDS == 2_592_000, "REMEMBER_ME_SECONDS must be exactly 30 days (2,592,000s)"

    salt = bcrypt.gensalt()
    pw_hash = bcrypt.hashpw(b"testpass123", salt).decode("utf-8")
    db = TestSessionLocal()
    user = User(username="expiry_user", password_hash=pw_hash)
    db.add(user)
    db.commit()
    db.close()

    client = TestClient(app)
    res = client.post("/api/auth/login", data={"username": "expiry_user", "password": "testpass123", "remember_me": True})
    assert res.status_code == 200
    set_cookie = res.headers.get("set-cookie", "")
    assert "max-age=2592000" in set_cookie.lower()


def test_login_timing_attack_mitigation():
    """Verify non-existent username and >72 byte passwords execute dummy bcrypt safely and return 401 without oracle"""
    client = TestClient(app, raise_server_exceptions=False)
    dependencies.limiter.reset()

    # Create real user
    salt = bcrypt.gensalt()
    pw_hash = bcrypt.hashpw(b"validpass123", salt).decode("utf-8")
    db = TestSessionLocal()
    db.add(User(username="timing_tester", password_hash=pw_hash))
    db.commit()
    db.close()

    # 1. Non-existent username
    res = client.post("/api/auth/login", data={"username": "completely_nonexistent_user", "password": "some_password"})
    assert res.status_code == 401
    assert res.json() == {"detail": "Invalid username or password"}

    # 2. Long password (>72 bytes) on existing user must NOT crash with 500
    long_pw = "A" * 100
    res_exist_long = client.post("/api/auth/login", data={"username": "timing_tester", "password": long_pw})
    assert res_exist_long.status_code == 401, "Long password on existing user must return 401, not 500"

    # 3. Long password (>72 bytes) on non-existing user must return identical 401
    res_fake_long = client.post("/api/auth/login", data={"username": "no_such_user_123", "password": long_pw})
    assert res_fake_long.status_code == 401, "Long password on fake user must return 401"
    assert res_exist_long.json() == res_fake_long.json()


def test_rbac_admin_guards():
    """Verify admin-only guards on push notification send and file deletion endpoints"""
    client = TestClient(app)

    # 1. Non-admin user calling /notifications/send -> 403 Forbidden
    app.dependency_overrides[dependencies.get_current_user] = lambda: {"id": 2, "username": "regular_user", "role": "user", "is_admin": False}
    res_send_denied = client.post("/notifications/send", json={"title": "Test", "body": "Body"})
    assert res_send_denied.status_code == 403, "Non-admin user must receive 403 on /notifications/send"

    # Also test /api/notifications/send alias
    res_api_send_denied = client.post("/api/notifications/send", json={"title": "Test", "body": "Body"})
    assert res_api_send_denied.status_code == 403, "Non-admin user must receive 403 on /api/notifications/send"

    # 2. Non-admin user calling DELETE /upload/files/1 -> 403 Forbidden
    res_del_shipment_denied = client.delete("/upload/files/1")
    assert res_del_shipment_denied.status_code == 403, "Non-admin user must receive 403 on /upload/files/{id}"

    # 3. Non-admin user calling DELETE /payments/files/1 -> 403 Forbidden
    res_del_payment_denied = client.delete("/payments/files/1")
    assert res_del_payment_denied.status_code == 403, "Non-admin user must receive 403 on /payments/files/{id}"

    # 4. Admin user calling the same endpoints is authorized (e.g. 404 for non-existent file rather than 403)
    app.dependency_overrides[dependencies.get_current_user] = lambda: {"id": 1, "username": "admin_user", "role": "admin", "is_admin": True}
    res_del_shipment_admin = client.delete("/upload/files/99999")
    assert res_del_shipment_admin.status_code == 404, "Admin should pass authorization check (returning 404 for missing file)"

    res_del_payment_admin = client.delete("/payments/files/99999")
    assert res_del_payment_admin.status_code == 404, "Admin should pass authorization check (returning 404 for missing file)"

    app.dependency_overrides.clear()


def test_async_push_broadcast():
    """Verify push notification send does not block synchronously and queues background task"""
    from database import PushSubscription
    db = TestSessionLocal()
    db.add(PushSubscription(endpoint="https://push.example.com/sub1", p256dh="key1", auth="auth1"))
    db.add(PushSubscription(endpoint="https://push.example.com/sub2", p256dh="key2", auth="auth2"))
    db.commit()
    db.close()

    app.dependency_overrides[dependencies.get_current_user] = lambda: {"id": 1, "username": "admin_user", "role": "admin", "is_admin": True}
    dependencies.limiter.reset()
    client = TestClient(app)

    res = client.post("/notifications/send", json={"title": "Broadcast Test", "body": "Async check"})
    assert res.status_code == 200
    assert "2 subscribers" in res.json()["message"]
    app.dependency_overrides.clear()


def test_upload_disk_cleanup_on_success():
    """Verify successful Excel uploads delete temporary files from disk (vuln 11 disk exhaustion)"""
    import pandas as pd
    client = TestClient(app)
    app.dependency_overrides[dependencies.get_current_user] = lambda: {"id": 1, "username": "uploader", "role": "admin", "is_admin": True}
    dependencies.limiter.reset()

    # Generate valid Excel bytes
    excel_io = io.BytesIO()
    df = pd.DataFrame([{"الكود": "CLEANUP_01", "العميل": "ClientClean", "الحالة": "جديد", "قيمة الطرد": 100, "الرسوم": 10}])
    df.to_excel(excel_io, index=False)
    excel_io.seek(0)

    files_before = set(os.listdir("uploads")) if os.path.exists("uploads") else set()
    res = client.post(
        "/upload",
        files={"file": ("cleanup_test.xlsx", excel_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # Temporary file must NOT linger in uploads directory
    files_after = set(os.listdir("uploads")) if os.path.exists("uploads") else set()
    assert files_after == files_before, f"Temporary upload file must be deleted upon success, leaked: {files_after - files_before}"
    app.dependency_overrides.clear()


def test_batched_crud_deduplication():
    """Verify crud.save_upload uses batched duplicate checks without loading full table"""
    import crud
    from database import Shipment
    db = TestSessionLocal()

    # Seed 3 existing shipments
    for code in ["CODE_A", "CODE_B", "CODE_C"]:
        db.add(Shipment(shipment_code=code, status="جديد"))
    db.commit()

    # Prepare upload data with 1 existing code and 2 new codes
    upload_data = [
        {"الكود": "CODE_A", "الحالة": "جديد", "العميل": "A"},  # duplicate
        {"الكود": "CODE_D", "الحالة": "جديد", "العميل": "D"},  # new
        {"الكود": "CODE_E", "الحالة": "جديد", "العميل": "E"},  # new
        {"الكود": "CODE_D", "الحالة": "جديد", "العميل": "D_repeat"},  # duplicate within batch
    ]

    result = crud.save_upload(db, "test_batch.xlsx", upload_data)
    assert result["inserted"] == 2
    assert result["skipped_duplicates"] == 2
    db.close()


def test_bounded_pydantic_and_query_limits():
    """Verify limit query parameter enforces le=100 and Pydantic models enforce max lengths"""
    client = TestClient(app)
    app.dependency_overrides[dependencies.get_current_user] = lambda: {"id": 1, "username": "tester", "role": "admin", "is_admin": True}

    # 1. limit > 100 on /shipments returns 422
    res_limit_too_high = client.get("/shipments?limit=101")
    assert res_limit_too_high.status_code == 422

    # limit <= 100 succeeds
    res_limit_ok = client.get("/shipments?limit=100")
    assert res_limit_ok.status_code == 200

    # 2. Pydantic bounds on NoteCreate (title > 255 chars rejected)
    long_title = "A" * 256
    res_note_too_long = client.post("/api/notes", json={"title": long_title})
    assert res_note_too_long.status_code == 422

    # Negative audio duration rejected
    res_note_neg_dur = client.post("/api/notes", json={"title": "Valid Title", "audio_duration": -5.0})
    assert res_note_neg_dur.status_code == 422

    # Valid note accepted
    res_note_valid = client.post("/api/notes", json={"title": "Valid Note", "audio_duration": 12.5})
    assert res_note_valid.status_code == 200

    # 3. Pydantic bounds on ContentItemCreate (title > 255 chars rejected)
    res_content_too_long = client.post("/api/content", json={"date": "2026-01-01", "title": long_title})
    assert res_content_too_long.status_code == 422

    app.dependency_overrides.clear()


def test_pinned_requirements_and_no_passlib():
    """Verify requirements.txt has no unpinned packages, includes slowapi, and removed passlib"""
    with open("requirements.txt", "r", encoding="utf-8") as f:
        req_lines = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    assert "passlib" not in "".join(req_lines), "passlib must be removed from requirements.txt"
    assert any(line.startswith("slowapi==") for line in req_lines), "slowapi must be pinned in requirements.txt"
    
    # Every package line must have '=='
    for line in req_lines:
        assert "==" in line, f"Package requirement '{line}' must be pinned with exact version (==)"


def test_swagger_docs_csp_compatibility():
    """Verify CSP allows Swagger UI resources from CDN so /docs works in browsers"""
    client = TestClient(app)
    res = client.get("/docs")
    assert res.status_code == 200
    csp = res.headers.get("content-security-policy", "")
    assert "https://cdn.jsdelivr.net" in csp
    assert "https://fastapi.tiangolo.com" in csp


def test_alembic_migrations_chain():
    """Verify Alembic migration chain contains baseline and 002 auth tables migration"""
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config("alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert "002_user_roles_and_auth" in heads


# ============================================================================
# Task 1 — admin recovery and deliberate session invalidation
# ============================================================================
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def _load_module(name, relative_path):
    """Load a module from a file path that is not on sys.path (scripts/, alembic/versions/)."""
    path = os.path.join(REPO_ROOT, relative_path)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _migration_002():
    return _load_module(
        "migration_002_under_test",
        os.path.join("alembic", "versions", "20261007_002_user_roles_and_auth.py"),
    )


def _sqlite_migration_engine(tmp_path, name="migration.sqlite3"):
    """A real file-backed SQLite engine, so the DDL under test really executes."""
    engine = create_engine(f"sqlite:///{(tmp_path / name).as_posix()}")
    return engine


def _create_pre_002_schema(engine):
    """users / user_sessions / push_subscriptions as they existed before revision 002.

    users has no role or is_admin column - that is the state 002 has to add columns to.
    user_sessions holds a plaintext uuid4 row plus a SHA-256 hash row.
    """
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, password_hash TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE user_sessions ("
            " token VARCHAR(64) PRIMARY KEY, user_id INTEGER NOT NULL,"
            " created_at DATETIME, expires_at DATETIME NOT NULL,"
            " FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE)"
        ))
        conn.execute(text(
            "CREATE TABLE push_subscriptions ("
            " id INTEGER PRIMARY KEY, endpoint VARCHAR, p256dh VARCHAR NOT NULL,"
            " auth VARCHAR NOT NULL, created_at DATETIME)"
        ))
        conn.execute(text(
            "INSERT INTO users (id, username, password_hash) VALUES (1, 'omar', 'hash')"
        ))
        conn.execute(text(
            "INSERT INTO user_sessions (token, user_id, expires_at) VALUES"
            " ('legacy-plaintext-uuid4-row', 1, '2026-01-01'),"
            " ('%s', 1, '2026-01-01')" % ("a" * 64)
        ))


def _column_names(engine, table_name):
    with engine.connect() as conn:
        return [column["name"] for column in inspect(conn).get_columns(table_name)]


def _table_names(engine):
    with engine.connect() as conn:
        return sorted(inspect(conn).get_table_names())


def test_promote_admin_grants_admin_and_passes_require_admin():
    """A pre-migration user (role='user', is_admin=False) must be recoverable, then pass require_admin"""
    # 1. Reproduce the audited defect: a user that already existed before migration 002.
    original_hash = bcrypt.hashpw(b"omarpassword123", bcrypt.gensalt()).decode("utf-8")
    db = TestSessionLocal()
    db.add(User(username="omar", password_hash=original_hash, role="user", is_admin=False))
    db.commit()
    db.close()

    client = TestClient(app)
    login_res = client.post("/api/auth/login", data={"username": "omar", "password": "omarpassword123"})
    assert login_res.status_code == 200
    cookies = {"session_token": login_res.cookies["session_token"]}

    # The real auth path agrees the user exists but has no admin privileges (the 403s).
    me_before = client.get("/api/auth/me", cookies=cookies)
    assert me_before.status_code == 200
    assert me_before.json() == {"id": 1, "username": "omar", "role": "user", "is_admin": False}
    assert client.delete("/upload/files/1", cookies=cookies).status_code == 403
    assert client.delete("/payments/files/1", cookies=cookies).status_code == 403
    dependencies.limiter.reset()
    assert client.post("/notifications/send", json={"title": "t", "body": "b"}, cookies=cookies).status_code == 403

    # 2. Recovery: the script's session-scoped function promotes that user.
    promote_admin = _load_module("promote_admin_under_test", os.path.join("scripts", "promote_admin.py"))
    db = TestSessionLocal()
    message = promote_admin.promote_user(db, "omar")
    db.close()
    assert "user 'omar' is now admin" in message

    db = TestSessionLocal()
    promoted = db.query(User).filter(User.username == "omar").first()
    assert promoted.role == "admin"
    assert promoted.is_admin is True
    assert promoted.password_hash == original_hash, "promote_admin must never touch the password"
    db.close()

    # 3. The SAME session cookie now passes require_admin on the previously blocked endpoints.
    me_after = client.get("/api/auth/me", cookies=cookies)
    assert me_after.json() == {"id": 1, "username": "omar", "role": "admin", "is_admin": True}
    dependencies.limiter.reset()
    assert client.post("/notifications/send", json={"title": "t", "body": "b"}, cookies=cookies).status_code == 200
    assert client.delete("/upload/files/99999", cookies=cookies).status_code == 404
    assert client.delete("/payments/files/99999", cookies=cookies).status_code == 404


def test_promote_admin_is_idempotent_and_rejects_unknown_username():
    """Promoting an existing admin is a no-op success; an unknown username raises with a clear message"""
    promote_admin = _load_module("promote_admin_under_test", os.path.join("scripts", "promote_admin.py"))

    db = TestSessionLocal()
    db.add(User(username="mariam", password_hash=bcrypt.hashpw(b"mariampw123", bcrypt.gensalt()).decode("utf-8")))
    db.commit()
    db.close()

    db = TestSessionLocal()
    first = promote_admin.promote_user(db, "mariam")
    db.close()
    assert "user 'mariam' is now admin" in first

    db = TestSessionLocal()
    second = promote_admin.promote_user(db, "mariam")
    db.close()
    assert "already admin" in second

    db = TestSessionLocal()
    mariam = db.query(User).filter(User.username == "mariam").first()
    assert mariam.role == "admin" and mariam.is_admin is True
    db.close()

    with pytest.raises(promote_admin.UserNotFoundError) as excinfo:
        db = TestSessionLocal()
        try:
            promote_admin.promote_user(db, "ghost_user")
        finally:
            db.close()
    assert "ghost_user" in str(excinfo.value)
    assert "promote_admin.py --list" in str(excinfo.value)


def test_promote_admin_cli_end_to_end(tmp_path):
    """The operator-facing CLI: --list shows roles, promoting exits 0, unknown user exits non-zero"""
    promote_admin = _load_module("promote_admin_under_test", os.path.join("scripts", "promote_admin.py"))
    script_path = os.path.join(REPO_ROOT, "scripts", "promote_admin.py")

    # Real file-backed SQLite database so the subprocess sees the committed rows.
    db_url = f"sqlite:///{(tmp_path / 'promote_admin.sqlite3').as_posix()}"
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    original_hash = bcrypt.hashpw(b"cli_user_password", bcrypt.gensalt()).decode("utf-8")
    db.add(User(username="omar", password_hash=original_hash, role="user", is_admin=False))
    db.commit()
    db.close()

    env = dict(os.environ, DATABASE_URL=db_url)

    def run(*args):
        return subprocess.run(
            [sys.executable, script_path, *args],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
        )

    # --list reports every user and its role.
    listed = run("--list")
    assert listed.returncode == 0, listed.stderr
    assert "omar" in listed.stdout
    assert "user" in listed.stdout
    assert "admin" not in listed.stdout

    # Unknown username -> non-zero exit with a clear message.
    missing = run("ghost")
    assert missing.returncode == 1, "an unknown username is exit 1 (user not found), not an environment error"
    assert "ghost" in missing.stdout + missing.stderr

    # Promote -> exit 0 and the documented success line.
    promoted = run("omar")
    assert promoted.returncode == 0, promoted.stderr
    assert "user 'omar' is now admin" in promoted.stdout

    # Re-running is an idempotent success, still exit 0.
    again = run("omar")
    assert again.returncode == 0, again.stderr
    assert "already admin" in again.stdout

    # The database really changed, and only the privilege columns did.
    db = Session()
    omar = db.query(User).filter(User.username == "omar").first()
    assert omar.role == "admin"
    assert omar.is_admin is True
    assert omar.password_hash == original_hash
    db.close()
    engine.dispose()


def test_promote_admin_cli_reports_a_schema_error_distinctly(tmp_path):
    """A database with no users table is an environment error: exit 3, with a hint.

    This is not "that user does not exist" (exit 1) - the schema is missing - so it
    must get its own exit code, or a scripted caller cannot tell the two apart.
    """
    script_path = os.path.join(REPO_ROOT, "scripts", "promote_admin.py")
    empty_db = f"sqlite:///{(tmp_path / 'empty.sqlite3').as_posix()}"
    env = dict(os.environ, DATABASE_URL=empty_db)

    result = subprocess.run(
        [sys.executable, script_path, "omar"],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 3, (result.returncode, result.stdout, result.stderr)
    assert "[ERROR] Could not promote 'omar'" in result.stdout
    assert "run_migrations.py" in result.stdout
    assert "Traceback" not in result.stdout + result.stderr


def test_promote_admin_promotes_writes_no_transaction_when_already_admin(tmp_path):
    """Promoting an existing admin must be a read-only no-op.

    Proven with a real SQLite database and a real sessionmaker: after_commit is a real
    SQLAlchemy event that fires once per committed transaction, so it distinguishes
    "returned without committing" from "committed". A re-run must not open a write
    transaction at all.
    """
    promote_admin = _load_module("promote_admin_under_test", os.path.join("scripts", "promote_admin.py"))

    engine = create_engine(f"sqlite:///{(tmp_path / 'already_admin.sqlite3').as_posix()}")
    try:
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        db.add(User(username="mariam", password_hash="h" * 60, role="admin", is_admin=True))
        db.commit()
        db.close()

        commits = []
        event.listen(Session, "after_commit", lambda session: commits.append(1))

        db = Session()
        message = promote_admin.promote_user(db, "mariam")
        db.close()
        assert "already admin" in message
        assert commits == [], "promoting an existing admin must not commit"

        # The row is still admin, and its password hash was never touched.
        db = Session()
        mariam = db.query(User).filter_by(username="mariam").first()
        assert mariam.role == "admin" and mariam.is_admin is True
        assert mariam.password_hash == "h" * 60
        db.close()
    finally:
        engine.dispose()


def test_promote_admin_promotes_writes_a_transaction_when_promoting(tmp_path):
    """Positive control for the no-write test: a real promotion does commit."""
    promote_admin = _load_module("promote_admin_under_test", os.path.join("scripts", "promote_admin.py"))

    engine = create_engine(f"sqlite:///{(tmp_path / 'needs_promote.sqlite3').as_posix()}")
    try:
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        db.add(User(username="omar", password_hash="h" * 60, role="user", is_admin=False))
        db.commit()
        db.close()

        commits = []
        event.listen(Session, "after_commit", lambda session: commits.append(1))

        db = Session()
        message = promote_admin.promote_user(db, "omar")
        db.close()
        assert "user 'omar' is now admin" in message
        assert commits == [1], "a real promotion must commit the change"
    finally:
        engine.dispose()


def test_promote_admin_list_reports_a_usable_error_when_schema_is_missing(monkeypatch, capsys):
    """--list must not dump a traceback on an operator whose database has no tables yet"""
    promote_admin = _load_module("promote_admin_under_test", os.path.join("scripts", "promote_admin.py"))

    class _SchemaMissingSession:
        def query(self, *args):
            raise RuntimeError("no such table: users")

        def close(self):
            pass

    monkeypatch.setattr(promote_admin, "SessionLocal", _SchemaMissingSession)

    assert promote_admin.main(["--list"]) == 3
    out = capsys.readouterr().out
    assert "[ERROR] Could not list users" in out
    assert "run_migrations.py" in out
    assert "Traceback" not in out


def test_promote_admin_survives_a_session_that_cannot_be_built(monkeypatch, capsys):
    """A SessionLocal() that raises must not escape main() as a traceback.

    SessionLocal() construction happens against the real engine, so an unbound engine or
    a bad DATABASE_URL fails here - inside main(), not outside it.
    """
    promote_admin = _load_module("promote_admin_under_test", os.path.join("scripts", "promote_admin.py"))

    def _broken_session_factory():
        raise RuntimeError("misconfigured DATABASE_URL")

    monkeypatch.setattr(promote_admin, "SessionLocal", _broken_session_factory)

    for argv in (["--list"], ["omar"]):
        ret = promote_admin.main(argv)
        assert ret == 3, argv
        out = capsys.readouterr().out
        assert "[ERROR]" in out, argv
        assert "Traceback" not in out, argv


def test_seed_users_prints_recovery_hint_for_existing_user(monkeypatch, capsys):
    """An existing non-admin user gets an actionable promote_admin hint, never a silent skip"""
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "RecoveryHintPw123!")
    original_hash = bcrypt.hashpw(b"existinguserpw", bcrypt.gensalt()).decode("utf-8")
    db = TestSessionLocal()
    db.add(User(username="omar", password_hash=original_hash, role="user", is_admin=False))
    db.commit()
    db.close()

    seed_users.seed()
    out = capsys.readouterr().out
    assert "[INFO] User 'omar' exists and is role='user'; run 'python scripts/promote_admin.py omar' to grant admin." in out

    db = TestSessionLocal()
    omar = db.query(User).filter(User.username == "omar").first()
    assert omar.password_hash == original_hash, "Seeding must still not overwrite the existing user"
    assert omar.role == "user" and omar.is_admin is False
    db.close()


def test_migration_002_invalidates_every_preexisting_session_exactly_once(tmp_path):
    """The blanket DELETE runs, and is a no-op on a re-run.

    Every pre-existing session row must go, including one whose token happens to be 64
    characters long - the shape of a SHA-256 hash. A length-filtered DELETE would leave
    such a row behind while the migration still reported success, so the two rows below
    are chosen to make that failure visible.
    """
    migration = _migration_002()
    engine = _sqlite_migration_engine(tmp_path, "invalidate.sqlite3")
    try:
        _create_pre_002_schema(engine)

        with engine.connect() as conn:
            assert migration.invalidate_legacy_sessions(conn) == 2
            conn.commit()
            assert conn.execute(text("SELECT COUNT(*) FROM user_sessions")).scalar() == 0

        # Idempotent: re-running deletes zero rows and cannot log anybody out twice.
        with engine.connect() as conn:
            assert migration.invalidate_legacy_sessions(conn) == 0
            conn.commit()
            assert conn.execute(text("SELECT COUNT(*) FROM user_sessions")).scalar() == 0

        # The users are untouched - only the sessions are gone.
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM users")).scalar() == 1
    finally:
        engine.dispose()


def test_migration_002_schema_probes_resolve_through_the_connection(tmp_path):
    """table_exists / column_exists must answer from the connection's own schema.

    These probes guard the upgrade() critical path: if column_exists() wrongly reports
    True for a column that is not there, upgrade() prints "users table already exists"
    and silently never adds role/is_admin, which is unrecoverable.
    """
    migration = _migration_002()
    engine = _sqlite_migration_engine(tmp_path, "probes.sqlite3")
    try:
        _create_pre_002_schema(engine)
        with engine.connect() as conn:
            assert migration.table_exists(conn, "users") is True
            assert migration.table_exists(conn, "user_sessions") is True
            assert migration.table_exists(conn, "no_such_table") is False
            # The pre-002 users table has neither column, and both probes must agree.
            assert migration.column_exists(conn, "users", "role") is False
            assert migration.column_exists(conn, "users", "is_admin") is False
            assert migration.column_exists(conn, "users", "username") is True
            # A column on a table that does not exist is False, not an error.
            assert migration.column_exists(conn, "no_such_table", "role") is False
    finally:
        engine.dispose()


def _run_downgrade_on_real_sqlite(tmp_path, name="downgrade.sqlite3"):
    """Run migration 002's downgrade() under the real alembic machinery.

    No stub and no recorded op calls: a real MigrationContext is configured against a
    real SQLite engine and real alembic Operations are installed, so op.drop_column
    executes actual ALTER TABLE DDL. Whatever downgrade() does is what the database ends
    up with.
    """
    migration = _migration_002()
    engine = _sqlite_migration_engine(tmp_path, name)
    _create_pre_002_schema(engine)
    # Put users into the post-002 state: role / is_admin added.
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR NOT NULL DEFAULT 'user'"))
        conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))

    tables_before = _table_names(engine)
    with engine.begin() as conn:
        context = MigrationContext.configure(conn)
        with Operations.context(context):
            # downgrade() must return normally instead of raising: alembic runs a
            # migration inside a transaction, so a raise after the DDL would roll the
            # drops back and leave the operator believing the reversal happened.
            assert migration.downgrade() is None

    return engine, tables_before


def test_migration_002_downgrade_drops_only_the_columns_and_keeps_the_tables(tmp_path):
    """downgrade() reverses the columns and returns, leaving the three tables intact."""
    engine, tables_before = _run_downgrade_on_real_sqlite(tmp_path)
    try:
        # The columns this revision added are gone from the real schema.
        assert _column_names(engine, "users") == ["id", "username", "password_hash"]
        # The tables survive - they may predate revision 002 (Base.metadata.create_all).
        assert _table_names(engine) == tables_before
        assert "user_sessions" in tables_before and "push_subscriptions" in tables_before
    finally:
        engine.dispose()


def test_migration_002_downgrade_is_safe_to_re_run(tmp_path):
    """Re-running downgrade() is a no-op: nothing raised, nothing further dropped."""
    migration = _migration_002()
    engine = _sqlite_migration_engine(tmp_path, "downgrade_rerun.sqlite3")
    try:
        _create_pre_002_schema(engine)
        # users still has role / is_admin, so the first run has real work to do.
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR NOT NULL DEFAULT 'user'"))
            conn.execute(text("ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"))

        tables_before = _table_names(engine)

        for run in ("first", "second"):
            with engine.begin() as conn:
                context = MigrationContext.configure(conn)
                with Operations.context(context):
                    assert migration.downgrade() is None
            assert _column_names(engine, "users") == ["id", "username", "password_hash"], run
            assert _table_names(engine) == tables_before, run
    finally:
        engine.dispose()


def test_migration_002_downgrade_leaves_a_database_without_users_alone(tmp_path):
    """A database with no users table is not an error and produces no DDL."""
    migration = _migration_002()
    engine = _sqlite_migration_engine(tmp_path, "downgrade_empty.sqlite3")
    try:
        with engine.begin() as conn:
            context = MigrationContext.configure(conn)
            with Operations.context(context):
                assert migration.downgrade() is None
        assert _table_names(engine) == []
    finally:
        engine.dispose()





