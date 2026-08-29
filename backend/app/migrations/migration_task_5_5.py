"""
Migration Task 5.5 — Creates dispute_lifecycle_snapshots table
"""

from sqlalchemy import text
from backend.app.database import engine


async def run_migration_5_5():
    async with engine.begin() as conn:
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dispute_lifecycle_snapshots (
                id VARCHAR(36) PRIMARY KEY,
                dispute_id VARCHAR(64) NOT NULL,
                razorpay_dispute_id VARCHAR(64) NOT NULL,
                submission_id VARCHAR(36),
                previous_lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN',
                new_lifecycle_status VARCHAR(32) NOT NULL DEFAULT 'UNKNOWN',
                razorpay_status VARCHAR(64) NOT NULL,
                razorpay_phase VARCHAR(64),
                razorpay_reference VARCHAR(128),
                outcome VARCHAR(32) NOT NULL DEFAULT 'PENDING',
                sync_result VARCHAR(32) NOT NULL DEFAULT 'STATE_CHANGED',
                observed_at TIMESTAMP NOT NULL,
                input_fingerprint VARCHAR(64),
                created_at TIMESTAMP NOT NULL,
                FOREIGN KEY (dispute_id) REFERENCES disputes (id) ON DELETE CASCADE
            );
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dl_snapshots_dispute_id ON dispute_lifecycle_snapshots (dispute_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dl_snapshots_rzp_dispute_id ON dispute_lifecycle_snapshots (razorpay_dispute_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_dl_snapshots_submission_id ON dispute_lifecycle_snapshots (submission_id);"))


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_migration_5_5())
