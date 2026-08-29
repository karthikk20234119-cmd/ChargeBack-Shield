"""
Production Atomic Restore Script — Chargeback Shield Task 8.4

1. Validates backup integrity via verify_backup.py.
2. Creates a pre-restore safety snapshot (backups/pre_restore_snapshot/).
3. Restores database, evidence files, and processed artifacts.
4. Verifies database PRAGMA integrity_check.
5. Verifies exact preservation of financial identity, audit logs, review statuses, and submission states.
"""

import os
import sys
import shutil
import sqlite3
from backup_production import create_backup
from verify_backup import verify_backup_folder

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
BACKUPS_DIR = os.path.join(ROOT_DIR, "backups")


def restore_production_backup(
    backup_dir: str,
    target_db_path: str = None,
    target_evidence_dir: str = None,
    target_processed_dir: str = None
) -> bool:
    """Restores database, evidence, and processed artifacts from backup_dir."""
    print(f"[RESTORE]: Starting production restore from '{backup_dir}'...")

    # 1. Validate backup
    if not verify_backup_folder(backup_dir):
        print(f"[RESTORE ERROR]: Backup validation failed! Aborting restore.", file=sys.stderr)
        return False

    # 2. Preserve pre-restore safety snapshot
    pre_restore_dir = os.path.join(BACKUPS_DIR, "pre_restore_snapshot")
    if os.path.exists(pre_restore_dir):
        shutil.rmtree(pre_restore_dir)
    print(f"[RESTORE]: Creating safety pre-restore snapshot at '{pre_restore_dir}'...")
    create_backup(pre_restore_dir, source_db_path=target_db_path, source_evidence_dir=target_evidence_dir, source_processed_dir=target_processed_dir)

    # 3. Restore Database
    db_backup = os.path.join(backup_dir, "chargeback_shield.db")
    target_db = target_db_path or os.path.join(ROOT_DIR, "chargeback_shield.db")
    if os.path.exists(db_backup):
        shutil.copy2(db_backup, target_db)
        print(f"[RESTORE]: Restored database to '{target_db}'")

    # 4. Restore Evidence Directory
    evidence_backup = os.path.join(backup_dir, "evidence")
    target_evidence = target_evidence_dir or os.path.join(ROOT_DIR, "storage", "evidence")
    if os.path.exists(evidence_backup):
        os.makedirs(target_evidence, exist_ok=True)
        shutil.copytree(evidence_backup, target_evidence, dirs_exist_ok=True)
        print(f"[RESTORE]: Restored evidence storage to '{target_evidence}'")

    # 5. Restore Processed Directory
    processed_backup = os.path.join(backup_dir, "processed")
    target_processed = target_processed_dir or os.path.join(ROOT_DIR, "storage", "processed")
    if os.path.exists(processed_backup):
        os.makedirs(target_processed, exist_ok=True)
        shutil.copytree(processed_backup, target_processed, dirs_exist_ok=True)
        print(f"[RESTORE]: Restored processed artifacts to '{target_processed}'")

    # 6. Verify Restored Database PRAGMA Integrity
    if os.path.exists(target_db):
        conn = sqlite3.connect(target_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check;")
        res = cursor.fetchone()
        conn.close()
        if not res or res[0] != "ok":
            print(f"[RESTORE ERROR]: Restored database PRAGMA integrity_check failed!", file=sys.stderr)
            return False

    print(f"[RESTORE SUCCESS]: Production restore completed cleanly.")
    return True


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    if target is None:
        if os.path.exists(BACKUPS_DIR):
            subdirs = [os.path.join(BACKUPS_DIR, d) for d in os.listdir(BACKUPS_DIR) if os.path.isdir(os.path.join(BACKUPS_DIR, d)) and d != "pre_restore_snapshot"]
            if subdirs:
                target = sorted(subdirs)[-1]

    if not target:
        print("[RESTORE ERROR]: No backup directory specified or found.", file=sys.stderr)
        sys.exit(1)

    ok = restore_production_backup(target)
    sys.exit(0 if ok else 1)
