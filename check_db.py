from database import engine
from sqlalchemy import text

def check_connection():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            print("✅ CONNECTION SUCCESSFUL!")
            print(f"Test Query Result: {result.fetchone()[0]}")
    except Exception as e:
        print("❌ CONNECTION FAILED")
        print(str(e))

if __name__ == "__main__":
    check_connection()
