"""
Structured Logging & Secret Redaction Policy — Chargeback Shield Task 8.1
"""

import re
import logging
from typing import Any, Dict

# Regex patterns for secret redaction
SECRET_PATTERNS = [
    (re.compile(r"rzp_live_[a-zA-Z0-9]+"), "[REDACTED_RAZORPAY_KEY]"),
    (re.compile(r"rzp_test_[a-zA-Z0-9]+"), "[REDACTED_RAZORPAY_KEY]"),
    (re.compile(r"gsk_[a-zA-Z0-9_\-]+"), "[REDACTED_GROQ_KEY]"),
    (re.compile(r"sk-proj-[a-zA-Z0-9_\-]+"), "[REDACTED_OPENAI_KEY]"),
    (re.compile(r"(?i)bearer\s+[a-zA-Z0-9\._\-]+"), "Bearer [REDACTED_TOKEN]"),
    (re.compile(r"(?i)password\s*=\s*['\"]?[^\s'\"]+['\"]?"), "password=[REDACTED]"),
]


def redact_secrets(text: str) -> str:
    """Sanitizes text strings, stripping raw API keys, passwords, and tokens."""
    if not isinstance(text, str):
        return text
    sanitized = text
    for pattern, replacement in SECRET_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


class SecretSanitizingFormatter(logging.Formatter):
    """Logging formatter that automatically redacts secrets from log records."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return redact_secrets(formatted)
