"""
promote_admin.py — grant admin to an existing user, or list every user's role.

Recovery path for migration 002 (alembic/versions/20261007_002_user_roles_and_auth.py):
`role` / `is_admin` were added with the server defaults 'user' / false, so every user
that already existed was downgraded to a non-admin and seed_users.py skips users that
are already present. This script is the only way back into an admin account.

It connects through database.py (DATABASE_URL from .env / environment) — no hardcoded URL.
It never asks for, accepts, or prints a password, and it never changes a password hash.

Usage:
    python scripts/promote_admin.py <username>   # grant admin to an existing user
    python scripts/promote_admin.py --list        # list all users with their role

Exit codes: 0 = success (including "already admin"), 1 = user not found / DB error,
2 = bad usage.
"""
import argparse
import os
import sys

# Make the repository root importable no matter where the script is invoked from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from database import SessionLocal, User  # noqa: E402  (import needs the path fix above)

ADMIN_ROLE = "admin"
LIST_HINT = "python scripts/promote_admin.py --list"


class UserNotFoundError(Exception):
    """Raised when the requested username does not exist in the database."""


def promote_user(db, username: str) -> str:
    """Grant admin to an existing user and return the operator-facing message.

    Idempotent: promoting a user who is already an admin succeeds with a "nothing
    changed" message. The password hash is never touched.
    """
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise UserNotFoundError(
            f"User '{username}' does not exist. Run '{LIST_HINT}' to see the available usernames."
        )

    already_admin = bool(getattr(user, "is_admin", False)) or getattr(user, "role", "user") == ADMIN_ROLE

    user.role = ADMIN_ROLE
    user.is_admin = True
    db.commit()

    if already_admin:
        return (
            f"[INFO] user '{username}' is already admin "
            f"(role='{ADMIN_ROLE}', is_admin=true) - nothing changed."
        )
    return (
        f"[SUCCESS] user '{username}' is now admin "
        f"(equivalent SQL: UPDATE users SET role='{ADMIN_ROLE}', is_admin=TRUE "
        f"WHERE username='{username}';)"
    )


def list_users(db) -> list:
    """Return every user as {id, username, role, is_admin} dicts, ordered by id."""
    users = db.query(User).order_by(User.id).all()
    return [
        {
            "id": user.id,
            "username": user.username,
            "role": getattr(user, "role", "user"),
            "is_admin": bool(getattr(user, "is_admin", False)),
        }
        for user in users
    ]


def format_users(users: list) -> str:
    """Render list_users() output as a plain-text table."""
    lines = [f"{'ID':<5} {'USERNAME':<24} {'ROLE':<10} IS_ADMIN", "-" * 48]
    for user in users:
        lines.append(
            f"{user['id']:<5} {user['username']:<24} {user['role']:<10} {str(user['is_admin']).lower()}"
        )
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="promote_admin.py",
        description="Grant admin privileges to an existing user (never asks for a password).",
    )
    parser.add_argument("username", nargs="?", help="username of the existing user to promote")
    parser.add_argument("--list", action="store_true", help="list all users with their role and exit")
    args = parser.parse_args(argv)

    if args.list:
        db = SessionLocal()
        try:
            users = list_users(db)
        except Exception as exc:  # keep operator-facing output free of tracebacks
            print(
                f"[ERROR] Could not list users: {exc}\n"
                "[HINT] Has the schema been created? Check DATABASE_URL, then run "
                "'python run_migrations.py' (or 'alembic upgrade head')."
            )
            return 1
        finally:
            db.close()
        if not users:
            print(
                "[WARN] No users found in the database. Seed one first with "
                "'python seed_users.py' and the SEED_*_PASSWORD variables set."
            )
        else:
            print(format_users(users))
        return 0

    if not args.username:
        parser.error(
            "a username is required, e.g. 'python scripts/promote_admin.py omar' "
            "(or use --list to see the existing usernames)"
        )

    db = SessionLocal()
    try:
        message = promote_user(db, args.username)
    except UserNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return 1
    except Exception as exc:  # keep operator-facing output free of tracebacks
        print(f"[ERROR] Could not promote '{args.username}': {exc}")
        return 1
    finally:
        db.close()

    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
