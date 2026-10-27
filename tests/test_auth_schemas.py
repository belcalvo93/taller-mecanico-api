import pytest
from pydantic import ValidationError


def test_schemas_extra_forbid():
    from app.modules.usuarios.schemas import (
        CambiarPasswordRequest,
        LoginRequest,
        RegistroRequest,
    )

    # RegistroRequest rechaza campos extras como 'rol' o 'activo'
    with pytest.raises(ValidationError) as exc:
        RegistroRequest(
            email="cliente@example.com",
            nombre="Cliente",
            password="Password.123",
            documento="30111222",
            telefono="11 4000-1111",
            rol="ADMIN",  # Campo no permitido
        )
    assert "extra_forbidden" in str(exc.value)

    # LoginRequest rechaza campos extras
    with pytest.raises(ValidationError) as exc:
        LoginRequest(
            email="cliente@example.com",
            password="Password.123",
            hack="true",
        )
    assert "extra_forbidden" in str(exc.value)

    # CambiarPasswordRequest rechaza campos extras
    with pytest.raises(ValidationError) as exc:
        CambiarPasswordRequest(
            password_actual="Actual.123",
            password_nueva="Nueva.123",
            otro="campo",
        )
    assert "extra_forbidden" in str(exc.value)


def test_schemas_limite_72_bytes():
    from app.modules.usuarios.schemas import (
        CambiarPasswordRequest,
        LoginRequest,
        RegistroRequest,
    )

    # 72 caracteres ASCII = 72 bytes -> Válido
    clave_72_bytes = "a" * 72
    req = RegistroRequest(
        email="cliente@example.com",
        nombre="Cliente",
        password=clave_72_bytes,
        documento="30111222",
        telefono="11 4000-1111",
    )
    assert req.password == clave_72_bytes

    # 73 caracteres ASCII = 73 bytes -> Inválido (422)
    clave_73_bytes = "a" * 73
    with pytest.raises(ValidationError):
        RegistroRequest(
            email="cliente@example.com",
            nombre="Cliente",
            password=clave_73_bytes,
            documento="30111222",
            telefono="11 4000-1111",
        )

    # 36 letras 'ñ' = 72 bytes en UTF-8 -> Válido
    clave_36_enes = "ñ" * 36
    assert len(clave_36_enes.encode("utf-8")) == 72
    req_ene = LoginRequest(
        email="cliente@example.com",
        password=clave_36_enes,
    )
    assert req_ene.password == clave_36_enes

    # 37 letras 'ñ' = 74 bytes en UTF-8 -> Inválido (422)
    clave_37_enes = "ñ" * 37
    assert len(clave_37_enes.encode("utf-8")) == 74
    with pytest.raises(ValidationError):
        LoginRequest(
            email="cliente@example.com",
            password=clave_37_enes,
        )

    # CambiarPasswordRequest también valida 72 bytes en ambas
    with pytest.raises(ValidationError):
        CambiarPasswordRequest(
            password_actual=clave_73_bytes,
            password_nueva="Valida.123",
        )
    with pytest.raises(ValidationError):
        CambiarPasswordRequest(
            password_actual="Valida.123",
            password_nueva=clave_73_bytes,
        )


def test_schemas_salida_sin_password_hash():
    from app.modules.usuarios.schemas import (
        LoginResponse,
        RegistroResponse,
        UsuarioYoResponse,
    )

    # Ningún esquema de respuesta contiene el campo password_hash
    assert "password_hash" not in RegistroResponse.model_fields
    assert "password_hash" not in LoginResponse.model_fields
    assert "password_hash" not in UsuarioYoResponse.model_fields

    # Verificación de serialización de LoginResponse (cuerpo del login de la consigna)
    login_res = LoginResponse(
        mensaje="Sesión iniciada",
        debe_cambiar_password=False,
        expira_en_segundos=1800,
    )
    assert login_res.model_dump() == {
        "mensaje": "Sesión iniciada",
        "debe_cambiar_password": False,
        "expira_en_segundos": 1800,
    }
