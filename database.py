import os
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, ForeignKey, Text, text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get the Database URL from env
DATABASE_URL = os.getenv("DATABASE_URL")

# Render/SQLAlchemy fix for postgres:// vs postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Validate database configuration on startup
if not DATABASE_URL:
    raise RuntimeError(
        "❌ DATABASE_URL is not set! "
        "Please create a .env file with DATABASE_URL=your_connection_string"
    )

# Create the engine and session
# engine = create_engine(DATABASE_URL)
# # Test the connection immediately
# try:
#     with engine.connect() as conn:
#         conn.execute(text("SELECT 1"))
#     print("✅ Database connection established successfully!")
# except Exception as e:
#     raise RuntimeError(f"❌ Failed to connect to database: {str(e)}")

engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    
    # Relationship to shipments
    shipments = relationship("Shipment", back_populates="source_file", cascade="all, delete-orphan")

class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"))
    
    # Core Fields (Mapped to Arabic DB Columns)
    # syntax: Column("DB_COLUMN_NAME", Type, ...)
    shipment_code = Column("الكود", String, index=True)
    date = Column("التاريخ", DateTime)
    client_name = Column("العميل", String, index=True)
    branch_name = Column("الفرع", String)
    status = Column("الحالة", String, index=True)
    
    # Sender Info
    sender_name = Column("اسم الراسل", String)
    sender_city = Column("مدينة الراسل", String)
    
    # Recipient Info
    recipient_name = Column("المستلم", String)
    recipient_city = Column("مدينة المستلم", String)
    recipient_area = Column("منطقة المستلم", String)
    recipient_address = Column("عنوان المستلم", Text)
    recipient_phone = Column("هاتف المستلم", String)
    recipient_mobile = Column("موبايل المستلم", String)
    
    # Financials
    amount = Column("قيمة الطرد", Float)
    shipping_fee = Column("الرسوم", Float)
    net_price = Column("صافي سعر الطرد", Float)
    total_value = Column("القيمة الإجمالية", Float)
    price_type = Column("نوع السعر", String)
    
    # Logistics
    weight = Column("الوزن", Float)
    pieces_count = Column("عدد القطع", Integer)
    description = Column("الوصف", Text)
    notes = Column("ملاحظات", Text)
    
    # Relationship
    source_file = relationship("UploadedFile", back_populates="shipments")


class PaymentFile(Base):
    """Tracks uploaded payment Excel files"""
    __tablename__ = "payment_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    upload_date = Column(DateTime, default=datetime.utcnow)
    record_count = Column(Integer, default=0)
    
    # Relationship to payment records
    records = relationship("PaymentRecord", back_populates="source_file", cascade="all, delete-orphan")


class PaymentRecord(Base):
    """Stores parsed payment data from Excel files - ALL 48 columns"""
    __tablename__ = "payment_records"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("payment_files.id"), index=True)
    
    # Core Fields
    amount_due = Column("المستحق", Float)
    code = Column("الكود", String, index=True)
    date = Column("التاريخ", DateTime)
    status = Column("الحالة", String, index=True)
    branch = Column("الفرع", String)
    origin_branch = Column("فرع المنشأ", String)
    service = Column("الخدمة", String)
    
    # Sender Info
    sender_name = Column("اسم الراسل", String)
    sender_city = Column("مدينة الراسل", String)
    sender_area = Column("منطقة الراسل", String)
    sender_postal_code = Column("الرمز البريدي للراسل", String)
    
    # Reference
    reference_number = Column("الرقم المرجعي", String, index=True)
    
    # Recipient Info
    recipient_name = Column("المستلم", String)
    recipient_city = Column("مدينة المستلم", String)
    recipient_area = Column("منطقة المستلم", String)
    recipient_address = Column("عنوان المستلم", Text)
    recipient_postal_code = Column("الرمز البريدي للمستلم", String)
    recipient_phone = Column("هاتف المستلم", String)
    recipient_mobile = Column("موبايل المستلم", String)
    
    # Package Info
    description = Column("الوصف", Text)
    weight = Column("الوزن", Float)
    pieces_count = Column("عدد القطع", Integer)
    
    # Financial Info
    package_value = Column("قيمة الطرد", Float)
    fees = Column("الرسوم", Float)
    net_package_price = Column("صافي سعر الطرد", Float)
    total_value = Column("القيمة الإجمالية", Float)
    delivery_value = Column("قيمة التسليم", Float)
    collected_fees = Column("الرسوم المحصلة", Float)
    due_fees = Column("الرسوم المستحقة", Float)
    
    # Type Info
    payment_type = Column("نوع الدفع", String)
    price_type = Column("نوع السعر", String)
    delivery_type = Column("نوع التسليم", String)
    return_type = Column("نوع المرتجع للراسل", String)
    
    # Agent
    shipping_agent = Column("مندوب الشحن", String)
    
    # === NEW COLUMNS (14 additional) ===
    is_collected = Column("تم التحصيل", String)
    paid_to_client = Column("تم السداد للعميل", String)
    notes = Column("ملاحظات", Text)
    can_open_package = Column("امكانية فتح الطرد", String)
    client_name = Column("العميل", String)
    return_reason = Column("سبب الإرجاع", String)
    order_type = Column("نوع الطلب", String)
    delivery_cancel_date = Column("تاريخ التسليم/الإلغاء", DateTime)
    return_value = Column("قيمة المرتجع", Float)
    attempts_count = Column("عدد المحاولات", Integer)
    delivery_date = Column("تاريخ التوصيل", DateTime)
    is_cancelled = Column("تم الإلغاء", String)
    last_movement_date = Column("تاريخ أخر حركة", DateTime)
    client_dues_payment = Column("سداد مستحقات العملاء", String)
    
    # Relationship
    source_file = relationship("PaymentFile", back_populates="records")


def create_tables():
    if engine is None:
        print("ERROR: DATABASE_URL is missing in .env file!")
        return
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully!")
