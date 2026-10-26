from collections.abc import AsyncIterator
from datetime import datetime, timezone

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings

# Nombres fijos de restricciones e índices: los otros changes traducen el
# IntegrityError a 409 por nombre y el downgrade de Alembic puede referenciarlos.
# Es configuración de metadatos (no conecta ni lee el entorno): no viola la regla 7.
# Se fija acá porque todos los modelos importan este módulo antes de declarar tablas.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
SQLModel.metadata.naming_convention = NAMING_CONVENTION


def ahora_utc() -> datetime:
    """Instante actual con zona UTC y microsegundos (default de las columnas timestamptz)."""
    return datetime.now(timezone.utc)


# Regla 7: nada de lo que sigue se ejecuta al importar. El motor y la fábrica
# los crea el lifespan de main.py y viven en app.state.


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
