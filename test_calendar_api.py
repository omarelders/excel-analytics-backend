
import requests
import json
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load env to get DB URL
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/dbname")  # Fallback just in case

# Fix for postgres:// vs postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def check_database_schema():
    print("--- Checking Database Schema ---")
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # Check if table exists
            result = conn.execute(text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'content_items')"
            ))
            exists = result.scalar()
            print(f"Table 'content_items' exists: {exists}")
            
            if exists:
                # Check columns
                result = conn.execute(text(
                    "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'content_items'"
                ))
                print("Columns:")
                for row in result:
                    print(f" - {row[0]}: {row[1]}")
            else:
                 print("CRITICAL: content_items table is MISSING!")
                 
    except Exception as e:
        print(f"Error checking DB: {e}")

def test_api_endpoint():
    print("\n--- Testing API Endpoint ---")
    url = "http://127.0.0.1:8000/api/content"
    
    payload = {
        "date": "2026-02-04",
        "title": "Test Item",
        "type": "video",
        "platforms": ["Insta", "TikTok"],
        "status": "To Shoot",
        "visualIdea": "Test valid idea"
    }
    
    try:
        print(f"Sending POST to {url}")
        response = requests.post(url, json=payload)
        
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Response: {response.json()}")
        except:
            print(f"Response Text: {response.text}")
            
    except Exception as e:
        print(f"Error calling API: {e}")

if __name__ == "__main__":
    check_database_schema()
    test_api_endpoint()
