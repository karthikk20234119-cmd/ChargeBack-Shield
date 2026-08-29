"""
Deterministic Normalization Utilities — Phase 4 Task 4.1

Provides deterministic parsing and normalization functions for evidence facts:
- Amounts (minor units / paise integer)
- Dates (ISO 8601 YYYY-MM-DD string)
- Email addresses (lowercase, stripped)
- Phone numbers (stripped, formatting-normalized)
- Tracking numbers (trimmed, uppercase)
- Confidence levels (HIGH, MEDIUM, LOW)
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional


def normalize_amount(val: Any) -> Optional[int]:
    """
    Normalizes currency amount strings/numbers to integer minor units (paise/cents).

    Examples:
        "₹1,499.00" -> 149900
        "1499" -> 149900
        "1,499.50 INR" -> 149950
        149900 -> 149900
    """
    if val is None:
        return None

    if isinstance(val, int):
        # If already integer and looks like minor units (> 1000 for standard amounts)
        return val

    if isinstance(val, float):
        return int(round(val * 100))

    val_str = str(val).strip()
    if not val_str:
        return None

    # Remove currency symbols (₹, $, €, £, INR, USD, etc.) and spaces
    cleaned = re.sub(r"[^\d.,]", "", val_str)

    if not cleaned:
        return None

    # Handle Indian/Western number formatting (e.g. 1,499.00 or 1499.00)
    # If contains comma and dot, assume dot is decimal separator
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(",", "")
    elif "," in cleaned and "." not in cleaned:
        # Check if comma is decimal separator (e.g. European format 1499,50)
        parts = cleaned.split(",")
        if len(parts[-1]) == 2:
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")

    try:
        float_val = float(cleaned)
        return int(round(float_val * 100))
    except ValueError:
        return None


def normalize_date(val: Any) -> Optional[str]:
    """
    Normalizes date strings into ISO format (YYYY-MM-DD).

    Examples:
        "15 Aug 2026" -> "2026-08-15"
        "2026-08-15" -> "2026-08-15"
        "15/08/2026" -> "2026-08-15"
        "08/15/2026" -> "2026-08-15"
    """
    if not val:
        return None

    val_str = str(val).strip()
    if not val_str:
        return None

    # Supported date formats
    date_formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y/%m/%d",
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y.%m.%d",
        "%d.%m.%Y",
    ]

    for fmt in date_formats:
        try:
            dt = datetime.strptime(val_str, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # ISO format match using regex YYYY-MM-DD
    match = re.search(r"(\d{4})[-/.](0[1-9]|1[0-2])[-/.](0[1-9]|[12]\d|3[01])", val_str)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

    return None


def normalize_email(val: Any) -> Optional[str]:
    """
    Normalizes email addresses to lowercased, whitespace-stripped format.
    """
    if not val:
        return None

    email_str = str(val).strip().lower()
    if not email_str:
        return None

    # Basic regex validation
    if re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email_str):
        return email_str

    return None


def normalize_phone(val: Any) -> Optional[str]:
    """
    Normalizes phone numbers by stripping formatting characters without inventing digits.
    """
    if not val:
        return None

    phone_str = str(val).strip()
    if not phone_str:
        return None

    has_plus = phone_str.startswith("+")
    digits_only = re.sub(r"[^\d]", "", phone_str)

    if not digits_only:
        return None

    return f"+{digits_only}" if has_plus else digits_only


def normalize_tracking_id(val: Any) -> Optional[str]:
    """
    Normalizes shipment tracking IDs by trimming whitespace and capitalizing letters.
    """
    if not val:
        return None

    tracking_str = str(val).strip().upper()
    if not tracking_str:
        return None

    # Remove internal spaces or control chars
    sanitized = re.sub(r"[\s\x00-\x1f]", "", tracking_str)
    return sanitized if sanitized else None


def normalize_confidence(val: Any) -> str:
    """
    Normalizes confidence scores or strings into standardized 'HIGH', 'MEDIUM', or 'LOW'.

    Examples:
        0.95 -> "HIGH"
        0.75 -> "MEDIUM"
        0.40 -> "LOW"
        "high" -> "HIGH"
        "probably correct" -> "MEDIUM"
        "uncertain" -> "LOW"
    """
    if val is None:
        return "MEDIUM"

    if isinstance(val, (int, float)):
        if val >= 0.85:
            return "HIGH"
        elif val >= 0.60:
            return "MEDIUM"
        else:
            return "LOW"

    val_str = str(val).strip().upper()

    if any(k in val_str for k in ("LOW", "UNCERTAIN", "WEAK", "POOR", "DOUBTFUL")):
        return "LOW"
    elif any(k in val_str for k in ("HIGH", "CERTAIN", "CONFIDENT", "STRONG", "EXACT")):
        return "HIGH"

    return "MEDIUM"
