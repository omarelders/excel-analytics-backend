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
# characters). It now stores the SHA-256 hex digest of that token
# (hashlib.sha256(token).hexdigest() -> 64 characters), which is why the column is
# declared String(64) below. See routers/auth.py (login/logout) and
# dependencies.get_current_user, which hash before lookup.
SESSION_TOKEN_HASH_LENGTH = 64

TABLES_CREATED_BY_THIS_REVISION = ("users", "user_sessions", "push_subscriptions")


def table_exists(conn, table_name):
    """Check if a table exists in the database.

    Uses the SQLAlchemy inspector rather than a raw information_schema query.
    information_schema is namespace-global, so querying it with no table_schema
    filter also sees same-named tables in other schemas: on a database whose
    search_path is not 'public', a foreign 'users' would make this report True and
    upgrade() would silently skip adding role/is_admin while printing
    "users table already exists". The inspector resolves through the connection's
    own current schema, so it only ever sees what this connection can see.
    """
    return bool(inspect(conn).has_table(table_name))


def column_exists(conn, table_name, column_name):
    """Check if a column exists in a table.

    False when the table does not exist at all, so callers can check a table and its
    column independently without the inspector raising.
    """
    if not inspect(conn).has_table(table_name):
        return False
    return any(column["name"] == column_name for column in inspect(conn).get_columns(table_name))


def invalidate_legacy_sessions(conn):
    """Delete every session row that predates this revision. One-time, unconditional.

    user_sessions.token changes here from a plaintext uuid4 session token to the
    SHA-256 hash of that token, so every row written before this revision can no
    longer be matched by dependencies.get_current_user and is dead data. Deleting it
    explicitly - rather than leaving it to rot - is what logs every user out ONCE:
    users log in again (passwords are untouched), and lost admins are recovered with
    'python scripts/promote_admin.py <username>'.

    The DELETE is deliberately unconditional. Idempotency is free - after the first
    run the table is empty, so a re-run deletes zero rows - whereas filtering on
    token shape would leave any legacy plaintext token that happens to be 64
    characters long behind as a dead row while the migration still reported success.
    """
    if not inspect(conn).has_table("user_sessions"):
        print("[MIGRATION] user_sessions table does not exist - no sessions to invalidate")
        return 0

    result = conn.execute(text("DELETE FROM user_sessions"))
    deleted = result.rowcount or 0
    print(
        f"[MIGRATION] Invalidated {deleted} pre-existing session row(s). "
        "user_sessions.token changed from a plaintext uuid4 session token to the SHA-256 hash "
        "of that token, so every user is logged out ONCE and simply logs in again "
        "(passwords are untouched)."
    )
    return deleted


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
            sa.Column('token', sa.String(length=SESSION_TOKEN_HASH_LENGTH), nullable=False),
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
    """Reverse 002: drop the role / is_admin columns this revision added.

    This function returns normally instead of raising, because raising would be worse
    than useless in both directions:

    * On a transactional-DDL backend such as Postgres, alembic runs the migration inside
      a transaction, so an exception now would roll the column drops below back - the
      operator is told the reversal succeeded while the schema is untouched.
    * On SQLite the driver auto-commits DDL, so the drops would already be applied
      before the raise fires.

    Either way an exception here misleads the operator about what actually happened, so
    the genuinely irreversible parts of this revision are recorded in this docstring
    rather than simulated with a rolled-back exception:

    * The pre-existing user_sessions rows deleted by invalidate_legacy_sessions() in
      upgrade() cannot be restored - they are gone from the moment 002 ran, and
      re-running upgrade() will not bring them back.
    * The role / is_admin values dropped below cannot be restored: after this
      downgrade nobody can tell any more who was an admin. Re-grant admin with
      'python scripts/promote_admin.py <username>'.

    The three tables are left in place on purpose. upgrade() creates each of them only
    when it is absent, so any of them may have existed long before this revision - the
    application also creates the schema through Base.metadata.create_all(). Dropping a
    table here would be silent data loss for exactly the accounts this revision's
    recovery script exists to restore. An operator who really wants one gone must drop
    it by hand, knowing what it holds.
    """
    conn = op.get_bind()

    if not table_exists(conn, "users"):
        print("[MIGRATION] users table does not exist - nothing to reverse")
        return

    for column_name in ("role", "is_admin"):
        if column_exists(conn, "users", column_name):
            op.drop_column("users", column_name)
            print(f"[MIGRATION] Dropped {column_name} column from users")
        else:
            print(f"[MIGRATION] users.{column_name} column already absent")

    for table_name in TABLES_CREATED_BY_THIS_REVISION:
        print(
            f"[MIGRATION] Table {table_name} left in place - it may predate revision 002 "
            "(the app also creates it via Base.metadata.create_all). Drop it by hand if that "
            "is intended."
        )
