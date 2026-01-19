"""
Centralized constants for shipment statuses.
Single source of truth for status values used across the application.
"""

# ALL statuses can now be changed (no restrictions on source status)
CHANGEABLE_STATUSES = [
    "طلب الشحن",
    "طلب شحن",
    "تم الاستلام بالمخزن",
    "قيد التوصيل",
    "تم التسليم",
    "مرتجع",
    "تسليم جزئي",
    "ملغى",
    "تم الارجاع للراسل"
]

# Statuses that orders can be changed TO (target statuses)
TARGET_STATUSES = [
    "تم التسليم",
    "مرتجع",
    "تسليم جزئي",
    "قيد التوصيل"
]

# All possible statuses in the system
ALL_STATUSES = list(set(CHANGEABLE_STATUSES + TARGET_STATUSES))

# Status display colors (for frontend reference)
STATUS_COLORS = {
    "تم التسليم": "success",
    "تم الاستلام بالمخزن": "info",
    "طلب الشحن": "pending",
    "طلب شحن": "pending",
    "مرتجع": "error",
    "ملغى": "error",
    "قيد التوصيل": "info",
    "تسليم جزئي": "warning",
    "تم الارجاع للراسل": "warning"
}
