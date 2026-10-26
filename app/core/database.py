from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings

# Regla 7: nada de esto se ejecuta al importar. El motor y la fábrica los crea
# el lifespan de main.py y viven en app.state.


def crear_motor(settings: Settings) -> AsyncEngine:
    """Crea el motor async. No conecta: los motores de SQLAlchemy son perezosos."""
    return create_async_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        echo=settings.SQL_ECHO,
        pool_pre_ping=True,
    )


def crear_fabrica_sesiones(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Fábrica de sesiones con expire_on_commit=False (regla 7)."""
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Una sesión por petición, tomada de app.state. No hace commit (es del UoW)."""
    async with request.app.state.session_factory() as session:
        yield session
