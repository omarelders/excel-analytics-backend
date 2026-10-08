"""
Seed Script — Insert default users into the database from environment variables.
Run: python seed_users.py

Checks for existing users by username to avoid duplicates and never overwrites existing passwords.
"""
import os
import bcrypt
from dotenv import load_dotenv
from database import SessionLocal, User, create_tables

load_dotenv()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt with 72-byte safe truncation"""
    salt = bcrypt.gensalt()
    pw_bytes = password.encode('utf-8')[:72]
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode('utf-8')


def seed():
    # Ensure tables exist
    create_tables()

    seed_admin_pw = os.getenv("SEED_ADMIN_PASSWORD")
    seed_omar_pw = os.getenv("SEED_OMAR_PASSWORD") or seed_admin_pw
    seed_mariam_pw = os.getenv("SEED_MARIAM_PASSWORD") or seed_admin_pw

    seed_candidates = []
    if seed_omar_pw:
        seed_candidates.append({"username": "omar", "password": seed_omar_pw})
    if seed_mariam_pw:
        seed_candidates.append({"username": "mariam", "password": seed_mariam_pw})

    if not seed_candidates:
        print("[INFO] No seed passwords provided via environment variables (SEED_ADMIN_PASSWORD / SEED_OMAR_PASSWORD / SEED_MARIAM_PASSWORD). Skipping seeding.")
        return

    db = None
    try:
        db = SessionLocal()
        for user_data in seed_candidates:
            username = user_data["username"]
            password = user_data["password"]

            existing = db.query(User).filter(User.username == username).first()
            if existing:
                print(f"[INFO] User '{username}' already exists - skipping overwrite.")
                continue

            print(f"[SUCCESS] Creating new user '{username}'...")
            hashed = hash_password(password)
            new_user = User(
                username=username,
                password_hash=hashed,
                role="admin",
                is_admin=True,
            )
            db.add(new_user)
            db.commit()

        print("\n[SUCCESS] Seeding complete!")
    except Exception as e:
        if db:
            db.rollback()
        print(f"[ERROR] Seeding failed: {e}")
    finally:
        if db:
            db.close()


if __name__ == "__main__":
    seed()
