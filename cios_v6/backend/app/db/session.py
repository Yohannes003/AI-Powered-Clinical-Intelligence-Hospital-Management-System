from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.core.config import settings


def get_async_url(url: str) -> str:
    """Convert sync DB URL to async driver URL."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    return url


ASYNC_DATABASE_URL = get_async_url(settings.DATABASE_URL)
_is_sqlite = "sqlite" in ASYNC_DATABASE_URL

if _is_sqlite:
    # SQLite needs StaticPool and check_same_thread=False for async use
    engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_async_engine(
        ASYNC_DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    from app.models.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---- Optional ICU DB connection ---------------------------------
ICU_ASYNC_DATABASE_URL = None
ICU_engine = None
ICU_AsyncSessionLocal = None

if getattr(settings, 'ICU_DATABASE_URL', None):
    ICU_ASYNC_DATABASE_URL = get_async_url(settings.ICU_DATABASE_URL)
    if "sqlite" in ICU_ASYNC_DATABASE_URL:
        ICU_engine = create_async_engine(
            ICU_ASYNC_DATABASE_URL,
            echo=settings.DEBUG,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        ICU_engine = create_async_engine(
            ICU_ASYNC_DATABASE_URL,
            echo=settings.DEBUG,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_pre_ping=True,
        )

    ICU_AsyncSessionLocal = async_sessionmaker(
        ICU_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


async def get_icu_db() -> AsyncSession:
    """Yield an async session connected to the ICU database (if configured)."""
    if ICU_AsyncSessionLocal is None:
        raise RuntimeError("ICU database not configured")
    async with ICU_AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def safe_get_icu_db():
    """Returns an ICU DB session or None if ICU not configured.
    Callers must handle commit/rollback and close the session."""
    if ICU_AsyncSessionLocal is None:
        return None
    return ICU_AsyncSessionLocal()
