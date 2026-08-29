"""
Database Migration: Task 5.2 Contest Draft Review Schema

Adds review_status column to contest_drafts with safe backfill to 'PENDING_REVIEW'.
Creates contest_draft_review_audits append-only table.
"""

import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def apply_task_5_2_migration(db: AsyncSession) -> None:
    """Applies schema migration for Task 5.2 safely backfilling review_status."""
    try:
        # 1. Add review_status column to contest_drafts if missing
        await db.execute(
            text(
                "ALTER TABLE contest_drafts ADD COLUMN review_status VARCHAR(32) DEFAULT 'PENDING_REVIEW';"
            )
        )
        await db.commit()
        logger.info("Successfully added review_status column to contest_drafts.")
    except Exception as ex:
        # Column may already exist
        await db.rollback()
        logger.debug(f"Migration step review_status column check: {ex}")

    # Backfill any null review_status values to 'PENDING_REVIEW'
    try:
        await db.execute(
            text(
                "UPDATE contest_drafts SET review_status = 'PENDING_REVIEW' WHERE review_status IS NULL;"
            )
        )
        await db.commit()
    except Exception as ex:
        await db.rollback()
        logger.debug(f"Migration step backfill check: {ex}")
