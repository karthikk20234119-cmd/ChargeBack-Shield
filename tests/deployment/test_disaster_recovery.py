"""
Disaster Recovery & Backup/Restore Integration Suite — Chargeback Shield Task 8.4

Simulates full data loss and verifies atomic backup & restore with 100% financial,
audit, evidence, human review, and submission state preservation.
"""

import os
import sys
import shutil
import sqlite3
import pytest

# Ensure scripts directory is in path for backup/verify/restore modules
SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../scripts"))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from backup_production import create_backup, compute_file_sha256
from verify_backup import verify_backup_folder
from restore_production import restore_production_backup

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))


def test_disaster_recovery_workflow(tmp_path):
    """
    Full automated disaster recovery scenario:
    1. Seed test SQLite DB with dispute lifecycle record.
    2. Seed test evidence storage file.
    3. Create backup & manifest via backup_production.
    4. Record baseline financial fields, review state, submission state.
    5. Simulate disaster (remove DB & evidence).
    6. Execute restore via restore_production.
    7. Verify SQLite integrity & exact preservation of financial identity & states.
    """

    # Target test files isolated inside tmp_path
    test_db_path = str(tmp_path / "dr_test.db")
    test_evidence_dir = str(tmp_path / "storage" / "evidence")
    test_processed_dir = str(tmp_path / "storage" / "processed")
    test_evidence_file = os.path.join(test_evidence_dir, "dr_test_evidence.pdf")

    os.makedirs(test_evidence_dir, exist_ok=True)
    os.makedirs(test_processed_dir, exist_ok=True)

    # 1. Seed test evidence file
    sample_pdf_bytes = b"%PDF-1.4 sample evidence content for DR test"
    with open(test_evidence_file, "wb") as ef:
        ef.write(sample_pdf_bytes)
    original_pdf_hash = compute_file_sha256(test_evidence_file)

    # 2. Seed test SQLite database
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dr_dispute_test (
            dispute_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            amount INTEGER NOT NULL,
            currency TEXT NOT NULL,
            review_status TEXT NOT NULL,
            submission_status TEXT NOT NULL
        )
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO dr_dispute_test
        (dispute_id, payment_id, amount, currency, review_status, submission_status)
        VALUES ('disp_dr_1001', 'pay_dr_554433', 250000, 'INR', 'APPROVED', 'UNKNOWN')
    """)
    conn.commit()
    conn.close()

    # 3. Create Backup
    backup_target_dir = os.path.join(tmp_path, "dr_backup_2026")
    created_dir = create_backup(
        target_backup_dir=backup_target_dir,
        source_db_path=test_db_path,
        source_evidence_dir=test_evidence_dir,
        source_processed_dir=test_processed_dir
    )
    assert os.path.exists(created_dir)
    assert verify_backup_folder(created_dir) is True

    # 4. Simulate Disaster (Corrupt / Remove DB and Evidence)
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    if os.path.exists(test_evidence_file):
        os.remove(test_evidence_file)

    assert not os.path.exists(test_db_path)
    assert not os.path.exists(test_evidence_file)

    # 5. Execute Restore
    restore_ok = restore_production_backup(
        backup_dir=created_dir,
        target_db_path=test_db_path,
        target_evidence_dir=test_evidence_dir,
        target_processed_dir=test_processed_dir
    )
    assert restore_ok is True

    # 6. Verify SQLite PRAGMA Integrity & Financial Identity Preservation
    assert os.path.exists(test_db_path)
    conn_restored = sqlite3.connect(test_db_path)
    cur_restored = conn_restored.cursor()

    cur_restored.execute("PRAGMA integrity_check;")
    assert cur_restored.fetchone()[0] == "ok"

    cur_restored.execute("SELECT dispute_id, payment_id, amount, currency, review_status, submission_status FROM dr_dispute_test WHERE dispute_id='disp_dr_1001';")
    row = cur_restored.fetchone()
    conn_restored.close()

    assert row is not None
    dispute_id, payment_id, amount, currency, review_status, submission_status = row

    # Assert exact financial identity preservation
    assert dispute_id == "disp_dr_1001"
    assert payment_id == "pay_dr_554433"
    assert amount == 250000
    assert currency == "INR"

    # Assert exact human review and submission state preservation
    assert review_status == "APPROVED"
    assert submission_status == "UNKNOWN"

    # 7. Verify Evidence File Hash Preservation
    assert os.path.exists(test_evidence_file)
    restored_pdf_hash = compute_file_sha256(test_evidence_file)
    assert restored_pdf_hash == original_pdf_hash
