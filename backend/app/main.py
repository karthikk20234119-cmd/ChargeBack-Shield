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
from backend.app.api.observability import router as observability_router

from backend.app.core.errors import setup_error_handlers
from backend.app.core.middleware import RequestCorrelationMiddleware
from backend.app.core.startup import validate_production_startup
from backend.app.core.observability import check_database_health, check_storage_health

logger = logging.getLogger("chargeback_shield")
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_startup()
    logger.info("Initializing Chargeback Shield Database schema...")
    await init_db()
    logger.info("Chargeback Shield Backend application startup complete.")
    yield
    logger.info("Chargeback Shield Backend application shutdown.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="1.0.0",
    description="Chargeback Shield — AI-powered chargeback evidence intelligence and safe representment system",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_OPENAPI else None,
)

# Register Request Correlation & Security Headers Middleware
app.add_middleware(RequestCorrelationMiddleware)

# Register Hardened CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup Centralized Production Exception Handlers
setup_error_handlers(app)

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
app.include_router(observability_router)

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

@app.get("/api/health/live")
async def health_live():
    return {
        "status": "ok",
        "service": "Chargeback Shield API",
        "environment": settings.ENVIRONMENT
    }

@app.get("/api/health/ready")
async def health_ready():
    db_health = await check_database_health()
    storage_health = check_storage_health()
    is_ready = db_health["status"] == "HEALTHY" and storage_health["status"] == "HEALTHY"

    return {
        "status": "ready" if is_ready else "degraded",
        "service": "Chargeback Shield API",
        "environment": settings.ENVIRONMENT,
        "database": db_health["status"],
        "storage": storage_health["status"]
    }
