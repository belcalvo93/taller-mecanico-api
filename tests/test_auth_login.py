"""POST /auth/login (CH-04, US-009): cookie, límite de intentos y anti-enumeración.

RN-08, RN-09, SU-02, casos C-03, C-04 y C-05.
"""
from datetime import timedelta

import bcrypt
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import ahora_utc
from app.modules.usuarios.models import IntentoAcceso

CLIENTE = {"email": "cliente@example.com", "password": "Cliente.2026"}
IP_TEST = "127.0.0.1"  # la IP que informa httpx.ASGITransport


@pytest.fixture
def espia_checkpw(monkeypatch):
    """Cuenta las llamadas a bcrypt.checkpw (security.py lo llama a través del módulo)."""
    llamadas = []
    original = bcrypt.checkpw

    def _espia(password, hashed):
        llamadas.append(hashed)
        return original(password, hashed)

    monkeypatch.setattr(bcrypt, "checkpw", _espia)
    return llamadas


async def _intentos(motor, email: str) -> list[IntentoAcceso]:
    fabrica = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as s:
        res = await s.exec(
            select(IntentoAcceso)
            .where(IntentoAcceso.email == email)
            .order_by(IntentoAcceso.cuando)
        )
        return list(res.all())


async def test_login_exitoso_cookie_httponly_y_cuerpo_sin_token(sembrada, client, motor):
    res = await client.post("/auth/login", json=CLIENTE)

    assert res.status_code == 200
    assert res.json() == {
        "mensaje": "Sesión iniciada",
        "debe_cambiar_password": False,
        "expira_en_segundos": 1800,
    }
    set_cookie = res.headers["set-cookie"]
    assert set_cookie.startswith("access_token=")
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()
    assert "max-age=1800" in set_cookie.lower()
    # COOKIE_SECURE=false en el entorno de tests
    assert "secure" not in set_cookie.lower().replace("samesite", "")
    # el token nunca viaja en el cuerpo
    token = res.cookies["access_token"]
    assert token not in res.text

    intentos = await _intentos(motor, CLIENTE["email"])
    assert [(i.exito, i.ip) for i in intentos] == [(True, IP_TEST)]


async def test_login_usuario_con_cambio_pendiente_informa_el_flag(sembrada, client):
    res = await client.post(
        "/auth/login", json={"email": "nuevo@example.com", "password": "Provisoria.2026"}
    )
    assert res.status_code == 200
    assert res.json()["debe_cambiar_password"] is True


async def test_login_anti_enumeracion_mismo_401_y_ambos_usan_bcrypt(
    sembrada, client, motor, espia_checkpw
):
    mala = await client.post(
        "/auth/login", json={"email": CLIENTE["email"], "password": "Incorrecta.1"}
    )
    inexistente = await client.post(
        "/auth/login", json={"email": "nadie@example.com", "password": "Incorrecta.1"}
    )

    assert mala.status_code == inexistente.status_code == 401
    assert mala.json() == inexistente.json() == {"detail": "Credenciales inválidas"}
    assert "set-cookie" not in mala.headers
    assert "set-cookie" not in inexistente.headers
    # las dos verificaron con bcrypt: una contra el hash real y otra contra el ficticio
    assert len(espia_checkpw) == 2
    from main import app

    assert app.state.hash_ficticio in espia_checkpw

    # los fallos quedaron confirmados aunque la petición respondió 401 (sesión propia)
    assert [i.exito for i in await _intentos(motor, CLIENTE["email"])] == [False]
    assert [i.exito for i in await _intentos(motor, "nadie@example.com")] == [False]


async def test_login_usuario_inactivo_responde_igual_que_inexistente(sembrada, client, motor):
    from sqlalchemy import text

    async with motor.begin() as c:
        await c.execute(text("UPDATE usuario SET activo = false WHERE email = 'cliente@example.com'"))

    res = await client.post("/auth/login", json=CLIENTE)
    assert res.status_code == 401
    assert res.json() == {"detail": "Credenciales inválidas"}


async def test_sexto_intento_429_sin_bcrypt_y_sin_sexta_fila(
    sembrada, client, motor, espia_checkpw
):
    for _ in range(5):
        res = await client.post(
            "/auth/login", json={"email": CLIENTE["email"], "password": "Incorrecta.1"}
        )
        assert res.status_code == 401
    assert len(espia_checkpw) == 5

    # el sexto, aun con la contraseña correcta, queda bloqueado sin calcular hash
    sexto = await client.post("/auth/login", json=CLIENTE)

    assert sexto.status_code == 429
    assert 1 <= int(sexto.headers["retry-after"]) <= 60
    assert "set-cookie" not in sexto.headers
    assert len(espia_checkpw) == 5
    intentos = await _intentos(motor, CLIENTE["email"])
    assert [i.exito for i in intentos] == [False] * 5


async def test_fallos_fuera_de_la_ventana_no_bloquean(sembrada, client, motor):
    viejo = ahora_utc() - timedelta(seconds=61)
    fabrica = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as s:
        for _ in range(5):
            s.add(IntentoAcceso(email=CLIENTE["email"], ip=IP_TEST, exito=False, cuando=viejo))
        await s.commit()

    res = await client.post("/auth/login", json=CLIENTE)
    assert res.status_code == 200


async def test_login_exitoso_reinicia_el_conteo(sembrada, client, motor):
    mala = {"email": CLIENTE["email"], "password": "Incorrecta.1"}
    for _ in range(3):
        assert (await client.post("/auth/login", json=mala)).status_code == 401
    assert (await client.post("/auth/login", json=CLIENTE)).status_code == 200
    # sin el reinicio, el 3.er fallo de acá sería el 6.º de la ventana → 429
    for _ in range(4):
        assert (await client.post("/auth/login", json=mala)).status_code == 401

    # las filas anteriores al éxito siguen en la tabla
    intentos = await _intentos(motor, CLIENTE["email"])
    assert [i.exito for i in intentos] == [False] * 3 + [True] + [False] * 4


async def test_login_contrasena_mayor_a_72_bytes_422(client):
    res = await client.post(
        "/auth/login", json={"email": CLIENTE["email"], "password": "ñ" * 37}
    )
    assert res.status_code == 422


async def test_login_campo_extra_422(client):
    res = await client.post("/auth/login", json={**CLIENTE, "recordarme": True})
    assert res.status_code == 422
