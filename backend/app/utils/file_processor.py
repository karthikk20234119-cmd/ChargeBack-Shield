import os
import uuid
import hashlib
from typing import Tuple

MAGIC_HEADERS = {
    "pdf": [b"%PDF-"],
    "jpg": [b"\xff\xd8\xff"],
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"]
}

ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png"}

MIME_TYPE_MAP = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png"
}

def sanitize_filename(filename: str) -> str:
    """
    Strips directory traversal paths and returns only the basename.
    """
    if not filename:
        return ""
    # Strip both Windows and Unix path separators
    clean_name = os.path.basename(filename.replace("\\", "/"))
    return clean_name

def validate_extension_and_mime(filename: str, content_type: str) -> Tuple[str, str]:
    """
    Validates file extension and normalizes extension and MIME type.
    
    :return: Tuple of (normalized_extension, mime_type)
    """
    clean_name = sanitize_filename(filename)
    if not clean_name or "." not in clean_name:
        raise ValueError("File missing valid extension")

    ext = clean_name.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension '.{ext}'. Supported: PDF, JPEG, JPG, PNG")

    expected_mime = MIME_TYPE_MAP.get(ext)
    return ext, expected_mime

def validate_magic_bytes(file_bytes: bytes, extension: str) -> bool:
    """
    Validates file content magic bytes against claimed extension.
    Prevents file extension spoofing (e.g. malicious.exe renamed to document.pdf).
    """
    if not file_bytes:
        return False

    valid_headers = MAGIC_HEADERS.get(extension.lower(), [])
    for header in valid_headers:
        if file_bytes.startswith(header):
            return True
    return False

def calculate_sha256(file_bytes: bytes) -> str:
    """
    Calculates SHA-256 hash of file content.
    """
    return hashlib.sha256(file_bytes).hexdigest()

def generate_internal_filename(extension: str) -> str:
    """
    Generates a secure UUID-based internal filename.
    """
    return f"{uuid.uuid4().hex}.{extension.lower()}"
