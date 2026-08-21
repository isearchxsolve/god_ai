from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


class Base(DeclarativeBase):
    pass


# Engine is created lazily so importing this module does not require a live DB.
engine = None
async_session_maker = None


def _init_engine():
    """Create the async engine + session maker on first use."""
    global engine, async_session_maker
    if engine is None:
        if not settings.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured")
        engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
        async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, async_session_maker


async def init_db():
    _, session_maker = _init_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    _, session_maker = _init_engine()
    async with session_maker() as session:
        yield session