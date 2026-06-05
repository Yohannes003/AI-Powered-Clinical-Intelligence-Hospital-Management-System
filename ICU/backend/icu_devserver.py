import sys, os, warnings
warnings.filterwarnings("ignore")

os.environ["DATABASE_URL"] = f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icu_dev.db')}"

import app.database as _db
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

_sqlite_url = f"sqlite:///{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'icu_dev.db')}"
_db.engine = create_engine(_sqlite_url, echo=False, connect_args={"check_same_thread": False})
_db.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_db.engine)

@event.listens_for(_db.engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

from app.main import app
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
