"""
Backup Integrity Verification Script — Chargeback Shield Task 8.4

Verifies database file SHA-256 hash, SQLite PRAGMA integrity_check, evidence file counts,
and directory aggregate hashes against manifest.json.
Returns 0 on success, 1 on corruption/mismatch.
"""

import os
import sys
import json
import sqlite3
from backup_production import compute_file_sha256, compute_directory_sha256

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
BACKUPS_DIR = os.path.join(ROOT_DIR, "backups")


def verify_backup_folder(backup_dir: str) -> bool:
    """Verifies a backup folder against its manifest.json."""
    if not os.path.exists(backup_dir):
        print(f"[VERIFY ERROR]: Backup directory '{backup_dir}' does not exist.", file=sys.stderr)
        return False

    manifest_path = os.path.join(backup_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"[VERIFY ERROR]: manifest.json missing in '{backup_dir}'.", file=sys.stderr)
        return False

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # 1. Verify Database File Hash & SQLite Integrity
    db_backup_path = os.path.join(backup_dir, manifest["database"]["file"])
    if os.path.exists(db_backup_path):
        actual_db_hash = compute_file_sha256(db_backup_path)
        expected_db_hash = manifest["database"]["sha256"]
        if actual_db_hash != expected_db_hash:
            print(f"[VERIFY CORRUPTION]: Database SHA-256 mismatch! Expected: {expected_db_hash}, Got: {actual_db_hash}", file=sys.stderr)
            return False

        # SQLite integrity check
        conn = sqlite3.connect(db_backup_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()
        conn.close()
        if not res or res[0] != "ok":
            print(f"[VERIFY CORRUPTION]: Database PRAGMA integrity_check failed! Status: {res}", file=sys.stderr)
            return False

    # 2. Verify Evidence Storage
    evidence_backup_dir = os.path.join(backup_dir, manifest["evidence"]["directory"])
    if os.path.exists(evidence_backup_dir):
        actual_cnt, actual_hash = compute_directory_sha256(evidence_backup_dir)
        if actual_cnt != manifest["evidence"]["file_count"] or actual_hash != manifest["evidence"]["sha256"]:
            print(f"[VERIFY CORRUPTION]: Evidence directory hash/count mismatch!", file=sys.stderr)
            return False

    # 3. Verify Processed Storage
    processed_backup_dir = os.path.join(backup_dir, manifest["processed_artifacts"]["directory"])
    if os.path.exists(processed_backup_dir):
        actual_cnt, actual_hash = compute_directory_sha256(processed_backup_dir)
        if actual_cnt != manifest["processed_artifacts"]["file_count"] or actual_hash != manifest["processed_artifacts"]["sha256"]:
            print(f"[VERIFY CORRUPTION]: Processed directory hash/count mismatch!", file=sys.stderr)
            return False

    print(f"[VERIFY SUCCESS]: Backup at '{backup_dir}' verified clean & uncorrupted.")
    return True


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target is None:
        # Find latest backup in backups/
        if os.path.exists(BACKUPS_DIR):
            subdirs = [os.path.join(BACKUPS_DIR, d) for d in os.listdir(BACKUPS_DIR) if os.path.isdir(os.path.join(BACKUPS_DIR, d))]
            if subdirs:
                target = sorted(subdirs)[-1]

    if not target:
        print("[VERIFY ERROR]: No backup directory specified or found.", file=sys.stderr)
        sys.exit(1)

    ok = verify_backup_folder(target)
    sys.exit(0 if ok else 1)
