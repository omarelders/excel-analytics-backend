"""
Migration script to create the notes table in existing databases.
Run this script once to add the notes table for voice recording feature.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Fix for postgres:// vs postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    print("[ERROR] DATABASE_URL not found in .env file!")
    exit(1)

def create_notes_table():
    """Create the notes table if it doesn't exist"""
    try:
        engine = create_engine(DATABASE_URL)
        
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS notes (
            id SERIAL PRIMARY KEY,
            title VARCHAR NOT NULL,
            content TEXT,
            audio_data BYTEA,
            audio_duration FLOAT,
            note_type VARCHAR DEFAULT 'text',
            color VARCHAR DEFAULT 'yellow',
            is_favorite BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS ix_notes_id ON notes(id);
        CREATE INDEX IF NOT EXISTS ix_notes_is_favorite ON notes(is_favorite);
        CREATE INDEX IF NOT EXISTS ix_notes_note_type ON notes(note_type);
        """
        
        with engine.connect() as conn:
            conn.execute(text(create_table_sql))
            conn.commit()
            print("[SUCCESS] Notes table created successfully!")
            
            # Verify table exists
            result = conn.execute(text(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'notes'"
            ))
            columns = [row[0] for row in result]
            print(f"[INFO] Notes table columns: {columns}")
            
    except Exception as e:
        print(f"[ERROR] Error creating notes table: {str(e)}")
        raise

if __name__ == "__main__":
    print("[INFO] Starting notes table migration...")
    create_notes_table()
    print("[SUCCESS] Migration complete!")
