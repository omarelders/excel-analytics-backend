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

Exit codes:
    0 = success (including "already admin")
    1 = the username does not exist
    2 = bad usage
    3 = environment or schema error (unreachable database, missing users table, ...)
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

EXIT_OK = 0
EXIT_USER_NOT_FOUND = 1
EXIT_USAGE = 2
EXIT_ENVIRONMENT = 3

SCHEMA_HINT = (
    "[HINT] Is the database reachable and has the schema been created? Check DATABASE_URL, "
    "then run 'python run_migrations.py' (or 'alembic upgrade head')."
)


class UserNotFoundError(Exception):
    """Raised when the requested username does not exist in the database."""


def report_environment_error(action: str, exc: Exception) -> int:
    """Print an environment/schema failure and return the matching exit code.

    An unreachable database, a missing users table and a permission failure are
    different problems, and none of them means "that user does not exist", so they get
    their own exit code and the schema hint instead of being folded into a generic
    "could not promote" line.
    """
    print(f"[ERROR] {action}: {exc}")
    print(SCHEMA_HINT)
    return EXIT_ENVIRONMENT


def promote_user(db, username: str) -> str:
    """Grant admin to an existing user and return the operator-facing message.

    Idempotent: a user who is already an admin is a no-op success - checked before any
    write, so a re-run neither touches the row nor opens a transaction. The password
    hash is never touched.
    """
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise UserNotFoundError(
            f"User '{username}' does not exist. Run '{LIST_HINT}' to see the available usernames."
        )

    if bool(getattr(user, "is_admin", False)) or getattr(user, "role", "user") == ADMIN_ROLE:
        return (
            f"[INFO] user '{username}' is already admin "
            f"(role='{ADMIN_ROLE}', is_admin=true) - nothing changed."
        )

    user.role = ADMIN_ROLE
    user.is_admin = True
    db.commit()

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
        try:
            db = SessionLocal()
        except Exception as exc:  # unbound engine, bad URL...
            return report_environment_error("Could not connect to the database", exc)
        try:
            users = list_users(db)
        except Exception as exc:  # missing users table, no permission...
            return report_environment_error("Could not list users", exc)
        finally:
            db.close()
        if not users:
            print(
                "[WARN] No users found in the database. Seed one first with "
                "'python seed_users.py' and the SEED_*_PASSWORD variables set."
            )
        else:
            print(format_users(users))
        return EXIT_OK

    if not args.username:
        parser.error(
            "a username is required, e.g. 'python scripts/promote_admin.py omar' "
            "(or use --list to see the existing usernames)"
        )

    # Session construction is inside the try on purpose: if SessionLocal() itself
    # raises (unbound engine, bad DATABASE_URL) the operator must get an exit code and
    # a hint, not a traceback.
    db = None
    try:
        db = SessionLocal()
        message = promote_user(db, args.username)
    except UserNotFoundError as exc:
        print(f"[ERROR] {exc}")
        return EXIT_USER_NOT_FOUND
    except Exception as exc:  # keep operator-facing output free of tracebacks
        return report_environment_error(f"Could not promote '{args.username}'", exc)
    finally:
        if db is not None:
            db.close()

    print(message)
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
