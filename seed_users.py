"""
Seed Script — Insert default users into the database from environment variables.
Run: python seed_users.py

Checks for existing users by username to avoid duplicates and never overwrites existing passwords.

A seed password longer than bcrypt's 72-byte limit is refused rather than truncated:
bcrypt hashes only those first 72 bytes, so "A"*72 and "A"*72+"extra" would be stored as - and
later log in as - the same credential, silently.
"""
import os
import sys
import bcrypt
from dotenv import load_dotenv
from database import SessionLocal, User, create_tables

# One definition of the limit, shared with the login verifier: seeding must hash
# exactly the bytes routers.auth.verify_password reads back.
from routers.auth import MAX_PASSWORD_BYTES

load_dotenv()


class PasswordTooLongError(ValueError):
    """A seed password is longer than the 72 bytes bcrypt will actually use."""


def reject_overlong_password(password: str, source: str) -> None:
    """Refuse a seed password past the 72-byte limit instead of truncating it.

    Truncating would hash only the password's own prefix, so two different
    strings would set the same credential and nobody who typed the longer one
    would ever be told their extra characters were ignored. `source` is what
    the operator has to change - the environment variable holding the value -
    and it is named in the error so the failure is actionable.
    """
    length = len(password.encode("utf-8"))
    if length > MAX_PASSWORD_BYTES:
        raise PasswordTooLongError(
            f"{source} is {length} bytes long - {length - MAX_PASSWORD_BYTES} byte(s) more than "
            f"bcrypt can use. bcrypt hashes only the first {MAX_PASSWORD_BYTES} bytes of a "
            f"password, so a longer one would be stored, and accepted at login, as its own "
            f"{MAX_PASSWORD_BYTES}-byte prefix. Set {source} to at most {MAX_PASSWORD_BYTES} "
            f"bytes and run 'python seed_users.py' again."
        )


def hash_password(password: str) -> str:
    """Hash a password using bcrypt, rejecting anything over the 72-byte limit"""
    reject_overlong_password(password, "the seed password")
    salt = bcrypt.gensalt()
    pw_bytes = password.encode('utf-8')[:MAX_PASSWORD_BYTES]
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

    # Checked before the first DB write: an over-long password must fail here,
    # loudly and with nothing half-created, instead of being hashed from its own
    # prefix. SEED_OMAR_PASSWORD and SEED_MARIAM_PASSWORD fall back to
    # SEED_ADMIN_PASSWORD, so it is the one that is most often the culprit.
    for source, password in (
        ("SEED_ADMIN_PASSWORD", seed_admin_pw),
        ("SEED_OMAR_PASSWORD", seed_omar_pw),
        ("SEED_MARIAM_PASSWORD", seed_mariam_pw),
    ):
        if password:
            reject_overlong_password(password, source)

    db = None
    try:
        db = SessionLocal()
        for user_data in seed_candidates:
            username = user_data["username"]
            password = user_data["password"]

            existing = db.query(User).filter(User.username == username).first()
            if existing:
                # Migration 002 gave every pre-existing user role='user' / is_admin=false,
                # and seeding never overwrites an existing row. Never leave the operator
                # with a silent skip: tell them exactly how to get admin back.
                if getattr(existing, "is_admin", False) or getattr(existing, "role", "user") == "admin":
                    print(f"[INFO] User '{username}' exists and already has admin privileges (role='{existing.role}') - skipping overwrite.")
                else:
                    print(f"[INFO] User '{username}' exists and is role='{existing.role}'; run 'python scripts/promote_admin.py {username}' to grant admin.")
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
    # An over-long seed password is an operator error worth a non-zero exit code,
    # not a traceback: the message already says which variable to change.
    try:
        seed()
    except PasswordTooLongError as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)
