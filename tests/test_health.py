"""Salud: /health/live (sin base) y /health/ready (con base)."""
import asyncio
import time

from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.health import router


async def test_live_responde_200_ok(client):
    r = await client.get("/health/live")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok"}


async def test_live_no_necesita_la_base_ni_abre_sesiones(puerto_cerrado, client):
    # `puerto_cerrado` va antes que `client`: la app arranca apuntando a un puerto sin servidor.
    sesiones = []
    client._transport.app.state.session_factory = lambda: sesiones.append(1)
    r = await client.get("/health/live")
    assert r.status_code == 200
    assert sesiones == []


async def test_ready_con_la_base_real_responde_200(sql_echo, caplog, client):
    r = await client.get("/health/ready")
    assert r.status_code == 200
    assert r.json() == {"estado": "ok", "base": "ok"}
    # SQL_ECHO=true deja la consulta a la vista (regla 17).
    assert any("SELECT 1" in m for m in caplog.messages)


CUERPO_503 = {"estado": "no disponible", "base": "no disponible"}


async def test_ready_con_la_base_caida_responde_503_en_pocos_segundos(puerto_cerrado, client):
    inicio = time.monotonic()
    r = await client.get("/health/ready")
    assert r.status_code == 503
    assert r.json() == CUERPO_503
    assert time.monotonic() - inicio < 4


PALABRAS_PROHIBIDAS = ("asyncpg", "Traceback", "password", "localhost")


def _cuerpo_limpio(respuesta, *extra):
    texto = respuesta.text
    for prohibida in (*PALABRAS_PROHIBIDAS, *extra):
        assert prohibida not in texto, prohibida


async def test_ready_503_con_contrasena_incorrecta(monkeypatch, client_factory):
    monkeypatch.setenv("POSTGRES_PASSWORD", "clave-incorrecta-xyz")
    async with client_factory() as c:
        r = await c.get("/health/ready")
    assert r.status_code == 503
    assert r.json() == CUERPO_503
    _cuerpo_limpio(r, "clave-incorrecta-xyz")


async def test_ready_503_con_base_inexistente(monkeypatch, client_factory):
    monkeypatch.setenv("POSTGRES_DB", "no_existe_test")
    async with client_factory() as c:
        r = await c.get("/health/ready")
    assert r.status_code == 503
    assert r.json() == CUERPO_503
    _cuerpo_limpio(r, "no_existe_test")


async def test_ready_503_si_la_consulta_no_termina_a_tiempo(monkeypatch, client_factory):
    async def nunca_termina(self, *args, **kwargs):
        await asyncio.sleep(30)

    monkeypatch.setattr(router, "TIEMPO_MAXIMO_READY_SEGUNDOS", 0.05)
    monkeypatch.setattr(AsyncSession, "exec", nunca_termina)
    async with client_factory() as c:
        r = await c.get("/health/ready")
    assert r.status_code == 503
    assert r.json() == CUERPO_503
    _cuerpo_limpio(r)


async def test_ready_registra_solo_el_nombre_de_la_clase_de_la_excepcion(
    monkeypatch, caplog, client_factory
):
    monkeypatch.setenv("POSTGRES_PASSWORD", "clave-incorrecta-xyz")
    async with client_factory() as c:
        await c.get("/health/ready")
    avisos = [r for r in caplog.records if r.levelname == "WARNING" and "ready" in r.getMessage()]
    assert len(avisos) == 1
    mensaje = avisos[0].getMessage()
    assert "DBAPIError" in mensaje  # SQLAlchemy envuelve el error de asyncpg
    assert "clave-incorrecta-xyz" not in mensaje
    assert "localhost" not in mensaje
