from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from database import Shipment, UploadedFile


def _to_mojibake(text: str) -> str:
    """Convert UTF-8 text to latin1-mojibake if needed."""
    if text is None:
        return ""
    try:
        return str(text).encode("utf-8").decode("latin1")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return str(text)


def _normalize_header(value) -> str:
    """Normalize spacing and surrounding whitespace for resilient key matching."""
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def _build_row_lookup(row: dict) -> dict:
    """
    Build lookup keys for both normal and mojibake headers.
    This lets one importer accept files with either encoding style.
    """
    lookup = {}
    for raw_key, val in row.items():
        normalized = _normalize_header(raw_key)
        if not normalized:
            continue

        lookup[normalized] = val
        lookup[_to_mojibake(normalized)] = val
    return lookup


def _row_get(lookup: dict, key: str):
    normalized = _normalize_header(key)
    if normalized in lookup:
        return lookup[normalized]

    return lookup.get(_to_mojibake(normalized))


def save_upload(db: Session, filename: str, data: list, file_path: str = None):
    """
    Saves upload record and shipments to database.
    Uses transaction to ensure all-or-nothing insertion.
    Skips duplicate shipments based on shipment_code.
    """
    db_file = UploadedFile(filename=filename)
    db.add(db_file)
    db.flush()

    shipments_to_insert = []
    skipped_duplicates = 0

    keys = {
        "code": "\u0627\u0644\u0643\u0648\u062f",
        "date": "\u0627\u0644\u062a\u0627\u0631\u064a\u062e",
        "client_name": "\u0627\u0644\u0639\u0645\u064a\u0644",
        "branch_name": "\u0627\u0644\u0641\u0631\u0639",
        "status": "\u0627\u0644\u062d\u0627\u0644\u0629",
        "sender_name": "\u0627\u0633\u0645 \u0627\u0644\u0631\u0627\u0633\u0644",
        "sender_city": "\u0645\u062f\u064a\u0646\u0629 \u0627\u0644\u0631\u0627\u0633\u0644",
        "recipient_name": "\u0627\u0644\u0645\u0633\u062a\u0644\u0645",
        "recipient_city": "\u0645\u062f\u064a\u0646\u0629 \u0627\u0644\u0645\u0633\u062a\u0644\u0645",
        "recipient_area": "\u0645\u0646\u0637\u0642\u0629 \u0627\u0644\u0645\u0633\u062a\u0644\u0645",
        "recipient_address": "\u0639\u0646\u0648\u0627\u0646 \u0627\u0644\u0645\u0633\u062a\u0644\u0645",
        "recipient_phone": "\u0647\u0627\u062a\u0641 \u0627\u0644\u0645\u0633\u062a\u0644\u0645",
        "recipient_mobile": "\u0645\u0648\u0628\u0627\u064a\u0644 \u0627\u0644\u0645\u0633\u062a\u0644\u0645",
        "amount": "\u0642\u064a\u0645\u0629 \u0627\u0644\u0637\u0631\u062f",
        "shipping_fee": "\u0627\u0644\u0631\u0633\u0648\u0645",
        "net_price": "\u0635\u0627\u0641\u064a \u0633\u0639\u0631 \u0627\u0644\u0637\u0631\u062f",
        "total_value": "\u0627\u0644\u0642\u064a\u0645\u0629 \u0627\u0644\u0625\u062c\u0645\u0627\u0644\u064a\u0629",
        "price_type": "\u0646\u0648\u0639 \u0627\u0644\u0633\u0639\u0631",
        "weight": "\u0627\u0644\u0648\u0632\u0646",
        "pieces_count": "\u0639\u062f\u062f \u0627\u0644\u0642\u0637\u0639",
        "description": "\u0627\u0644\u0648\u0635\u0641",
        "notes": "\u0645\u0644\u0627\u062d\u0638\u0627\u062a",
    }

    existing_codes = {
        str(code[0]).strip()
        for code in db.query(Shipment.shipment_code).all()
        if code[0]
    }

    for row in data:
        row_lookup = _build_row_lookup(row)

        row_status = _row_get(row_lookup, keys["status"])

        shipment_code = clean_str(_row_get(row_lookup, keys["code"]))
        shipment_code = shipment_code.strip() if shipment_code else None
        if not shipment_code:
            continue

        if shipment_code in existing_codes:
            skipped_duplicates += 1
            continue
        existing_codes.add(shipment_code)

        shipment = Shipment(
            file_id=db_file.id,
            shipment_code=shipment_code,
            date=parse_date(_row_get(row_lookup, keys["date"])),
            client_name=_row_get(row_lookup, keys["client_name"]),
            branch_name=_row_get(row_lookup, keys["branch_name"]),
            status=row_status,
            sender_name=_row_get(row_lookup, keys["sender_name"]),
            sender_city=_row_get(row_lookup, keys["sender_city"]),
            recipient_name=_row_get(row_lookup, keys["recipient_name"]),
            recipient_city=_row_get(row_lookup, keys["recipient_city"]),
            recipient_area=_row_get(row_lookup, keys["recipient_area"]),
            recipient_address=_row_get(row_lookup, keys["recipient_address"]),
            recipient_phone=clean_str(_row_get(row_lookup, keys["recipient_phone"])),
            recipient_mobile=clean_str(_row_get(row_lookup, keys["recipient_mobile"])),
            amount=clean_float(_row_get(row_lookup, keys["amount"])),
            shipping_fee=clean_float(_row_get(row_lookup, keys["shipping_fee"])),
            net_price=clean_float(_row_get(row_lookup, keys["net_price"])),
            total_value=clean_float(_row_get(row_lookup, keys["total_value"])),
            price_type=_row_get(row_lookup, keys["price_type"]),
            weight=clean_float(_row_get(row_lookup, keys["weight"])),
            pieces_count=clean_int(_row_get(row_lookup, keys["pieces_count"])),
            description=_row_get(row_lookup, keys["description"]),
            notes=_row_get(row_lookup, keys["notes"]),
        )
        shipments_to_insert.append(shipment)

    if len(shipments_to_insert) == 0:
        db.rollback()
        raise Exception(
            "No valid shipments to upload. "
            f"Skipped duplicates: {skipped_duplicates}, "
            "and no rows with a valid shipment code remained."
        )

    try:
        db.add_all(shipments_to_insert)
        db.commit()
    except Exception as e:
        db.rollback()
        raise Exception(f"Database error: {str(e)}. All changes rolled back.")

    return {
        "file_id": db_file.id,
        "inserted": len(shipments_to_insert),
        "skipped_duplicates": skipped_duplicates,
    }


def parse_date(date_val):
    """
    Robustly parse date from various formats.
    Handles pandas Timestamp, datetime, excel serial dates, and string dates.
    """
    if date_val is None:
        return None

    if isinstance(date_val, datetime):
        return date_val

    if isinstance(date_val, pd.Timestamp):
        return date_val.to_pydatetime()

    if isinstance(date_val, (int, float)):
        # Excel serial date fallback
        try:
            return pd.to_datetime(date_val, unit="D", origin="1899-12-30").to_pydatetime()
        except Exception:
            return None

    if isinstance(date_val, str):
        date_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
        ]
        for fmt in date_formats:
            try:
                return datetime.strptime(date_val, fmt)
            except ValueError:
                continue
        return None

    return None


def clean_float(val):
    if val is None:
        return 0.0
    try:
        if isinstance(val, str):
            val = val.replace(",", "").strip()
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def clean_int(val):
    if val is None:
        return 0
    try:
        if isinstance(val, str):
            val = val.replace(",", "").strip()
        return int(float(val))
    except (ValueError, TypeError):
        return 0


def clean_str(val):
    if val is None:
        return None
    return str(val)
