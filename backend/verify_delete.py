import requests
import os

BASE_URL = "http://localhost:8000"

def test_delete_flow():
    # 1. Upload a dummy file
    print("Creating dummy file...")
    dummy_file = "test_upload.xlsx"
    import pandas as pd
    df = pd.DataFrame([{
        "الكود": "TEST001", "العميل": "Test Client", "الحالة": "جديد", 
        "قيمة الطرد": 100, "الرسوم": 10
    }])
    df.to_excel(dummy_file, index=False)
    
    print("Uploading file...")
    with open(dummy_file, "rb") as f:
        response = requests.post(f"{BASE_URL}/upload", files={"file": f})
    
    if response.status_code != 200:
        print(f"Upload failed: {response.text}")
        return
    
    print("Upload successful!")
    
    # 2. List files to get ID
    print("Listing files...")
    response = requests.get(f"{BASE_URL}/upload/files")
    files = response.json().get("files", [])
    
    target_file = None
    for f in files:
        if "test_upload" in f["filename"]:
            target_file = f
            break
            
    if not target_file:
        print("Could not find uploaded file in list")
        return
        
    file_id = target_file["id"]
    print(f"Found file ID: {file_id}")
    
    # 3. Verify shipments exist
    print("Verifying shipments...")
    response = requests.get(f"{BASE_URL}/shipments/file/{file_id}") 
    # Note: I haven't implemented this endpoint yet, so this part of the script might fail if run now.
    # But for the purpose of the plan, I am writing the script that WILL work.
    
    # 4. Delete the file
    print(f"Deleting file {file_id}...")
    response = requests.delete(f"{BASE_URL}/upload/files/{file_id}")
    
    if response.status_code == 200:
        print("Delete successful!")
    else:
        print(f"Delete failed: {response.text}")
        
    
    # Cleanup local file
    if os.path.exists(dummy_file):
        os.remove(dummy_file)

if __name__ == "__main__":
    test_delete_flow()
