import os
import subprocess
import sys
from pathlib import Path

# Antes de importar la app: los tests nunca tocan la base de desarrollo. El resto
# de las credenciales sale del .env de cada integrante (código de test, no de la app).
BASE_DE_TESTS = "taller_test"
os.environ["POSTGRES_DB"] = BASE_DE_TESTS

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from main import app  # noqa: E402


@pytest.fixture(autouse=True)
def _limpiar_cache_de_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def client():
    """Cliente httpx sobre la app con su lifespan corriendo.

    ASGITransport no ejecuta el lifespan por sí mismo, por eso se entra a mano.
    """
    async with app.router.lifespan_context(app):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c


@pytest.fixture
def puerto_cerrado(monkeypatch):
    """La app arrancará apuntando a un puerto local sin servidor."""
    monkeypatch.setenv("POSTGRES_PORT", "1")


@pytest.fixture
def sql_echo(monkeypatch):
    """La app arrancará con SQL_ECHO=true."""
    monkeypatch.setenv("SQL_ECHO", "true")


@pytest.fixture
def client_factory():
    """Para tests que cambian el entorno antes de arrancar la app: `async with client_factory() as c`."""
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _crear():
        get_settings.cache_clear()
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                yield c

    return _crear


RAIZ = Path(__file__).resolve().parent.parent


def migrar_base_de_tests(raiz: Path, base: str) -> None:
    """Aplica `alembic upgrade head` sobre la base de tests (nunca create_all).

    Se ejercita de punta a punta con CH-02. Contrato con CH-02: el env.py de
    Alembic toma la URL de get_settings().DATABASE_URL (nunca de alembic.ini),
    así que la variable POSTGRES_DB del subproceso decide la base.
    """
    if not (raiz / "alembic.ini").exists():
        pytest.skip("se ejercita cuando CH-02 agregue las migraciones")
    if not base.endswith("_test"):
        raise RuntimeError(f"Se niega a migrar una base que no termina en _test: {base!r}")
    # Subproceso para no anidar el asyncio.run del env.py async de Alembic
    # dentro del bucle de pytest-asyncio.
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=raiz,
        env={**os.environ, "POSTGRES_DB": base},
        check=True,
    )


@pytest.fixture(scope="session")
def base_migrada():
    migrar_base_de_tests(RAIZ, BASE_DE_TESTS)
