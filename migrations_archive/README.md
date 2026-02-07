# Migration Archive

This folder contains old standalone migration scripts that have been 
consolidated into Alembic migrations.

These scripts are preserved for reference but should NOT be run directly.
All migrations are now managed through Alembic.

## Archived Scripts:
- `add_soft_delete_columns.py` - Added is_deleted/deleted_at to shipments & payment_records
- `add_price_type.py` - Added نوع السعر column to shipments
- `create_notes_table.py` - Created notes table for voice recordings
- `create_payment_tables.py` - Created payment_files and payment_records tables

## Using Alembic

To run migrations:
```bash
python run_migrations.py
```

To check current status:
```bash
python run_migrations.py current
```

To stamp existing database:
```bash
python run_migrations.py stamp
```
