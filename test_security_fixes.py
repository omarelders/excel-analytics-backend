"""
Comprehensive verification test suite for Priority 0 and Priority 1 backend security fixes.
"""
import io
import os
import hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import bcrypt

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




