"""
Production Backup Generator — Chargeback Shield Task 8.4

Safely creates timestamped backup archives of SQLite DB, evidence files, and processed artifacts.
Generates a deterministic SHA-256 manifest.json while excluding secrets.
"""

import os
import shutil
import hashlib
import json
import sys
from datetime import datetime, timezone

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
BACKUPS_DIR = os.path.join(ROOT_DIR, "backups")


def compute_file_sha256(filepath: str) -> str:
    """Computes SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_directory_sha256(dirpath: str) -> tuple[int, str]:
    """Computes aggregate SHA-256 hash and count of files in a directory."""
    if not os.path.exists(dirpath):
        return 0, hashlib.sha256().hexdigest()

    file_count = 0
    sha256 = hashlib.sha256()

    for root, _, files in sorted(os.walk(dirpath)):
        for f in sorted(files):
            file_count += 1
            full_path = os.path.join(root, f)
            with open(full_path, "rb") as fp:
                while chunk := fp.read(65536):
                    sha256.update(chunk)

    return file_count, sha256.hexdigest()


def create_backup(
    target_backup_dir: str = None,
    source_db_path: str = None,
    source_evidence_dir: str = None,
    source_processed_dir: str = None
) -> str:
    """Creates a timestamped production backup directory with manifest.json."""
    timestamp_str = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    if target_backup_dir is None:
        target_backup_dir = os.path.join(BACKUPS_DIR, timestamp_str)

    os.makedirs(target_backup_dir, exist_ok=True)

    db_path = source_db_path or os.path.join(ROOT_DIR, "chargeback_shield.db")
    evidence_dir = source_evidence_dir or os.path.join(ROOT_DIR, "storage", "evidence")
    processed_dir = source_processed_dir or os.path.join(ROOT_DIR, "storage", "processed")

    # 1. Copy Database
    db_backup_path = os.path.join(target_backup_dir, "chargeback_shield.db")
    db_hash = "no_database_file"
    db_size = 0

    if os.path.exists(db_path):
        shutil.copy2(db_path, db_backup_path)
        db_hash = compute_file_sha256(db_backup_path)
        db_size = os.path.getsize(db_backup_path)

    # 2. Copy Evidence Storage
    evidence_backup_dir = os.path.join(target_backup_dir, "evidence")
    evidence_count = 0
    evidence_hash = ""
    if os.path.exists(evidence_dir):
        shutil.copytree(evidence_dir, evidence_backup_dir, dirs_exist_ok=True)
        evidence_count, evidence_hash = compute_directory_sha256(evidence_backup_dir)

    # 3. Copy Processed Artifact Storage
    processed_backup_dir = os.path.join(target_backup_dir, "processed")
    processed_count = 0
    processed_hash = ""
    if os.path.exists(processed_dir):
        shutil.copytree(processed_dir, processed_backup_dir, dirs_exist_ok=True)
        processed_count, processed_hash = compute_directory_sha256(processed_backup_dir)

    # 4. Generate Manifest (NO secrets, NO credentials)
    manifest = {
        "manifest_version": "1.0",
        "app_name": "Chargeback Shield",
        "app_version": "1.0.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "database": {
            "file": "chargeback_shield.db",
            "sha256": db_hash,
            "size_bytes": db_size,
        },
        "evidence": {
            "directory": "evidence",
            "file_count": evidence_count,
            "sha256": evidence_hash,
        },
        "processed_artifacts": {
            "directory": "processed",
            "file_count": processed_count,
            "sha256": processed_hash,
        },
        "security_policy": "NO_SECRETS_EXCLUDED_PER_TASK_8.4_SPEC",
    }

    manifest_path = os.path.join(target_backup_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"[BACKUP SUCCESS]: Created production backup at '{target_backup_dir}' (DB SHA-256: {db_hash[:16]}...)")
    return target_backup_dir


if __name__ == "__main__":
    create_backup()
