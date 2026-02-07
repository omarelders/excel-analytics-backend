"""Initial baseline migration - all existing tables

Revision ID: 001_baseline
Revises: 
Create Date: 2026-02-04

This migration represents the baseline state of the database.
It creates all tables if they don't exist (safe for existing databases).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = '001_baseline'
down_revision: Union[str, None] = None
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
    """Create all tables if they don't exist"""
    conn = op.get_bind()
    
    # ======== UPLOADED FILES TABLE ========
    if not table_exists(conn, 'uploaded_files'):
        op.create_table('uploaded_files',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('filename', sa.String(), nullable=True),
            sa.Column('upload_date', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_uploaded_files_id', 'uploaded_files', ['id'])
        op.create_index('ix_uploaded_files_filename', 'uploaded_files', ['filename'])
        print("[MIGRATION] Created uploaded_files table")
    else:
        print("[MIGRATION] uploaded_files table already exists")
    
    # ======== SHIPMENTS TABLE ========
    if not table_exists(conn, 'shipments'):
        op.create_table('shipments',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('file_id', sa.Integer(), nullable=True),
            sa.Column('الكود', sa.String(), nullable=True),
            sa.Column('العميل', sa.String(), nullable=True),
            sa.Column('المستلم', sa.String(), nullable=True),
            sa.Column('رقم المستلم', sa.String(), nullable=True),
            sa.Column('رقم المستلم 2', sa.String(), nullable=True),
            sa.Column('مدينة المستلم', sa.String(), nullable=True),
            sa.Column('منطقة المستلم', sa.String(), nullable=True),
            sa.Column('العنوان', sa.Text(), nullable=True),
            sa.Column('قيمة الطرد', sa.Float(), nullable=True),
            sa.Column('نوع السعر', sa.String(), nullable=True),
            sa.Column('الحالة', sa.String(), nullable=True),
            sa.Column('تاريخ الشحنة', sa.DateTime(), nullable=True),
            sa.Column('الوصف', sa.Text(), nullable=True),
            sa.Column('ملاحظات', sa.Text(), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), nullable=True, default=False),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['file_id'], ['uploaded_files.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_shipments_id', 'shipments', ['id'])
        op.create_index('ix_shipments_code', 'shipments', ['الكود'])
        op.create_index('ix_shipments_is_deleted', 'shipments', ['is_deleted'])
        print("[MIGRATION] Created shipments table")
    else:
        print("[MIGRATION] shipments table already exists")
        # Add missing columns if needed
        if not column_exists(conn, 'shipments', 'is_deleted'):
            op.add_column('shipments', sa.Column('is_deleted', sa.Boolean(), default=False))
            print("[MIGRATION] Added is_deleted column to shipments")
        if not column_exists(conn, 'shipments', 'deleted_at'):
            op.add_column('shipments', sa.Column('deleted_at', sa.DateTime(), nullable=True))
            print("[MIGRATION] Added deleted_at column to shipments")
        if not column_exists(conn, 'shipments', 'نوع السعر'):
            op.add_column('shipments', sa.Column('نوع السعر', sa.String(), nullable=True))
            print("[MIGRATION] Added نوع السعر column to shipments")
    
    # ======== NOTES TABLE ========
    if not table_exists(conn, 'notes'):
        op.create_table('notes',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('content', sa.Text(), nullable=True),
            sa.Column('audio_data', sa.LargeBinary(), nullable=True),
            sa.Column('audio_duration', sa.Float(), nullable=True),
            sa.Column('note_type', sa.String(), default='text'),
            sa.Column('color', sa.String(), default='yellow'),
            sa.Column('is_favorite', sa.Boolean(), default=False),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_notes_id', 'notes', ['id'])
        op.create_index('ix_notes_is_favorite', 'notes', ['is_favorite'])
        op.create_index('ix_notes_note_type', 'notes', ['note_type'])
        print("[MIGRATION] Created notes table")
    else:
        print("[MIGRATION] notes table already exists")
    
    # ======== CONTENT ITEMS TABLE ========
    if not table_exists(conn, 'content_items'):
        op.create_table('content_items',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('date', sa.String(), nullable=False),
            sa.Column('title', sa.String(), nullable=False),
            sa.Column('content_type', sa.String(), default='video'),
            sa.Column('platforms', sa.String(), default='[]'),
            sa.Column('status', sa.String(), default='To Shoot'),
            sa.Column('visual_idea', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_content_items_id', 'content_items', ['id'])
        op.create_index('ix_content_items_date', 'content_items', ['date'])
        print("[MIGRATION] Created content_items table")
    else:
        print("[MIGRATION] content_items table already exists")
    
    # ======== PAYMENT FILES TABLE ========
    if not table_exists(conn, 'payment_files'):
        op.create_table('payment_files',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('filename', sa.String(), nullable=True),
            sa.Column('upload_date', sa.DateTime(), nullable=True),
            sa.Column('record_count', sa.Integer(), default=0),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_payment_files_id', 'payment_files', ['id'])
        op.create_index('ix_payment_files_filename', 'payment_files', ['filename'])
        print("[MIGRATION] Created payment_files table")
    else:
        print("[MIGRATION] payment_files table already exists")
    
    # ======== PAYMENT RECORDS TABLE ========
    if not table_exists(conn, 'payment_records'):
        op.create_table('payment_records',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('file_id', sa.Integer(), nullable=True),
            # All 48 payment columns
            sa.Column('serial_number', sa.Integer(), nullable=True),
            sa.Column('order_code', sa.String(), nullable=True),
            sa.Column('order_date', sa.DateTime(), nullable=True),
            sa.Column('source', sa.String(), nullable=True),
            sa.Column('source_branch', sa.String(), nullable=True),
            sa.Column('client', sa.String(), nullable=True),
            sa.Column('client_branch', sa.String(), nullable=True),
            sa.Column('status', sa.String(), nullable=True),
            sa.Column('status_date', sa.DateTime(), nullable=True),
            sa.Column('recipient', sa.String(), nullable=True),
            sa.Column('recipient_phone', sa.String(), nullable=True),
            sa.Column('city', sa.String(), nullable=True),
            sa.Column('area', sa.String(), nullable=True),
            sa.Column('address', sa.Text(), nullable=True),
            sa.Column('delivery_type', sa.String(), nullable=True),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('order_value', sa.Float(), nullable=True),
            sa.Column('parcel_value', sa.Float(), nullable=True),
            sa.Column('cod_value', sa.Float(), nullable=True),
            sa.Column('shipping_fee', sa.Float(), nullable=True),
            sa.Column('collection_fee', sa.Float(), nullable=True),
            sa.Column('return_fee', sa.Float(), nullable=True),
            sa.Column('insurance_fee', sa.Float(), nullable=True),
            sa.Column('packaging_fee', sa.Float(), nullable=True),
            sa.Column('additional_fee', sa.Float(), nullable=True),
            sa.Column('village_fee', sa.Float(), nullable=True),
            sa.Column('storage_fee', sa.Float(), nullable=True),
            sa.Column('weight_fee', sa.Float(), nullable=True),
            sa.Column('total_fees', sa.Float(), nullable=True),
            sa.Column('total_due', sa.Float(), nullable=True),
            sa.Column('client_due', sa.Float(), nullable=True),
            sa.Column('payment_type', sa.String(), nullable=True),
            sa.Column('is_deleted', sa.Boolean(), default=False),
            sa.Column('deleted_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['file_id'], ['payment_files.id']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_payment_records_id', 'payment_records', ['id'])
        op.create_index('ix_payment_records_order_code', 'payment_records', ['order_code'])
        op.create_index('ix_payment_records_is_deleted', 'payment_records', ['is_deleted'])
        print("[MIGRATION] Created payment_records table")
    else:
        print("[MIGRATION] payment_records table already exists")
        # Add missing columns if needed
        if not column_exists(conn, 'payment_records', 'is_deleted'):
            op.add_column('payment_records', sa.Column('is_deleted', sa.Boolean(), default=False))
            print("[MIGRATION] Added is_deleted column to payment_records")
        if not column_exists(conn, 'payment_records', 'deleted_at'):
            op.add_column('payment_records', sa.Column('deleted_at', sa.DateTime(), nullable=True))
            print("[MIGRATION] Added deleted_at column to payment_records")
    
    print("[MIGRATION] Baseline migration complete!")


def downgrade() -> None:
    """
    We don't support downgrading the baseline migration
    as it would destroy all data.
    """
    pass
