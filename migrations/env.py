import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel

from alembic import context

# Registro de modelos: importa las 13 tablas para que autogenerate las vea.
import app.modules.modelos  # noqa: F401
from app.core.config import get_settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

# Regla 8 de CLAUDE.md: sin secretos en alembic.ini ni en el código. La URL sale
# de get_settings().DATABASE_URL (entorno / .env); si falta la contraseña de la
# base, get_settings() lanza el error de configuración y Alembic no arranca.
# Por eso NO se usa config.set_main_option("sqlalchemy.url", ...): ConfigParser
# interpreta el "%" y una contraseña que lo tenga rompería la migración (y la URL
# no debe pasar por la configuración de Alembic). Hay que correr Alembic desde la
# raíz del repo: el .env se lee relativo al directorio actual.


def run_migrations_offline() -> None:
    """Modo offline: genera el SQL sin conectarse (alembic upgrade --sql)."""
    context.configure(
        url=get_settings().DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Motor propio, sin pool: Alembic abre una conexión y la cierra."""
    connectable = create_async_engine(
        get_settings().DATABASE_URL, poolclass=pool.NullPool
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
