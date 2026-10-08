"""Add users, user_sessions, and push_subscriptions tables and role columns

Revision ID: 002_user_roles_and_auth
Revises: 001_baseline
Create Date: 2026-10-07

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '002_user_roles_and_auth'
down_revision: Union[str, None] = '001_baseline'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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


def downgrade() -> None:
    pass
