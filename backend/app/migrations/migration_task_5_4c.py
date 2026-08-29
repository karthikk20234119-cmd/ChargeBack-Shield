"""
Migration Task 5.4C — Adds reconciled_at and reconciliation_reason columns to contest_submissions
"""

from sqlalchemy import text
from backend.app.database import engine


async def run_migration_5_4c():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE contest_submissions ADD COLUMN reconciled_at TIMESTAMP;"))
        except Exception:
            pass  # Column already exists

        try:
            await conn.execute(text("ALTER TABLE contest_submissions ADD COLUMN reconciliation_reason VARCHAR(512);"))
        except Exception:
            pass  # Column already exists


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_migration_5_4c())
