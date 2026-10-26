"""Tests de app.core.database: fábricas puras y get_session (CH-01, regla 7)."""
import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings
from app.core.database import crear_fabrica_sesiones, crear_motor, get_session


def _settings(monkeypatch, **extra):
    base = {
        "POSTGRES_USER": "taller",
        "POSTGRES_PASSWORD": "pwd-de-prueba",
        "POSTGRES_DB": "taller_test",
        "JWT_SECRET_KEY": "k" * 32,
    }
    for k, v in {**base, **extra}.items():
        monkeypatch.setenv(k, str(v))
    return Settings(_env_file=None)


@pytest.mark.parametrize(
    "pool, echo", [(2, True), (5, False)]
)
def test_crear_motor_respeta_pool_y_echo(monkeypatch, pool, echo):
    settings = _settings(monkeypatch, DB_POOL_SIZE=pool, SQL_ECHO=str(echo).lower())
    engine = crear_motor(settings)
    assert engine.pool.size() == pool
    assert engine.echo is echo
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "asyncpg"


def test_fabrica_crea_asyncsession_sin_expirar_al_commit(monkeypatch):
    engine = crear_motor(_settings(monkeypatch))
    fabrica = crear_fabrica_sesiones(engine)
    s1, s2 = fabrica(), fabrica()
    assert isinstance(s1, AsyncSession)
    assert s1.sync_session.expire_on_commit is False
    assert s1 is not s2


@pytest.fixture
def cierres(monkeypatch):
    """Cuenta las llamadas a close() por sesión (delegando en el original)."""
    registro = {}
    original = AsyncSession.close

    async def espia(self):
        registro[id(self)] = registro.get(id(self), 0) + 1
        await original(self)

    monkeypatch.setattr(AsyncSession, "close", espia)
    return registro


def _app_con_fabrica(monkeypatch, capturadas):
    engine = crear_motor(_settings(monkeypatch))
    app = FastAPI()
    app.state.session_factory = crear_fabrica_sesiones(engine)

    @app.get("/ok")
    async def ok(session: AsyncSession = Depends(get_session)):
        capturadas.append(session)
        return {"ok": True}

    @app.get("/falla")
    async def falla(session: AsyncSession = Depends(get_session)):
        capturadas.append(session)
        raise RuntimeError("boom")

    return app


async def test_get_session_entrega_sesion_de_la_fabrica_y_la_cierra(monkeypatch, cierres):
    capturadas = []
    app = _app_con_fabrica(monkeypatch, capturadas)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r1 = await c.get("/ok")
        r2 = await c.get("/ok")
    assert r1.status_code == 200
    assert isinstance(capturadas[0], AsyncSession)
    assert capturadas[0] is not capturadas[1]
    assert r2.status_code == 200
    assert cierres[id(capturadas[0])] == 1
    assert cierres[id(capturadas[1])] == 1


async def test_get_session_cierra_la_sesion_aunque_la_ruta_falle(monkeypatch, cierres):
    capturadas = []
    app = _app_con_fabrica(monkeypatch, capturadas)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://t") as c:
        r = await c.get("/falla")
    assert r.status_code == 500
    assert cierres[id(capturadas[0])] == 1
