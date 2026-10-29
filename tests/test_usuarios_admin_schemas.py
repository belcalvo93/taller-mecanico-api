"""CH-05 (Grupo 2): Tests unitarios de contratos para alta de personal, asignación de roles y eventos."""
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.core.database import ahora_utc
from app.modules.usuarios.schemas import (
    AltaPersonalRequest,
    AsignacionRolResponse,
    AsignarRolRequest,
    EventoSeguridadResponse,
    UsuarioPersonalResponse,
)


def test_alta_personal_request_valido():
    req = AltaPersonalRequest(
        email="personal@example.com",
        nombre="Pedro Personal",
        password="ClaveProvisoria123",
        rol="MECANICO",
    )
    assert req.email == "personal@example.com"
    assert req.nombre == "Pedro Personal"
    assert req.rol == "MECANICO"


def test_alta_personal_request_rechaza_campos_extra():
    with pytest.raises(ValidationError):
        AltaPersonalRequest(
            email="personal@example.com",
            nombre="Pedro Personal",
            password="ClaveProvisoria123",
            rol="MECANICO",
            debe_cambiar_password=False,  # type: ignore[call-arg]
        )


def test_alta_personal_request_rechaza_password_mayor_a_72_bytes():
    with pytest.raises(ValidationError):
        AltaPersonalRequest(
            email="personal@example.com",
            nombre="Pedro Personal",
            password="ñ" * 37,  # 74 bytes UTF-8
            rol="MECANICO",
        )


def test_alta_personal_request_rechaza_rol_invalido():
    with pytest.raises(ValidationError):
        AltaPersonalRequest(
            email="personal@example.com",
            nombre="Pedro Personal",
            password="ClaveProvisoria123",
            rol="SUPERADMIN",  # type: ignore[arg-type]
        )


def test_alta_personal_request_rechaza_nombre_con_nul_o_vacio():
    with pytest.raises(ValidationError):
        AltaPersonalRequest(
            email="personal@example.com",
            nombre="Pedro\x00Personal",
            password="ClaveProvisoria123",
            rol="MECANICO",
        )
    with pytest.raises(ValidationError):
        AltaPersonalRequest(
            email="personal@example.com",
            nombre="   ",
            password="ClaveProvisoria123",
            rol="MECANICO",
        )


def test_asignar_rol_request_sin_vencimiento_y_con_vencimiento_futuro_con_tz():
    req1 = AsignarRolRequest(rol="RECEPCION")
    assert req1.rol == "RECEPCION"
    assert req1.vence_en is None

    futuro = ahora_utc() + timedelta(days=7)
    req2 = AsignarRolRequest(rol="RECEPCION", vence_en=futuro)
    assert req2.vence_en == futuro


def test_asignar_rol_request_rechaza_vencimiento_sin_zona_horaria():
    # C-07: vencimiento sin zona horaria (naive) -> 422 (ValidationError)
    with pytest.raises(ValidationError) as exc_info:
        AsignarRolRequest(
            rol="RECEPCION",
            vence_en="2030-01-01T00:00:00",  # type: ignore[arg-type]
        )
    assert "zona horaria" in str(exc_info.value).lower()


def test_asignar_rol_request_rechaza_vencimiento_en_el_pasado():
    # C-07: vencimiento en el pasado -> 422 (ValidationError)
    pasado = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValidationError) as exc_info:
        AsignarRolRequest(rol="RECEPCION", vence_en=pasado)
    assert "futuro" in str(exc_info.value).lower() or "pasado" in str(exc_info.value).lower()


def test_asignar_rol_request_rechaza_rol_invalido_y_extra():
    with pytest.raises(ValidationError):
        AsignarRolRequest(rol="JEFE")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        AsignarRolRequest(rol="ADMIN", otorgada_por=1)  # type: ignore[call-arg]


def test_contratos_de_salida_no_exponen_password_hash():
    resp = UsuarioPersonalResponse(
        id=10,
        email="personal@example.com",
        nombre="Pedro",
        activo=True,
        debe_cambiar_password=True,
        rol="MECANICO",
    )
    assert "password_hash" not in resp.model_dump()

    ahora = ahora_utc()
    asig = AsignacionRolResponse(
        id=1,
        usuario_id=10,
        rol="MECANICO",
        desde=ahora,
        vence_en=None,
        revocada_en=None,
        otorgada_por=1,
    )
    assert asig.rol == "MECANICO"

    ev = EventoSeguridadResponse(
        id=1,
        cuando=ahora,
        actor="admin@example.com",
        accion="Alta de usuario de personal",
    )
    assert ev.actor == "admin@example.com"
