"""CH-05 (Grupo 3): Tests de integración de POST /usuarios, GET/POST/DELETE /usuarios/{id}/roles y GET /eventos."""
from datetime import datetime, timedelta, timezone

import bcrypt
import pytest
from fastapi import FastAPI
from sqlalchemy import text

import main
from app.core.database import ahora_utc
from app.modules.usuarios import service

ADMIN_CREDS = {"email": "admin@example.com", "password": "Admin.2026"}
ADMIN2_CREDS = {"email": "admin2@example.com", "password": "Admin2.2026"}
RECEPCION_CREDS = {"email": "recepcion@example.com", "password": "Recepcion.2026"}
MECANICO_CREDS = {"email": "mecanico@example.com", "password": "Mecanico.2026"}


async def _login(client, credenciales=ADMIN_CREDS) -> str:
    res = await client.post("/auth/login", json=credenciales)
    assert res.status_code == 200
    token = res.cookies["access_token"]
    client.cookies.clear()
    return token


def _cookie(token: str) -> dict[str, str]:
    return {"Cookie": f"access_token={token}"}


async def _escalar(motor, sql: str, **params):
    async with motor.connect() as c:
        return (await c.execute(text(sql), params)).scalar()


# --- Grupo de rutas en main.py ------------------------------------------------


def _rutas_del_grupo(grupo) -> set[tuple[str, str]]:
    app = FastAPI()
    app.include_router(grupo)
    return {(m.upper(), ruta) for ruta, ops in app.openapi()["paths"].items() for m in ops}


def test_las_cinco_rutas_de_ch05_estan_en_el_grupo_protegido():
    protegidas = _rutas_del_grupo(main.rutas_protegidas)
    abiertas = {ruta for _, ruta in _rutas_del_grupo(main.rutas_abiertas)}
    for metodo, ruta in [
        ("POST", "/usuarios"),
        ("GET", "/usuarios/{id}/roles"),
        ("POST", "/usuarios/{id}/roles"),
        ("DELETE", "/usuarios/{id}/roles/{rol}"),
        ("GET", "/eventos"),
    ]:
        assert (metodo, ruta) in protegidas
        assert ruta not in abiertas


# --- POST /usuarios (alta de personal) ----------------------------------------


async def test_alta_personal_201_crea_usuario_rol_y_evento(sembrada, client, motor):
    token_admin = await _login(client, ADMIN_CREDS)

    res = await client.post(
        "/usuarios",
        headers=_cookie(token_admin),
        json={
            "email": "mecanico3@example.com",
            "nombre": "Marcos Mecánico",
            "password": "Provisoria.2026",
            "rol": "MECANICO",
        },
    )
    assert res.status_code == 201
    cuerpo = res.json()
    assert cuerpo == {
        "id": 8,
        "email": "mecanico3@example.com",
        "nombre": "Marcos Mecánico",
        "activo": True,
        "debe_cambiar_password": True,
        "rol": "MECANICO",
    }
    assert "password_hash" not in res.text

    # La asignación tiene otorgada_por = 1 (admin@example.com)
    otorgada_por = await _escalar(
        motor,
        "SELECT otorgada_por FROM asignacion_rol WHERE usuario_id = 8 AND rol = 'MECANICO'",
    )
    assert otorgada_por == 1

    # El evento de seguridad quedó registrado con actor admin@example.com
    eventos = await _escalar(
        motor,
        "SELECT count(*) FROM evento_seguridad WHERE actor = 'admin@example.com' "
        "AND accion = 'Alta de usuario de personal'",
    )
    assert eventos == 1


async def test_alta_personal_hashea_fuera_de_transaccion(sembrada, client, monkeypatch):
    from fastapi import Depends
    from app.core.database import get_session
    from app.modules.usuarios import unit_of_work as uow_mod

    token_admin = await _login(client, ADMIN_CREDS)
    hashpw_real = bcrypt.hashpw
    en_transaccion_durante_hash = []

    uow_actual = {}
    orig_get_uow = uow_mod.get_usuario_uow

    async def _espia_uow(session=Depends(get_session)):
        inst = await orig_get_uow(session)
        uow_actual["uow"] = inst
        return inst

    def _espia_hashpw(password: bytes, salt: bytes) -> bytes:
        if "uow" in uow_actual:
            en_transaccion_durante_hash.append(uow_actual["uow"].session.in_transaction())
        return hashpw_real(password, salt)

    monkeypatch.setattr(bcrypt, "hashpw", _espia_hashpw)
    main.app.dependency_overrides[uow_mod.get_usuario_uow] = _espia_uow
    try:
        res = await client.post(
            "/usuarios",
            headers=_cookie(token_admin),
            json={
                "email": "mecanico_tx@example.com",
                "nombre": "Tx Test",
                "password": "Provisoria.2026",
                "rol": "MECANICO",
            },
        )
        assert res.status_code == 201
        assert en_transaccion_durante_hash == [False]
    finally:
        main.app.dependency_overrides.pop(uow_mod.get_usuario_uow, None)


async def test_alta_personal_correo_duplicado_409_sin_filas_sueltas(sembrada, client, motor):
    token_admin = await _login(client, ADMIN_CREDS)
    eventos_antes = await _escalar(motor, "SELECT count(*) FROM evento_seguridad")
    asignaciones_antes = await _escalar(motor, "SELECT count(*) FROM asignacion_rol")

    res = await client.post(
        "/usuarios",
        headers=_cookie(token_admin),
        json={
            "email": "recepcion@example.com",
            "nombre": "Otro",
            "password": "Provisoria.2026",
            "rol": "RECEPCION",
        },
    )
    assert res.status_code == 409
    assert "uq_" not in res.text.lower()
    assert await _escalar(motor, "SELECT count(*) FROM evento_seguridad") == eventos_antes
    assert await _escalar(motor, "SELECT count(*) FROM asignacion_rol") == asignaciones_antes


async def test_alta_personal_sin_rol_admin_403(sembrada, client):
    token_rec = await _login(client, RECEPCION_CREDS)
    res = await client.post(
        "/usuarios",
        headers=_cookie(token_rec),
        json={
            "email": "otro@example.com",
            "nombre": "Otro",
            "password": "Provisoria.2026",
            "rol": "MECANICO",
        },
    )
    assert res.status_code == 403


# --- GET /usuarios/{id}/roles -------------------------------------------------


async def test_listar_roles_usuario_existente_200_e_inexistente_404(sembrada, client):
    token_admin = await _login(client, ADMIN_CREDS)

    res = await client.get("/usuarios/3/roles", headers=_cookie(token_admin))
    assert res.status_code == 200
    roles = res.json()
    assert len(roles) == 1
    assert roles[0]["usuario_id"] == 3
    assert roles[0]["rol"] == "RECEPCION"
    assert roles[0]["revocada_en"] is None

    res_404 = await client.get("/usuarios/999/roles", headers=_cookie(token_admin))
    assert res_404.status_code == 404


# --- POST /usuarios/{id}/roles ------------------------------------------------


async def test_asignar_rol_con_y_sin_vencimiento_201_y_registra_evento(sembrada, client, motor):
    token_admin = await _login(client, ADMIN_CREDS)
    futuro = (ahora_utc() + timedelta(days=30)).isoformat()

    # Asignar RECEPCION a mecánico (usuario 4) con vencimiento futuro
    res = await client.post(
        "/usuarios/4/roles",
        headers=_cookie(token_admin),
        json={"rol": "RECEPCION", "vence_en": futuro},
    )
    assert res.status_code == 201
    cuerpo = res.json()
    assert cuerpo["usuario_id"] == 4
    assert cuerpo["rol"] == "RECEPCION"
    assert cuerpo["vence_en"] is not None
    assert cuerpo["revocada_en"] is None
    assert cuerpo["otorgada_por"] == 1

    eventos = await _escalar(
        motor,
        "SELECT count(*) FROM evento_seguridad WHERE actor = 'admin@example.com' "
        "AND accion = 'Asignación de rol'",
    )
    assert eventos == 1


@pytest.mark.parametrize(
    "vence_en",
    [
        "2030-05-01T10:00:00",  # sin zona horaria (naive)
        "2020-01-01T00:00:00Z",  # en el pasado
    ],
)
async def test_c07_asignar_rol_vencimiento_invalido_422_nunca_409(sembrada, client, vence_en):
    token_admin = await _login(client, ADMIN_CREDS)
    res = await client.post(
        "/usuarios/4/roles",
        headers=_cookie(token_admin),
        json={"rol": "RECEPCION", "vence_en": vence_en},
    )
    assert res.status_code == 422


async def test_asignar_rol_ya_vigente_409_y_usuario_inexistente_404(sembrada, client):
    token_admin = await _login(client, ADMIN_CREDS)

    # Usuario 3 ya tiene RECEPCION vigente
    res_409 = await client.post(
        "/usuarios/3/roles",
        headers=_cookie(token_admin),
        json={"rol": "RECEPCION"},
    )
    assert res_409.status_code == 409

    # Usuario inexistente -> 404
    res_404 = await client.post(
        "/usuarios/999/roles",
        headers=_cookie(token_admin),
        json={"rol": "RECEPCION"},
    )
    assert res_404.status_code == 404


async def test_reasignar_rol_previamente_vencido_cierra_el_anterior_y_crea_nuevo_201(
    sembrada, client, motor
):
    token_admin = await _login(client, ADMIN_CREDS)
    # Insertamos una asignación de RECEPCION ya vencida (revocada_en IS NULL) para usuario 4
    async with motor.begin() as c:
        await c.execute(
            text(
                "INSERT INTO asignacion_rol (usuario_id, rol, desde, vence_en) "
                "VALUES (4, 'RECEPCION', now() - interval '2 days', now() - interval '1 day')"
            )
        )

    res = await client.post(
        "/usuarios/4/roles",
        headers=_cookie(token_admin),
        json={"rol": "RECEPCION"},
    )
    assert res.status_code == 201

    # Ambas filas siguen en asignacion_rol (RN-03): la anterior cerrada y la nueva abierta
    res_roles = await client.get("/usuarios/4/roles", headers=_cookie(token_admin))
    roles_rec = [r for r in res_roles.json() if r["rol"] == "RECEPCION"]
    assert len(roles_rec) == 2
    assert roles_rec[0]["revocada_en"] is not None
    assert roles_rec[1]["revocada_en"] is None


# --- DELETE /usuarios/{id}/roles/{rol} (C-07 y C-08) --------------------------


async def test_c07_revocar_rol_con_sesion_abierta_quita_permiso_en_el_acto_y_conserva_fila(
    sembrada, client, motor
):
    token_admin = await _login(client, ADMIN_CREDS)
    token_rec = await _login(client, RECEPCION_CREDS)

    # Con sesión abierta, recepción puede ver clientes (200)
    assert (await client.get("/clientes/1", headers=_cookie(token_rec))).status_code == 200

    # Admin revoca el rol RECEPCION del usuario 3
    res_del = await client.delete("/usuarios/3/roles/RECEPCION", headers=_cookie(token_admin))
    assert res_del.status_code == 200
    assert res_del.json()["revocada_en"] is not None

    # En la petición siguiente, la MISMA cookie recibe 403 en /clientes/1
    assert (await client.get("/clientes/1", headers=_cookie(token_rec))).status_code == 403

    # /auth/yo muestra la diferencia entre roles_vigentes y roles_token
    yo = (await client.get("/auth/yo", headers=_cookie(token_rec))).json()
    assert yo["roles_vigentes"] == []
    assert yo["roles_token"] == ["RECEPCION"]

    # La fila revocada sigue en asignacion_rol (RN-03)
    roles_u3 = (await client.get("/usuarios/3/roles", headers=_cookie(token_admin))).json()
    assert len(roles_u3) == 1
    assert roles_u3[0]["rol"] == "RECEPCION"
    assert roles_u3[0]["revocada_en"] is not None

    # Quedó el evento de seguridad
    eventos = await _escalar(
        motor,
        "SELECT count(*) FROM evento_seguridad WHERE actor = 'admin@example.com' "
        "AND accion = 'Revocación de rol'",
    )
    assert eventos == 1


async def test_c08_autoproteccion_admin_no_se_revoca_a_si_mismo_ni_deja_sin_admins(
    sembrada, client, motor
):
    token_admin1 = await _login(client, ADMIN_CREDS)

    # 1. Admin 1 intenta revocar su propio ADMIN -> 409
    res_propio = await client.delete("/usuarios/1/roles/ADMIN", headers=_cookie(token_admin1))
    assert res_propio.status_code == 409

    # 2. Admin 1 revoca el ADMIN de Admin 2 (usuario 2) -> 200 (queda Admin 1 como único admin)
    res_otro = await client.delete("/usuarios/2/roles/ADMIN", headers=_cookie(token_admin1))
    assert res_otro.status_code == 200

    # 3. Si otro usuario tuviera ADMIN pero su cuenta estuviera inactiva, o si se intenta
    # dejar el sistema con 0 admins vigentes -> 409
    res_ultimo = await client.delete("/usuarios/1/roles/ADMIN", headers=_cookie(token_admin1))
    assert res_ultimo.status_code == 409


async def test_revocar_rol_no_vigente_o_usuario_inexistente_404(sembrada, client):
    token_admin = await _login(client, ADMIN_CREDS)

    # Usuario 3 no tiene rol MECANICO
    res_no_tiene = await client.delete("/usuarios/3/roles/MECANICO", headers=_cookie(token_admin))
    assert res_no_tiene.status_code == 404

    # Usuario inexistente
    res_inex = await client.delete("/usuarios/999/roles/RECEPCION", headers=_cookie(token_admin))
    assert res_inex.status_code == 404


# --- C-01: Parámetros de ruta inválidos en /usuarios/{id}/roles ---------------


@pytest.mark.parametrize(
    "metodo, ruta",
    [
        ("GET", "/usuarios/abc/roles"),
        ("GET", "/usuarios/0/roles"),
        ("GET", "/usuarios/3000000000/roles"),
        ("POST", "/usuarios/abc/roles"),
        ("DELETE", "/usuarios/abc/roles/RECEPCION"),
        ("DELETE", "/usuarios/3/roles/ROL_INEXISTENTE"),
    ],
)
async def test_c01_parametro_invalido_en_usuarios_roles_422_sin_ejecutar_servicio(
    sembrada, client, monkeypatch, metodo, ruta
):
    token_admin = await _login(client, ADMIN_CREDS)
    llamadas = []
    for nombre in ("listar_roles_usuario", "asignar_rol", "revocar_rol"):
        async def _espia(*args, _n=nombre, **kwargs):
            llamadas.append(_n)
            raise AssertionError("no debía ejecutarse")

        monkeypatch.setattr(service, nombre, _espia, raising=False)

    cuerpo = {"rol": "RECEPCION"} if metodo == "POST" else None
    res = await client.request(metodo, ruta, headers=_cookie(token_admin), json=cuerpo)
    assert res.status_code == 422
    assert llamadas == []


# --- GET /eventos (paginado) --------------------------------------------------


async def test_get_eventos_paginado_200_y_pagina_inexistente_422(sembrada, client):
    token_admin = await _login(client, ADMIN_CREDS)

    res = await client.get("/eventos?page=1&size=10", headers=_cookie(token_admin))
    assert res.status_code == 200
    cuerpo = res.json()
    assert set(cuerpo.keys()) == {"items", "total", "page", "size", "pages"}
    assert cuerpo["total"] >= 1
    assert cuerpo["page"] == 1
    assert cuerpo["size"] == 10
    assert cuerpo["pages"] == 1
    assert cuerpo["items"][0]["actor"] == "SISTEMA"
    assert cuerpo["items"][0]["accion"] == "Carga de los datos iniciales"

    # Página inexistente -> 422 con mensaje propio
    res_422 = await client.get("/eventos?page=2&size=10", headers=_cookie(token_admin))
    assert res_422.status_code == 422
    assert res_422.json() == {"detail": "La página 2 no existe: hay 1"}

    # size fuera de 1..100 -> 422
    assert (await client.get("/eventos?size=500", headers=_cookie(token_admin))).status_code == 422


async def test_get_eventos_sin_admin_403(sembrada, client):
    token_rec = await _login(client, RECEPCION_CREDS)
    assert (await client.get("/eventos", headers=_cookie(token_rec))).status_code == 403
