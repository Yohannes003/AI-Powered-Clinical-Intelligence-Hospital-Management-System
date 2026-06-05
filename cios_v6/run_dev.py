#!/usr/bin/env python3
"""
CIOS Dev Server — runs with SQLite, no Redis needed.
Usage: python run_dev.py
"""
import sys, os, warnings, asyncio
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

DB_PATH = os.path.join(os.path.dirname(__file__), 'backend', 'cios_dev.db')
DB_URL  = f'sqlite+aiosqlite:///{DB_PATH}'

# ── 1. Patch settings before ANY app import ─────────────
import app.core.config as _cfg
_cfg.settings.DATABASE_URL  = DB_URL
_cfg.settings.REDIS_URL      = ''
_cfg.settings.JWT_SECRET     = 'cios-dev-secret-2026'
_cfg.settings.DEBUG          = False
_cfg.settings.REPORTS_DIR    = os.path.join(os.path.dirname(__file__), 'backend', 'reports')
os.makedirs(_cfg.settings.REPORTS_DIR, exist_ok=True)

# ── 2. Patch DB session engine ───────────────────────────
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import app.db.session as _sess

_engine = create_async_engine(DB_URL, echo=False, connect_args={"check_same_thread": False})
_SessionLocal = async_sessionmaker(_engine, class_=AsyncSession,
                                   expire_on_commit=False, autocommit=False, autoflush=False)
_sess.engine           = _engine
_sess.AsyncSessionLocal = _SessionLocal

async def _get_db():
    async with _SessionLocal() as s:
        try:
            yield s
            await s.commit()
        except Exception:
            await s.rollback()
            raise
        finally:
            await s.close()
_sess.get_db = _get_db

# ── 3. Replace Redis event bus with safe in-memory ──────
import app.events.event_bus as _bus
_safe_bus = _bus.InMemoryEventBus()
_bus._event_bus   = _safe_bus
_bus.get_event_bus = lambda: _safe_bus

# ── 4. Now import and patch the FastAPI app ──────────────
from app.main import app
from fastapi import Depends
# Override get_db dependency everywhere
app.dependency_overrides[_sess.get_db] = _get_db

# ── 5. Start ─────────────────────────────────────────────
import uvicorn
uvicorn.run(app, host='0.0.0.0', port=8000,
            log_level='warning', access_log=True)
