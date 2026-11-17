"""
Integration and unit tests for Content Calendar API and backend bug fixes.
"""
import base64
import io
import os
import pandas as pd
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ENV", "production")
os.environ.setdefault("TRUSTED_PROXY_COUNT", "1")

import database
import dependencies
from database import Base, Shipment, UploadedFile, PaymentFile, PaymentRecord
from main import app
from test_security_fixes import test_engine, TestSessionLocal


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    dependencies.limiter.reset()
    app.dependency_overrides.clear()
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "SessionLocal", TestSessionLocal)
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[dependencies.get_current_user] = lambda: {
        "id": 1,
        "username": "admin",
        "role": "admin",
        "is_admin": True,
    }
    yield
    dependencies.limiter.reset()
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)


def test_content_calendar_crud_and_date_validation():
    """Verify content calendar create, read, update, move, date pattern validation, and delete."""
    client = TestClient(app)

    # 1. Invalid date rejected on create
    bad_create = client.post(
        "/api/content",
        json={"date": "04-02-2026", "title": "Invalid Date"},
    )
    assert bad_create.status_code == 422

    # 2. Valid create
    payload = {
        "date": "2026-02-04",
        "title": "Test Item",
        "type": "video",
        "platforms": ["Insta", "TikTok"],
        "status": "To Shoot",
        "visualIdea": "Test valid idea",
    }
    res_create = client.post("/api/content", json=payload)
    assert res_create.status_code == 200
    created = res_create.json()
    item_id = created["id"]
    assert created["date"] == "2026-02-04"
    assert created["title"] == "Test Item"
    assert created["platforms"] == ["Insta", "TikTok"]

    # 3. Get items
    res_get = client.get("/api/content?date_from=2026-02-01&date_to=2026-02-28")
    assert res_get.status_code == 200
    assert res_get.json()["total"] == 1
    assert res_get.json()["data"][0]["id"] == item_id

    # 4. Invalid date rejected on update
    bad_update = client.put(f"/api/content/{item_id}", json={"date": "not-a-date"})
    assert bad_update.status_code == 422

    # 5. Valid update
    res_update = client.put(
        f"/api/content/{item_id}",
        json={"title": "Updated Title", "status": "Ready"},
    )
    assert res_update.status_code == 200
    assert res_update.json()["title"] == "Updated Title"
    assert res_update.json()["status"] == "Ready"

    # 6. Invalid date rejected on move
    bad_move = client.patch(f"/api/content/{item_id}/move?new_date=2026/02/10")
    assert bad_move.status_code == 422

    # 7. Valid move
    res_move = client.patch(f"/api/content/{item_id}/move?new_date=2026-02-10")
    assert res_move.status_code == 200
    assert res_move.json()["new_date"] == "2026-02-10"

    # 8. Delete
    res_del = client.delete(f"/api/content/{item_id}")
    assert res_del.status_code == 200
    assert client.get("/api/content").json()["total"] == 0


def test_payment_upload_cleaning_and_nat_handling():
    """Verify payment upload handles empty date strings (pd.NaT), float strings, and phone numbers."""
    client = TestClient(app)

    excel_io = io.BytesIO()
    df = pd.DataFrame([
        {
            "الكود ": "1001.0",
            "المستحق": "1,250.50",
            "التاريخ": "2026-02-04",
            "تاريخ التوصيل": "",
            "تاريخ التسليم/الإلغاء": "invalid-date",
            "هاتف المستلم": 1012345678.0,
            "عدد القطع": "3",
            "قيمة التسليم": 1500,
            "الرسوم المستحقة": 249.5,
        }
    ])
    df.to_excel(excel_io, index=False, engine="openpyxl")
    excel_io.seek(0)

    res = client.post(
        "/payments/upload",
        files={"file": ("payments.xlsx", excel_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "success"
    assert body["rows_inserted"] == 1
    file_id = body["file_id"]

    data_res = client.get(f"/payments/files/{file_id}/data")
    assert data_res.status_code == 200
    row = data_res.json()["data"][0]
    assert row["الكود"] == "1001"
    assert row["المستحق"] == 1250.5
    assert row["هاتف المستلم"] == "1012345678"
    assert row["عدد القطع"] == 3
    assert row["تاريخ التوصيل"] is None
    assert row["تاريخ التسليم/الإلغاء"] is None

    # Empty or unrecognized columns Excel should return 400
    bad_excel = io.BytesIO()
    pd.DataFrame([{"foo": "bar"}]).to_excel(bad_excel, index=False, engine="openpyxl")
    bad_excel.seek(0)
    res_bad = client.post(
        "/payments/upload",
        files={"file": ("bad_payments.xlsx", bad_excel, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res_bad.status_code == 400


def test_vapid_public_key_is_65_byte_uncompressed_point():
    """Verify GET /notifications/vapid-key returns 65-byte uncompressed P-256 point in base64url."""
    client = TestClient(app)
    res = client.get("/notifications/vapid-key")
    assert res.status_code == 200
    pub_b64 = res.json()["publicKey"]
    assert "=" not in pub_b64

    padded = pub_b64 + "=" * (-len(pub_b64) % 4)
    raw = base64.urlsafe_b64decode(padded)
    assert len(raw) == 65
    assert raw[0] == 0x04

    # Verify SubscriptionSchema validates keys
    bad_sub = client.post("/notifications/subscribe", json={"endpoint": "https://push.example/1", "keys": {}})
    assert bad_sub.status_code == 422

    good_sub = client.post(
        "/notifications/subscribe",
        json={"endpoint": "https://push.example/1", "keys": {"p256dh": "k1", "auth": "a1"}},
    )
    assert good_sub.status_code == 200


def test_shipment_upload_error_returns_400_and_status_update_from_any_status():
    """Verify shipment upload errors return HTTP 400 and status updates work from 'جديد' or None."""
    client = TestClient(app)

    # 1. Uploading Excel with no valid shipment codes returns HTTP 400 (not 200 OK)
    empty_codes_io = io.BytesIO()
    pd.DataFrame([{"العميل": "ClientOnly"}]).to_excel(empty_codes_io, index=False, engine="openpyxl")
    empty_codes_io.seek(0)
    res_err = client.post(
        "/upload",
        files={"file": ("no_codes.xlsx", empty_codes_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res_err.status_code == 400

    # 2. Valid shipment upload with status 'جديد'
    valid_io = io.BytesIO()
    pd.DataFrame([
        {"الكود": "SHP100", "العميل": "ClientA", "الحالة": "جديد", "قيمة الطرد": 250, "هاتف المستلم": 1098765432.0},
        {"الكود": "SHP101", "العميل": "ClientB", "الحالة": None, "قيمة الطرد": 150},
    ]).to_excel(valid_io, index=False, engine="openpyxl")
    valid_io.seek(0)
    res_ok = client.post(
        "/upload",
        files={"file": ("valid_shipments.xlsx", valid_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res_ok.status_code == 200
    file_id = res_ok.json()["file_id"]

    # 3. Updating status from 'جديد' and None to 'تم التسليم' succeeds
    res_status = client.patch("/shipments/SHP100/status?new_status=تم التسليم")
    assert res_status.status_code == 200
    assert res_status.json()["old_status"] == "جديد"
    assert res_status.json()["new_status"] == "تم التسليم"

    # 4. Analytics includes shipment with status=None in total_value (250 + 150 = 400)
    res_analytics = client.get("/api/analytics")
    assert res_analytics.status_code == 200
    assert res_analytics.json()["summary"]["total_value"] == 400.0

    # 5. Soft-deleting SHP101 updates /upload/files record_count and allows re-uploading SHP101
    assert client.delete("/shipments/SHP101").status_code == 200
    files_list = client.get("/upload/files").json()["files"]
    assert files_list[0]["id"] == file_id
    assert files_list[0]["record_count"] == 1

    reupload_io = io.BytesIO()
    pd.DataFrame([{"الكود": "SHP101", "العميل": "ClientB", "الحالة": "جديد", "قيمة الطرد": 300}]).to_excel(
        reupload_io, index=False, engine="openpyxl"
    )
    reupload_io.seek(0)
    res_reupload = client.post(
        "/upload",
        files={"file": ("reupload.xlsx", reupload_io, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert res_reupload.status_code == 200
    assert res_reupload.json()["rows_inserted"] == 1

    # 6. Validate update_shipment bounds
    assert client.patch("/shipments/SHP100?amount=-10").status_code == 400
    assert client.patch(f"/shipments/SHP100?description={'x' * 2001}").status_code == 400
    assert client.patch("/shipments/SHP100?amount=500").status_code == 200

    # 7. Validate autocomplete respects limit
    res_auto = client.get("/shipments/autocomplete?query=SHP&limit=1")
    assert res_auto.status_code == 200
    assert len(res_auto.json()["suggestions"]) == 1
