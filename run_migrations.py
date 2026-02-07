"""
Unified Migration Runner
========================

This script runs all pending Alembic migrations on the database.
It's safe to run multiple times - only pending migrations will be applied.

Usage:
    python run_migrations.py

For Heroku deployment, this is called automatically on startup.
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migrations():
    """Run all pending Alembic migrations"""
    from alembic.config import Config
    from alembic import command
    
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    alembic_cfg = Config(os.path.join(script_dir, "alembic.ini"))
    
    print("[MIGRATION] Starting database migrations...")
    
    try:
        # Run all pending migrations
        command.upgrade(alembic_cfg, "head")
        print("[MIGRATION] All migrations completed successfully!")
        return True
    except Exception as e:
        print(f"[MIGRATION] Error running migrations: {str(e)}")
        # If Alembic fails, fall back to create_tables
        print("[MIGRATION] Falling back to SQLAlchemy create_tables...")
        try:
            from database import create_tables
            create_tables()
            print("[MIGRATION] Fallback successful!")
            return True
        except Exception as e2:
            print(f"[MIGRATION] Fallback also failed: {str(e2)}")
            return False


def stamp_current():
    """Stamp current database state (for existing databases)"""
    from alembic.config import Config
    from alembic import command
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    alembic_cfg = Config(os.path.join(script_dir, "alembic.ini"))
    
    try:
        command.stamp(alembic_cfg, "head")
        print("[MIGRATION] Database stamped at head revision")
    except Exception as e:
        print(f"[MIGRATION] Error stamping: {str(e)}")


def show_current():
    """Show current migration status"""
    from alembic.config import Config
    from alembic import command
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    alembic_cfg = Config(os.path.join(script_dir, "alembic.ini"))
    
    try:
        command.current(alembic_cfg)
    except Exception as e:
        print(f"[MIGRATION] Error getting current: {str(e)}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "stamp":
            stamp_current()
        elif sys.argv[1] == "current":
            show_current()
        else:
            print("Usage: python run_migrations.py [stamp|current]")
    else:
        run_migrations()
