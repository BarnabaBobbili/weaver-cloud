from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.config import settings
from app.security.headers import SecurityHeadersMiddleware
from app.security.session_timeout import SessionTimeoutMiddleware
from app.security.rate_limiter import limiter

logger = logging.getLogger(__name__)
from app.routers import (
    admin,
    analytics,
    auth,
    benchmarks,
    classify,
    decrypt,
    encrypt,
    guest,
    notifications,
    policies,
    profile,
    share,
)


# ─── Startup/Shutdown Events ──────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Initialize Azure services
    try:
        # Initialize telemetry service
        from app.services.telemetry_service import get_telemetry_service
        telemetry = get_telemetry_service()
        logger.info("Application Insights telemetry initialized")
        
        # Warm up ML model cache (download from Azure ML if needed)
        try:
            from app.services.ml_service import get_ml_service
            ml_service = get_ml_service()
            logger.info("Azure ML service initialized")
        except Exception as e:
            logger.warning(f"Azure ML service not available: {e}")
        
        # Test Key Vault connectivity
        try:
            from app.services.keyvault_service import get_keyvault_service
            kv = get_keyvault_service()
            logger.info("Key Vault connectivity verified")
        except Exception as e:
            logger.error(f"Key Vault initialization failed: {e}")
            raise
        
        # Test database connectivity
        try:
            from app.database import get_db
            async for db in get_db():
                await db.execute(text("SELECT 1"))
                logger.info("Database connectivity verified")
                break
        except Exception as e:
            logger.error(f"Database connectivity failed: {e}")
            raise
        
        logger.info("All Azure services initialized successfully")
        
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    try:
        from app.services.servicebus_service import get_servicebus_service
        sb = get_servicebus_service()
        sb.close()
        logger.info("Service Bus connections closed")
    except Exception as e:
        logger.warning(f"Error closing Service Bus: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-Driven Adaptive Cryptographic Policy Engine",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# ─── Rate Limiter ──────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ─── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Telemetry Middleware (Application Insights) ──────────────────────────────
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from app.services.telemetry_service import get_telemetry_service
    
    # Initialize telemetry
    telemetry_service = get_telemetry_service()
    
    # Instrument FastAPI with OpenTelemetry
    FastAPIInstrumentor.instrument_app(app)
    logger.info("OpenTelemetry instrumentation enabled")
except Exception as e:
    logger.warning(f"Telemetry instrumentation not available: {e}")

# ─── Security Headers ─────────────────────────────────────────────────────────
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(SessionTimeoutMiddleware)
app.add_middleware(SlowAPIMiddleware)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router)
app.include_router(classify.router)
app.include_router(encrypt.router)
app.include_router(decrypt.router)
app.include_router(policies.router)
app.include_router(share.router)
app.include_router(analytics.router)
app.include_router(benchmarks.router)
app.include_router(admin.router)
app.include_router(profile.router)
app.include_router(guest.router)
app.include_router(notifications.router)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """
    Health check endpoint for Azure Front Door probes and monitoring.
    
    Returns basic service health and version information.
    """
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "app": settings.APP_NAME,
    }
    
    # Check database connectivity (optional detailed check)
    try:
        from app.database import get_db
        async for db in get_db():
            await db.execute(text("SELECT 1"))
            health_status["database"] = "connected"
            break
    except Exception as e:
        health_status["database"] = "disconnected"
        health_status["status"] = "degraded"
        logger.warning(f"Health check: database connectivity issue: {e}")
    
    # Check Key Vault connectivity
    try:
        from app.services.keyvault_service import get_keyvault_service
        kv = get_keyvault_service()
        health_status["keyvault"] = "connected"
    except Exception as e:
        health_status["keyvault"] = "disconnected"
        health_status["status"] = "degraded"
        logger.warning(f"Health check: Key Vault connectivity issue: {e}")
    
    # Return appropriate status code
    status_code = 200 if health_status["status"] == "healthy" else 503
    
    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/health/ready")
async def readiness():
    """
    Readiness probe - checks if app is ready to serve traffic.
    """
    return {"status": "ready"}


@app.get("/health/live")
async def liveness():
    """
    Liveness probe - checks if app is alive (for Kubernetes-style health checks).
    """
    return {"status": "alive"}


# ─── Global Exception Handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler with telemetry tracking."""
    # Track exception in Application Insights
    try:
        from app.services.telemetry_service import get_telemetry_service
        telemetry = get_telemetry_service()
        telemetry.track_exception(exc, properties={
            "path": request.url.path,
            "method": request.method
        })
    except Exception as e:
        logger.error(f"Failed to track exception in telemetry: {e}")
    
    # Log the exception
    logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
    
    if settings.DEBUG:
        return JSONResponse({"detail": str(exc)}, status_code=500)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)
