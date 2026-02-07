
from database import engine, ContentItem
from sqlalchemy import inspect
import sqlalchemy.exc

def force_db_fix():
    print("--- Fixing Content Calendar Database ---")
    
    # 1. Check if table exists
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Current tables: {tables}")
    
    if "content_items" in tables:
        print("Table 'content_items' ALREADY EXISTS.")
        # Check columns
        columns = [c['name'] for c in inspector.get_columns("content_items")]
        print(f"Columns: {columns}")
        
        # Verify required columns
        required = ["visual_idea", "content_type", "type", "date"] # type vs content_type check
        for req in required:
             if req == "type" and "content_type" in columns: continue # handled
             if req not in columns and req != "type":
                 print(f"WARNING: Column '{req}' might be missing!")
    else:
        print("Table 'content_items' MISSING. Creating it now...")
        try:
            ContentItem.__table__.create(bind=engine)
            print("SUCCESS: Table 'content_items' created!")
        except Exception as e:
            print(f"FAILED to create table: {e}")

if __name__ == "__main__":
    force_db_fix()
