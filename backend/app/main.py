import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.database import init_db
from backend.app.api.disputes import router as disputes_router
from backend.app.api.webhooks import router as webhooks_router
from backend.app.api.evidence import router as evidence_router
from backend.app.api.matching import router as matching_router
from backend.app.api.policy import router as policy_router
from backend.app.api.razorpay_disputes import router as razorpay_disputes_router
from backend.app.api.dispute_sync import router as dispute_sync_router
from backend.app.api.contest_draft import router as contest_draft_router
from backend.app.api.contest_submission_preflight import router as contest_submission_preflight_router
from backend.app.api.contest_submission import contest_submission_router
from backend.app.api.contest_submission_reconciliation import contest_submission_reconciliation_router
from backend.app.api.dispute_lifecycle_sync import dispute_lifecycle_sync_router
from backend.app.api.dashboard import dashboard_router
from backend.app.api.audit_reporting import audit_reporting_router
from backend.app.api.operational_alerts import operational_alerts_router
from backend.app.api.analytics import analytics_router

logger = logging.getLogger("chargeback_shield")
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Chargeback Shield Database schema...")
    await init_db()
    logger.info("Chargeback Shield Backend application startup complete.")
    yield
    logger.info("Chargeback Shield Backend application shutdown.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Chargeback Shield — AI-powered chargeback evidence intelligence and safe representment system",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers
app.include_router(disputes_router)
app.include_router(webhooks_router)
app.include_router(evidence_router)
app.include_router(matching_router)
app.include_router(policy_router)
app.include_router(razorpay_disputes_router)
app.include_router(dispute_sync_router)
app.include_router(contest_draft_router)
app.include_router(contest_submission_preflight_router)
app.include_router(contest_submission_router)
app.include_router(contest_submission_reconciliation_router)
app.include_router(dispute_lifecycle_sync_router)
app.include_router(dashboard_router)
app.include_router(audit_reporting_router)
app.include_router(operational_alerts_router)
app.include_router(analytics_router)

@app.get("/")
async def root():
    return {
        "app": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "status": "operational"
    }

@app.get("/api/health")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Chargeback Shield API",
        "environment": settings.ENVIRONMENT
    }
