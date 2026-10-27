"""POST /auth/logout, GET /auth/yo y POST /auth/cambiar-password (CH-04, US-010, RN-07)."""
import jwt
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.usuarios.models import EventoSeguridad, Usuario
from app.modules.usuarios.schemas import ACCION_CAMBIO_PASSWORD

CLIENTE = {"email": "cliente@example.com", "password": "Cliente.2026"}


async def _login(client, credenciales=CLIENTE) -> str:
    """Inicia sesión y devuelve el token. Vacía el frasco de cookies del cliente para
    que cada petición lleve sólo la cookie que el test indica explícitamente."""
    res = await client.post("/auth/login", json=credenciales)
    assert res.status_code == 200
    token = res.cookies["access_token"]
    client.cookies.clear()
    return token


def _cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"access_token={token}"}


# --- logout ------------------------------------------------------------------


async def test_logout_borra_la_cookie(client):
    res = await client.post("/auth/logout")
    assert res.status_code == 200
    assert res.json() == {"mensaje": "Sesión cerrada"}
    set_cookie = res.headers["set-cookie"].lower()
    assert set_cookie.startswith("access_token=")
    assert "max-age=0" in set_cookie
    assert "httponly" in set_cookie


# --- /auth/yo ----------------------------------------------------------------


async def test_yo_devuelve_usuario_roles_vigentes_y_del_token(sembrada, client):
    token = await _login(client)

    res = await client.get("/auth/yo", headers=_cookie(token))

    assert res.status_code == 200
    body = res.json()
    assert body == {
        "id": 6,
        "email": "cliente@example.com",
        "nombre": "Laura Cliente",
        "activo": True,
        "debe_cambiar_password": False,
        "roles_vigentes": ["CLIENTE"],
        "roles_token": ["CLIENTE"],
    }
    assert "password_hash" not in res.text


async def test_yo_muestra_la_diferencia_entre_base_y_token(sembrada, client, motor):
    from sqlalchemy import text

    token = await _login(client)
    # Se revoca el rol con la sesión abierta: el token sigue diciendo CLIENTE.
    async with motor.begin() as c:
        await c.execute(text("UPDATE asignacion_rol SET revocada_en = now() WHERE usuario_id = 6"))

    body = (await client.get("/auth/yo", headers=_cookie(token))).json()
    assert body["roles_vigentes"] == []
    assert body["roles_token"] == ["CLIENTE"]


async def test_yo_sin_cookie_401(client):
    assert (await client.get("/auth/yo")).status_code == 401


async def test_yo_con_bearer_y_sin_cookie_401(sembrada, client):
    token = await _login(client)
    res = await client.get("/auth/yo", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401


# --- cambiar-password ----------------------------------------------------------


async def test_cambio_de_password_invalida_la_cookie_anterior_sin_esperar(
    sembrada, client, motor
):
    token_viejo = await _login(client)

    res = await client.post(
        "/auth/cambiar-password",
        headers=_cookie(token_viejo),
        json={"password_actual": "Cliente.2026", "password_nueva": "Nueva.Clave.2026"},
    )

    assert res.status_code == 200
    assert res.json() == {"mensaje": "Contraseña actualizada"}
    token_nuevo = res.cookies["access_token"]
    assert token_nuevo != token_viejo
    assert "httponly" in res.headers["set-cookie"].lower()
    client.cookies.clear()

    # sin ningún sleep: la cookie vieja cae y la nueva entra
    assert (await client.get("/auth/yo", headers=_cookie(token_viejo))).status_code == 401
    assert (await client.get("/auth/yo", headers=_cookie(token_nuevo))).status_code == 200

    # el iat del token nuevo no es anterior a password_cambiada_en (sin truncar)
    iat_nuevo = jwt.decode(token_nuevo, options={"verify_signature": False})["iat"]
    fabrica = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as s:
        usuario = await s.get(Usuario, 6)
        assert usuario.debe_cambiar_password is False
        assert usuario.password_cambiada_en is not None
        assert iat_nuevo >= usuario.password_cambiada_en.timestamp()
        eventos = (
            await s.exec(
                select(EventoSeguridad).where(
                    EventoSeguridad.actor == "cliente@example.com",
                    EventoSeguridad.accion == ACCION_CAMBIO_PASSWORD,
                )
            )
        ).all()
        assert len(eventos) == 1

    # la contraseña nueva sirve para iniciar sesión y la vieja ya no
    assert (await client.post("/auth/login", json=CLIENTE)).status_code == 401
    nueva = {"email": CLIENTE["email"], "password": "Nueva.Clave.2026"}
    assert (await client.post("/auth/login", json=nueva)).status_code == 200


async def test_cambio_obligatorio_baja_el_flag(sembrada, client):
    token = await _login(client, {"email": "nuevo@example.com", "password": "Provisoria.2026"})
    res = await client.post(
        "/auth/cambiar-password",
        headers=_cookie(token),
        json={"password_actual": "Provisoria.2026", "password_nueva": "Definitiva.2026"},
    )
    assert res.status_code == 200
    token_nuevo = res.cookies["access_token"]
    client.cookies.clear()
    body = (await client.get("/auth/yo", headers=_cookie(token_nuevo))).json()
    assert body["debe_cambiar_password"] is False


async def test_cambio_con_password_actual_incorrecta_401_sin_cambios(sembrada, client, motor):
    token = await _login(client)

    res = await client.post(
        "/auth/cambiar-password",
        headers=_cookie(token),
        json={"password_actual": "Equivocada.1", "password_nueva": "Nueva.Clave.2026"},
    )

    assert res.status_code == 401
    assert "set-cookie" not in res.headers
    fabrica = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    async with fabrica() as s:
        usuario = await s.get(Usuario, 6)
        assert usuario.password_cambiada_en is None
        eventos = (
            await s.exec(
                select(EventoSeguridad).where(EventoSeguridad.accion == ACCION_CAMBIO_PASSWORD)
            )
        ).all()
        assert eventos == []
    # la sesión sigue valiendo
    assert (await client.get("/auth/yo", headers=_cookie(token))).status_code == 200


async def test_cambio_sin_sesion_401(client):
    res = await client.post(
        "/auth/cambiar-password",
        json={"password_actual": "Cliente.2026", "password_nueva": "Nueva.Clave.2026"},
    )
    assert res.status_code == 401


async def test_cambio_con_mas_de_72_bytes_422(sembrada, client):
    token = await _login(client)
    for cuerpo in (
        {"password_actual": "a" * 73, "password_nueva": "Nueva.Clave.2026"},
        {"password_actual": "Cliente.2026", "password_nueva": "ñ" * 37},
    ):
        res = await client.post("/auth/cambiar-password", headers=_cookie(token), json=cuerpo)
        assert res.status_code == 422
