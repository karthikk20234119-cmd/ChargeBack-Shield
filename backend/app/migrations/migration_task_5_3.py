"""
Database Migration: Task 5.3 Contest Submission Preflight Schema

Creates contest_submission_preflights table for storing immutable local preflight verification records.
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def apply_task_5_3_migration(db: AsyncSession) -> None:
    """Applies schema migration for Task 5.3 by creating contest_submission_preflights table if needed."""
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS contest_submission_preflights (
        id VARCHAR(36) PRIMARY KEY,
        dispute_id VARCHAR(64) NOT NULL,
        contest_draft_id VARCHAR(36) NOT NULL,
        policy_result_id VARCHAR(36),
        status VARCHAR(32) NOT NULL,
        draft_status VARCHAR(32) NOT NULL,
        review_status VARCHAR(32) NOT NULL,
        input_fingerprint VARCHAR(64),
        draft_version VARCHAR(32) DEFAULT '1.0',
        generator_version VARCHAR(64) DEFAULT 'contest-draft-v1.0.0',
        checks JSON,
        blocking_reasons JSON,
        warnings JSON,
        verified_financial_identity JSON,
        verified_evidence_count INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (dispute_id) REFERENCES disputes (id) ON DELETE CASCADE,
        FOREIGN KEY (contest_draft_id) REFERENCES contest_drafts (id) ON DELETE CASCADE,
        FOREIGN KEY (policy_result_id) REFERENCES policy_results (id) ON DELETE SET NULL
    );
    """
    try:
        await db.execute(text(create_table_sql))
        await db.execute(text("CREATE INDEX IF NOT EXISTS ix_contest_sub_preflight_dispute_id ON contest_submission_preflights (dispute_id);"))
        await db.execute(text("CREATE INDEX IF NOT EXISTS ix_contest_sub_preflight_draft_id ON contest_submission_preflights (contest_draft_id);"))
        await db.execute(text("CREATE INDEX IF NOT EXISTS ix_contest_sub_preflight_status ON contest_submission_preflights (status);"))
        await db.commit()
        logger.info("Successfully ensured contest_submission_preflights table exists.")
    except Exception as ex:
        await db.rollback()
        logger.warning(f"Failed to apply contest_submission_preflights migration: {ex}")
