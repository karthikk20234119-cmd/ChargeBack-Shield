"""
Migration Task 5.4B — Creates contest_submissions and contest_submission_audits tables
"""

from sqlalchemy import text
from backend.app.database import engine


async def run_migration_5_4b():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE match_results ADD COLUMN processed_artifact_id VARCHAR(36);"))
        except Exception:
            pass  # Column already exists
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS contest_submissions (
                id VARCHAR(36) PRIMARY KEY,
                submission_attempt_id VARCHAR(36) NOT NULL UNIQUE,
                dispute_id VARCHAR(64) NOT NULL UNIQUE,
                contest_draft_id VARCHAR(36) NOT NULL,
                preflight_id VARCHAR(36) NOT NULL,
                input_fingerprint VARCHAR(64) NOT NULL,
                idempotency_key VARCHAR(64) NOT NULL UNIQUE,
                previous_state VARCHAR(32) NOT NULL DEFAULT 'PRECHECK_REQUIRED',
                state VARCHAR(32) NOT NULL DEFAULT 'SUBMISSION_AUTHORIZED',
                razorpay_reference VARCHAR(128),
                razorpay_status VARCHAR(64),
                http_status INTEGER,
                failure_category VARCHAR(32) NOT NULL DEFAULT 'NONE',
                failure_reason VARCHAR(512),
                submitted_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (dispute_id) REFERENCES disputes(id) ON DELETE CASCADE,
                FOREIGN KEY (contest_draft_id) REFERENCES contest_drafts(id) ON DELETE CASCADE,
                FOREIGN KEY (preflight_id) REFERENCES contest_submission_preflights(id) ON DELETE CASCADE
            );
        """))

        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contest_submissions_dispute_id ON contest_submissions(dispute_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contest_submissions_attempt_id ON contest_submissions(submission_attempt_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contest_submissions_idempotency ON contest_submissions(idempotency_key);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contest_submissions_state ON contest_submissions(state);"))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS contest_submission_audits (
                id VARCHAR(36) PRIMARY KEY,
                dispute_id VARCHAR(64) NOT NULL,
                contest_submission_id VARCHAR(36) NOT NULL,
                contest_draft_id VARCHAR(36) NOT NULL,
                preflight_id VARCHAR(36) NOT NULL,
                input_fingerprint VARCHAR(64) NOT NULL,
                previous_state VARCHAR(32) NOT NULL,
                new_state VARCHAR(32) NOT NULL,
                submission_status VARCHAR(32) NOT NULL,
                http_status_code INTEGER,
                razorpay_reference_id VARCHAR(128),
                error_code VARCHAR(64),
                sanitized_response_metadata JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (dispute_id) REFERENCES disputes(id) ON DELETE CASCADE,
                FOREIGN KEY (contest_submission_id) REFERENCES contest_submissions(id) ON DELETE CASCADE
            );
        """))

        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contest_sub_audits_dispute_id ON contest_submission_audits(dispute_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contest_sub_audits_sub_id ON contest_submission_audits(contest_submission_id);"))


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_migration_5_4b())
