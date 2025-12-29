"""
Centralized constants for shipment statuses.
Single source of truth for status values used across the application.
"""

# Statuses from which orders CAN be changed (source statuses)
CHANGEABLE_STATUSES = [
    "طلب الشحن",
    "طلب شحن",
    "تم الاستلام بالمخزن"
]

# Statuses that orders can be changed TO (target statuses)
TARGET_STATUSES = [
    "تم التسليم",
    "مرتجع"
]

# All possible statuses in the system
ALL_STATUSES = CHANGEABLE_STATUSES + TARGET_STATUSES + [
    "ملغى",
    "قيد التوصيل"
]

# Status display colors (for frontend reference)
STATUS_COLORS = {
    "تم التسليم": "success",
    "تم الاستلام بالمخزن": "info",
    "طلب الشحن": "pending",
    "طلب شحن": "pending",
    "مرتجع": "warning",
    "ملغى": "error",
    "قيد التوصيل": "info"
}
