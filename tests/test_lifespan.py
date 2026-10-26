"""Lifespan: recursos en app.state, hash ficticio una vez, dispose y arranque sin secretos."""
import asyncio

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from main import app

CLAVE_PRUEBA = "k" * 32


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    """Entorno controlado: secretos de prueba, bcrypt barato y sin .env real."""
    monkeypatch.chdir(tmp_path)
    for nombre, valor in {
        "POSTGRES_USER": "taller",
        "POSTGRES_PASSWORD": "pwd-de-prueba",
        "POSTGRES_DB": "taller_test",
        "JWT_SECRET_KEY": CLAVE_PRUEBA,
        "BCRYPT_COST": "4",
    }.items():
        monkeypatch.setenv(nombre, valor)
    return monkeypatch


async def test_estado_con_los_cinco_recursos_y_hash_ficticio_valido(entorno):
    async with app.router.lifespan_context(app):
        for nombre in ("settings", "engine", "session_factory", "bcrypt_semaforo", "hash_ficticio"):
            assert hasattr(app.state, nombre), nombre
        assert app.state.hash_ficticio.startswith(b"$2b$04$")
        assert bcrypt.checkpw(b"cualquier-cosa", app.state.hash_ficticio) is False


async def test_costo_de_bcrypt_viene_de_la_config(entorno):
    entorno.setenv("BCRYPT_COST", "5")
    async with app.router.lifespan_context(app):
        assert app.state.hash_ficticio.startswith(b"$2b$05$")


async def test_semaforo_admite_exactamente_bcrypt_max_concurrent(entorno):
    entorno.setenv("BCRYPT_MAX_CONCURRENT", "2")
    async with app.router.lifespan_context(app):
        semaforo = app.state.bcrypt_semaforo
        await asyncio.wait_for(semaforo.acquire(), 0.5)
        await asyncio.wait_for(semaforo.acquire(), 0.5)
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(semaforo.acquire(), 0.2)


async def test_el_hash_ficticio_se_calcula_una_sola_vez(entorno):
    llamadas = []
    original = bcrypt.hashpw

    def contador(*args, **kwargs):
        llamadas.append(1)
        return original(*args, **kwargs)

    entorno.setattr(bcrypt, "hashpw", contador)
    async with app.router.lifespan_context(app):
        # Varias peticiones a /health/live no vuelven a calcularlo.
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            for _ in range(3):
                r = await c.get("/health/live")
                assert r.status_code == 200
    assert len(llamadas) == 1


async def test_dispose_se_llama_una_vez_al_salir(entorno):
    llamadas = []
    original = AsyncEngine.dispose

    async def espia(self, *args, **kwargs):
        llamadas.append(1)
        await original(self, *args, **kwargs)

    entorno.setattr(AsyncEngine, "dispose", espia)
    async with app.router.lifespan_context(app):
        pass
    assert len(llamadas) == 1


async def test_dispose_se_llama_aunque_el_cuerpo_lance(entorno):
    llamadas = []
    original = AsyncEngine.dispose

    async def espia(self, *args, **kwargs):
        llamadas.append(1)
        await original(self, *args, **kwargs)

    entorno.setattr(AsyncEngine, "dispose", espia)
    with pytest.raises(RuntimeError):
        async with app.router.lifespan_context(app):
            raise RuntimeError("falla en el cuerpo")
    assert len(llamadas) == 1


async def test_arranque_sin_jwt_secret_key_falla_antes_del_yield(entorno):
    entorno.delenv("JWT_SECRET_KEY")
    with pytest.raises(ValidationError) as exc:
        async with app.router.lifespan_context(app):
            pytest.fail("no debería entrar al cuerpo")
    assert "JWT_SECRET_KEY" in str(exc.value)


async def test_arranque_con_puerto_cerrado_no_conecta_ni_falla(entorno):
    entorno.setenv("POSTGRES_PORT", "1")
    async with app.router.lifespan_context(app):
        assert hasattr(app.state, "engine")
