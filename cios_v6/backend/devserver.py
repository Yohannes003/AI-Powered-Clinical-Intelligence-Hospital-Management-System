import sys, os, warnings
warnings.filterwarnings("ignore")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cios_dev.db")
DB_URL  = f"sqlite+aiosqlite:///{DB_PATH}"

import app.core.config as _cfg
_cfg.settings.DATABASE_URL = DB_URL
_cfg.settings.REDIS_URL    = ""
_cfg.settings.JWT_SECRET   = "cios-dev-secret-2026"
_cfg.settings.ICU_DATABASE_URL = ""
_cfg.settings.DEBUG        = False
_cfg.settings.REPORTS_DIR  = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reports")
os.makedirs(_cfg.settings.REPORTS_DIR, exist_ok=True)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
import app.db.session as _sess
_engine = create_async_engine(DB_URL, echo=False)
_SL = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)
_sess.engine = _engine
_sess.AsyncSessionLocal = _SL

async def _gdb():
    async with _SL() as s:
        try:
            yield s; await s.commit()
        except: await s.rollback(); raise
        finally: await s.close()
_sess.get_db = _gdb

import app.events.event_bus as _bus
_sb = _bus.InMemoryEventBus()
_bus._event_bus = _sb
_bus.get_event_bus = lambda: _sb

from app.main import app
app.dependency_overrides[_sess.get_db] = _gdb

import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
