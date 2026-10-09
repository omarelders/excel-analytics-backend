"""Add users, user_sessions, and push_subscriptions tables and role columns

Revision ID: 002_user_roles_and_auth
Revises: 001_baseline
Create Date: 2026-10-07

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text

# revision identifiers, used by Alembic.
revision: str = '002_user_roles_and_auth'
down_revision: Union[str, None] = '001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# user_sessions.token used to store the raw session token (str(uuid.uuid4()) -> 36
# characters). The application now stores the SHA-256 hex digest of that token
# (hashlib.sha256(token).hexdigest() -> 64 characters). See routers/auth.py
# (login/logout) and dependencies.get_current_user, which hash before lookup.
SESSION_TOKEN_HASH_LENGTH = 64


def table_exists(conn, table_name):
    """Check if a table exists in the database"""
    result = conn.execute(text(
        f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')"
    ))
    return result.scalar()


def column_exists(conn, table_name, column_name):
    """Check if a column exists in a table"""
    result = conn.execute(text(f"""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns 
            WHERE table_name = '{table_name}' AND column_name = '{column_name}'
        )
    """))
    return result.scalar()


def invalidate_legacy_sessions(conn):
    """Delete the session rows written by the pre-SHA-256 auth code.

    Returns the number of rows deleted (0 when there is nothing to do).

    Idempotency: only rows holding a pre-hash token (length != 64) are deleted.
    After the first run every remaining row is a SHA-256 hash, so a re-run
    deletes zero rows and cannot log anybody out a second time.
    """
    if not inspect(conn).has_table("user_sessions"):
        print("[MIGRATION] user_sessions table does not exist - no sessions to invalidate")
        return 0

    result = conn.execute(text(
        "DELETE FROM user_sessions WHERE length(token) <> :hash_length"
    ), {"hash_length": SESSION_TOKEN_HASH_LENGTH})
    deleted = result.rowcount or 0
    print(
        f"[MIGRATION] Invalidated {deleted} pre-existing session row(s) - token is now a SHA-256 hash, "
        "so every user is logged out ONCE and simply logs in again (passwords are untouched)."
    )
    return deleted


def table_is_empty(conn, table_name):
    """True when the table holds no rows at all.

    upgrade() creates users / user_sessions / push_subscriptions only when they are
    absent, so on a database where the app had already created them out-of-band
    (Base.metadata.create_all) revision 002 merely added columns to an existing,
    populated table. An empty table is therefore the only safe signal that this
    revision created the table itself and may drop it again on downgrade.
    """
    result = conn.execute(text(f"SELECT EXISTS (SELECT 1 FROM {table_name})"))
    return not result.scalar()


def upgrade() -> None:
    conn = op.get_bind()

    # ======== USERS TABLE ========
    if not table_exists(conn, 'users'):
        op.create_table(
            'users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('username', sa.String(), nullable=False),
            sa.Column('password_hash', sa.String(), nullable=False),
            sa.Column('role', sa.String(), nullable=False, server_default='user'),
            sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_users_id', 'users', ['id'])
        op.create_index('ix_users_username', 'users', ['username'], unique=True)
        print("[MIGRATION] Created users table")
    else:
        print("[MIGRATION] users table already exists")
        if not column_exists(conn, 'users', 'role'):
            op.add_column('users', sa.Column('role', sa.String(), nullable=False, server_default='user'))
            print("[MIGRATION] Added role column to users")
        if not column_exists(conn, 'users', 'is_admin'):
            op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
            print("[MIGRATION] Added is_admin column to users")

    # ======== USER SESSIONS TABLE ========
    if not table_exists(conn, 'user_sessions'):
        op.create_table(
            'user_sessions',
            sa.Column('token', sa.String(length=64), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
            sa.PrimaryKeyConstraint('token')
        )
        op.create_index('ix_user_sessions_token', 'user_sessions', ['token'])
        print("[MIGRATION] Created user_sessions table")
    else:
        print("[MIGRATION] user_sessions table already exists")

    # ======== PUSH SUBSCRIPTIONS TABLE ========
    if not table_exists(conn, 'push_subscriptions'):
        op.create_table(
            'push_subscriptions',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('endpoint', sa.String(), nullable=True),
            sa.Column('p256dh', sa.String(), nullable=False),
            sa.Column('auth', sa.String(), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_push_subscriptions_id', 'push_subscriptions', ['id'])
        op.create_index('ix_push_subscriptions_endpoint', 'push_subscriptions', ['endpoint'], unique=True)
        print("[MIGRATION] Created push_subscriptions table")
    else:
        print("[MIGRATION] push_subscriptions table already exists")

    # ======== DELIBERATE SESSION INVALIDATION (ONE-TIME BREAKING CHANGE) ========
    # user_sessions.token is changing from a plaintext uuid4 session token to the
    # SHA-256 hash of that token, so every session row written before this revision
    # can no longer be matched by dependencies.get_current_user and is dead data.
    # It is deleted explicitly here instead of being left behind as an accident:
    # this logs ALL users out ONCE. Nobody is permanently locked out - users log in
    # again (passwords are untouched), and lost admins are recovered with
    # 'python scripts/promote_admin.py <username>'.
    invalidate_legacy_sessions(conn)


def downgrade() -> None:
    """Reverse 002: undo the role/is_admin columns and the tables this revision created."""
    conn = op.get_bind()

    # 1. Undo the column additions (dropping users below would remove them anyway).
    if table_exists(conn, "users"):
        if column_exists(conn, "users", "role"):
            op.drop_column("users", "role")
            print("[MIGRATION] Dropped role column from users")
        if column_exists(conn, "users", "is_admin"):
            op.drop_column("users", "is_admin")
            print("[MIGRATION] Dropped is_admin column from users")

    # 2. Undo the table creation, but only for tables this revision provably created.
    #    A populated users/user_sessions table predates 002 (the app creates tables via
    #    Base.metadata.create_all as well), and dropping it on downgrade would destroy
    #    the very accounts the recovery script exists to restore - so it is kept.
    for table_name in ("user_sessions", "push_subscriptions", "users"):
        if not table_exists(conn, table_name):
            print(f"[MIGRATION] {table_name} table already absent")
            continue
        if not table_is_empty(conn, table_name):
            print(
                f"[MIGRATION] {table_name} table is NOT empty - left in place (dropping it "
                f"would delete rows that predate revision 002). Drop it by hand if you are sure."
            )
            continue
        op.drop_table(table_name)
        print(f"[MIGRATION] Dropped {table_name} table")

    # 3. The reversal is deliberately incomplete, and the operator is told exactly why:
    #    the pre-existing session rows deleted by upgrade() cannot be restored, and the
    #    role/is_admin columns are gone, so nobody can tell any more who was an admin.
    raise NotImplementedError(
        "002_user_roles_and_auth cannot be fully downgraded. What was reversed: the "
        "role/is_admin columns, and any of users/user_sessions/push_subscriptions that "
        "002 itself created (left empty by this downgrade). What cannot be reversed: the "
        "pre-existing user_sessions rows deleted during upgrade(), which are unrecoverable, "
        "and the removed role/is_admin values - after downgrading, re-grant admin with "
        "'python scripts/promote_admin.py <username>'. Populated tables were kept on "
        "purpose because they predate this revision; drop them by hand if you are sure."
    )
