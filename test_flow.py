import os
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import database
from database import Base
from main import app
from dependencies import get_current_user

# Ensure StaticPool is configured so all connections share in-memory tables
if not hasattr(database, "_is_test_pool") or not database._is_test_pool:
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    database.engine = test_engine
    database.SessionLocal = TestSessionLocal
    database._is_test_pool = True


def test_flow():
    Base.metadata.create_all(bind=database.engine)
    app.dependency_overrides[get_current_user] = lambda: {"id": 1, "username": "flow_tester", "role": "admin", "is_admin": True}
    client = TestClient(app)

    dummy_file = "test_upload_client.xlsx"
    df = pd.DataFrame([{
        "الكود": "TEST_CLIENT_001", 
        "العميل": "Test Client", 
        "الحالة": "جديد", 
        "قيمة الطرد": 100, 
        "الرسوم": 10,
        "التاريخ": "2025-01-01"
    }])
    df.to_excel(dummy_file, index=False)
    
    try:
        # 2. Upload
        print("Uploading file...")
        with open(dummy_file, "rb") as f:
            response = client.post("/upload", files={"file": ("test_upload_client.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        
        print(f"Upload status: {response.status_code}")
        assert response.status_code == 200, f"Upload failed with status {response.status_code}: {response.text}"
            
        upload_data = response.json()
        assert upload_data.get("status") == "success"
        file_id = upload_data.get("file_id")
        assert file_id is not None
        
        # 3. List files
        print("Listing files...")
        response = client.get("/upload/files")
        assert response.status_code == 200
        files = response.json().get("files", [])
        print(f"Found {len(files)} files.")
        
        target_file = next((f for f in files if f["id"] == file_id), None)
        assert target_file is not None
        print("File found in list!")
        
        # 4. Get Data
        print(f"Fetching data for file {file_id}...")
        response = client.get(f"/shipments/file/{file_id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 1
        print("Data verified!")
        
        # 5. Delete file
        print(f"Deleting file {file_id}...")
        response = client.delete(f"/upload/files/{file_id}")
        assert response.status_code == 200
        print("Delete successful!")
        
        # 6. Verify Deletion
        response = client.get(f"/shipments/file/{file_id}")
        assert response.status_code == 404
        print("Verified file is gone!")
        
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        if os.path.exists(dummy_file):
            try:
                os.remove(dummy_file)
            except OSError:
                pass


if __name__ == "__main__":
    test_flow()
