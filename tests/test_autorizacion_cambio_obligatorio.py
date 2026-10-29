"""CH-05 (Grupo 1): Control transversal de cambio obligatorio de contraseña (US-011, US-013, RN-06, C-09)."""
import pytest
from fastapi import HTTPException

from app.core.dependencies import verificar_cambio_password_obligatorio
from app.modules.usuarios.models import Usuario

NUEVO = {"email": "nuevo@example.com", "password": "Provisoria.2026"}


async def _login(client, credenciales=NUEVO) -> str:
    res = await client.post("/auth/login", json=credenciales)
    assert res.status_code == 200
    token = res.cookies["access_token"]
    client.cookies.clear()
    return token


def _cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"access_token={token}"}


async def test_dependencia_permite_usuario_sin_cambio_obligatorio():
    usuario = Usuario(
        id=1,
        email="admin@example.com",
        nombre="Ana",
        password_hash="hash",
        activo=True,
        debe_cambiar_password=False,
    )
    resultado = await verificar_cambio_password_obligatorio(usuario=usuario)
    assert resultado is usuario


async def test_dependencia_rechaza_403_usuario_con_cambio_obligatorio():
    usuario = Usuario(
        id=7,
        email="nuevo@example.com",
        nombre="Nicolás",
        password_hash="hash",
        activo=True,
        debe_cambiar_password=True,
    )
    with pytest.raises(HTTPException) as exc_info:
        await verificar_cambio_password_obligatorio(usuario=usuario)
    assert exc_info.value.status_code == 403
    assert "contraseña" in exc_info.value.detail.lower()


async def test_usuario_con_cambio_obligatorio_bloqueado_en_grupo_protegido_y_permitido_en_auth(
    sembrada, client
):
    token = await _login(client, NUEVO)

    # En rutas protegidas responde 403
    res_vehiculos = await client.get("/mis-vehiculos", headers=_cookie(token))
    assert res_vehiculos.status_code == 403

    res_clientes = await client.get("/clientes/1", headers=_cookie(token))
    assert res_clientes.status_code == 403

    # En /auth/yo responde 200
    res_yo = await client.get("/auth/yo", headers=_cookie(token))
    assert res_yo.status_code == 200
    assert res_yo.json()["debe_cambiar_password"] is True

    # En /auth/logout responde 200
    res_logout = await client.post("/auth/logout", headers=_cookie(token))
    assert res_logout.status_code == 200


async def test_c09_flujo_completo_cambio_obligatorio_desbloquea_sin_esperar(sembrada, client):
    token_viejo = await _login(client, NUEVO)

    # Bloqueado antes del cambio
    assert (await client.get("/mis-vehiculos", headers=_cookie(token_viejo))).status_code == 403

    # Cambia la contraseña provisoria sin sleep
    res_cambio = await client.post(
        "/auth/cambiar-password",
        headers=_cookie(token_viejo),
        json={"password_actual": "Provisoria.2026", "password_nueva": "Definitiva.2026"},
    )
    assert res_cambio.status_code == 200
    token_nuevo = res_cambio.cookies["access_token"]
    client.cookies.clear()

    # La cookie nueva accede al grupo protegido (200) y la vieja da 401
    res_protegida_nueva = await client.get("/mis-vehiculos", headers=_cookie(token_nuevo))
    assert res_protegida_nueva.status_code == 200
    assert res_protegida_nueva.json() == []

    res_protegida_vieja = await client.get("/mis-vehiculos", headers=_cookie(token_viejo))
    assert res_protegida_vieja.status_code == 401


async def test_sin_sesion_en_grupo_protegido_responde_401_antes_que_403(client):
    res = await client.get("/mis-vehiculos")
    assert res.status_code == 401
