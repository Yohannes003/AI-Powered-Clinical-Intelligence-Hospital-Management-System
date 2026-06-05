"""
CIOS — Clinical Intelligence Operating System
FastAPI Application Entry Point
"""
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from loguru import logger
import time
import asyncio
import os
from collections import defaultdict

from app.core.config import settings
from app.api.v1.router import api_router
from app.db.session import init_db
from app.events.event_bus import get_event_bus
from app.events.handlers import register_handlers
from app.services.icu_sync import start_icu_sync


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    logger.info("🏥 CIOS Starting up...")

    # Initialize database
    await init_db()
    logger.info("✅ Database initialized")

    # Seed default users
    from app.db.session import AsyncSessionLocal
    from app.services.user_service import UserService
    async with AsyncSessionLocal() as db:
        await UserService.seed_default_users(db)
        await db.commit()
    logger.info("✅ Default users seeded")

    # Start event bus (InMemoryEventBus — no Redis needed for dev)
    from app.events.event_bus import InMemoryEventBus
    import app.events.event_bus as _bus_module
    bus = InMemoryEventBus()
    _bus_module._event_bus = bus
    _bus_module.get_event_bus = lambda: bus
    register_handlers(bus)
    await bus.start()
    logger.info("✅ Event bus started (in-memory)")

    # Start ICU sync background task if ICU DB configured
    app.state._icu_sync_stop = asyncio.Event()
    app.state._icu_sync_task = asyncio.create_task(
        start_icu_sync(app.state._icu_sync_stop, interval_seconds=getattr(settings, 'ICU_SYNC_INTERVAL_SECONDS', 300))
    )
    logger.info("✅ ICU sync background task started")

    logger.info(f"🚀 CIOS v{settings.APP_VERSION} running — {settings.ENVIRONMENT}")
    yield

    # Shutdown
    # Stop ICU sync task
    try:
        app.state._icu_sync_stop.set()
        await app.state._icu_sync_task
    except Exception:
        logger.exception("Error stopping ICU sync task")

    await bus.stop()
    logger.info("🛑 CIOS shutting down")


app = FastAPI(
    title="CIOS — Clinical Intelligence Operating System",
    description="""
## 🏥 Clinical Intelligence Operating System

A production-grade AI-native hospital ERP with:
- **Real-time AI risk prediction** with explainable outputs
- **Clinical Digital Twin** per patient
- **Anomaly Detection** on vitals and labs
- **Event-driven architecture** (Kafka-ready)
- **Immutable audit trail** (HIPAA-ready)
- **Multi-format reporting** (PDF, CSV, Excel, XPS)

### Authentication
Use `/api/v1/auth/login` to get a JWT token, then click **Authorize** above.

Default credentials:
- Admin: `admin@cios.hospital` / `Admin@123`
- Doctor: `doctor@cios.hospital` / `Doctor@123`
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ─── Middleware ──────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Rate Limiter ──────────────────────────────────────────
_rate_limit_store: dict = defaultdict(list)
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 120


@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    if request.url.path in ("/", "/health", "/docs", "/redoc", "/openapi.json"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW

    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if t > window_start
    ]

    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Rate limit exceeded. Please slow down.", "retry_after_seconds": 60},
            headers={"Retry-After": "60"},
        )

    _rate_limit_store[client_ip].append(now)
    response = await call_next(request)
    return response


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = round((time.time() - start) * 1000, 2)
    response.headers["X-Response-Time"] = f"{duration}ms"
    response.headers["X-CIOS-Version"] = settings.APP_VERSION
    return response


# ─── Exception Handlers ──────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc} | Path: {request.url.path}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "path": str(request.url.path)}
    )


# ─── Static Files (Frontend) ─────────────────────────────
FRONTEND_BUILD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "frontend", "build")


# ─── Routes ──────────────────────────────────────────────
app.include_router(api_router)


@app.get("/health", tags=["System"])
async def health_check():
    from app.db.session import engine
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "healthy"
    except Exception:
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": db_status,
        "ai_engine": "operational",
        "event_bus": "operational",
    }


# ─── Frontend SPA (must be last — catch-all) ─────────────
if os.path.isdir(FRONTEND_BUILD):
    app.mount("/static", StaticFiles(directory=os.path.join(FRONTEND_BUILD, "static")), name="frontend_static")

    _frontend_index = os.path.join(FRONTEND_BUILD, "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str):
        import mimetypes
        from fastapi.responses import FileResponse as FR
        static_path = os.path.join(FRONTEND_BUILD, full_path)
        if full_path and os.path.isfile(static_path):
            content_type, _ = mimetypes.guess_type(static_path)
            return FR(static_path, media_type=content_type)
        return FR(_frontend_index)
