"""
Seed Script — Insert 2 default users into the database.
Run: python seed_users.py

Checks for existing users by username to avoid duplicates.
"""
import bcrypt
from database import SessionLocal, User, create_tables

# ──────────────────────────────────────────────
# ⚠️  CHANGE THESE BEFORE DEPLOYING TO PROD  ⚠️
# ──────────────────────────────────────────────
SEED_USERS = [
    {"username": "omar",  "password": "omarelders1968$$"},
    {"username": "mariam",  "password": "mariamelders1968$$"},
]


def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def seed():
    # Ensure tables exist
    create_tables()

    db = SessionLocal()
    try:
        for user_data in SEED_USERS:
            hashed = hash_password(user_data["password"])
            
            existing = db.query(User).filter(User.username == user_data["username"]).first()
            if existing:
                print(f"🔄 User '{user_data['username']}' exists — updating password...")
                existing.password_hash = hashed
            else:
                print(f"✅ Creating new user '{user_data['username']}'...")
                new_user = User(
                    username=user_data["username"],
                    password_hash=hashed,
                )
                db.add(new_user)
            
            db.commit()

        print("\n🎉 Seeding complete!")
    except Exception as e:
        db.rollback()
        print(f"❌ Seeding failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
