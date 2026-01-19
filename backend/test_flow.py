from fastapi.testclient import TestClient
from backend.main import app
import pandas as pd
import os

client = TestClient(app)

def test_flow():
    # 1. Create dummy Excel
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
        if response.status_code != 200:
            print(f"Upload Response: {response.json()}")
            return
            
        upload_data = response.json()
        file_id = upload_data.get("file_id")
        print(f"File uploaded. ID: {file_id}")
        assert file_id is not None
        
        # 3. List files
        print("Listing files...")
        response = client.get("/upload/files")
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
        if os.path.exists(dummy_file):
            os.remove(dummy_file)
            
if __name__ == "__main__":
    test_flow()
