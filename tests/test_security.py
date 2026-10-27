import asyncio
from datetime import datetime, timezone
import pytest
from app.core.config import Settings
from app.core.database import ahora_utc


def test_import_security_fails_before_implementation():
    """ROJO: verifica que app.core.security se pueda importar."""
    from app.core.security import (
        TokenInvalidoError,
        crear_access_token,
        decodificar_access_token,
        hashear_password,
        verificar_password,
    )
    assert TokenInvalidoError is not None
    assert callable(hashear_password)
    assert callable(verificar_password)
    assert callable(crear_access_token)
    assert callable(decodificar_access_token)


@pytest.mark.asyncio
async def test_hashear_y_verificar_password():
    from app.core.security import hashear_password, verificar_password

    settings = Settings(
        POSTGRES_USER="taller",
        POSTGRES_PASSWORD="secretpassword",
        POSTGRES_DB="taller",
        JWT_SECRET_KEY="supersecretkeythatisatleast32characterslong!",
        BCRYPT_COST=4,  # Rápido para test
        BCRYPT_MAX_CONCURRENT=2,
    )
    semaforo = asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENT)

    password = "MiPassword.123"
    hash_str = await hashear_password(password, settings, semaforo)

    assert isinstance(hash_str, str)
    assert hash_str.startswith("$2b$04$")

    # Verificación correcta
    valido = await verificar_password(password, hash_str, semaforo)
    assert valido is True

    # Verificación con bytes
    valido_bytes = await verificar_password(password, hash_str.encode("utf-8"), semaforo)
    assert valido_bytes is True

    # Verificación errónea
    invalido = await verificar_password("OtraPassword", hash_str, semaforo)
    assert invalido is False


@pytest.mark.asyncio
async def test_bcrypt_respeta_semaforo_concurrencia(monkeypatch):
    import bcrypt
    from app.core.security import hashear_password

    settings = Settings(
        POSTGRES_USER="taller",
        POSTGRES_PASSWORD="secretpassword",
        POSTGRES_DB="taller",
        JWT_SECRET_KEY="supersecretkeythatisatleast32characterslong!",
        BCRYPT_COST=4,
        BCRYPT_MAX_CONCURRENT=2,
    )
    semaforo = asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENT)

    concurrencia_actual = 0
    max_concurrencia_observada = 0

    original_hashpw = bcrypt.hashpw

    def mock_hashpw(password, salt):
        nonlocal concurrencia_actual, max_concurrencia_observada
        concurrencia_actual += 1
        if concurrencia_actual > max_concurrencia_observada:
            max_concurrencia_observada = concurrencia_actual
        # simular trabajo
        res = original_hashpw(password, salt)
        concurrencia_actual -= 1
        return res

    monkeypatch.setattr(bcrypt, "hashpw", mock_hashpw)

    # Lanzar 6 hashes a la vez con semáforo de 2
    tasks = [hashear_password(f"clave_{i}", settings, semaforo) for i in range(6)]
    resultados = await asyncio.gather(*tasks)

    assert len(resultados) == 6
    assert max_concurrencia_observada <= 2


def test_crear_y_decodificar_access_token():
    from app.core.security import (
        TokenInvalidoError,
        crear_access_token,
        decodificar_access_token,
    )

    settings = Settings(
        POSTGRES_USER="taller",
        POSTGRES_PASSWORD="secretpassword",
        POSTGRES_DB="taller",
        JWT_SECRET_KEY="supersecretkeythatisatleast32characterslong!",
        ACCESS_TOKEN_EXPIRE_SECONDS=1800,
    )

    ahora = ahora_utc()
    token = crear_access_token(
        usuario_id=42,
        roles=["ADMIN", "MECANICO"],
        settings=settings,
        ahora=ahora,
    )
    assert isinstance(token, str)

    payload = decodificar_access_token(token, settings)
    assert payload["sub"] == "42"
    assert payload["roles"] == ["ADMIN", "MECANICO"]
    # iat debe preservar fracciones de segundo (float)
    assert isinstance(payload["iat"], float)
    assert abs(payload["iat"] - ahora.timestamp()) < 1e-4
    assert abs(payload["exp"] - (ahora.timestamp() + 1800)) < 1e-4


def test_decodificar_token_vencido_falla():
    from app.core.security import (
        TokenInvalidoError,
        crear_access_token,
        decodificar_access_token,
    )

    settings = Settings(
        POSTGRES_USER="taller",
        POSTGRES_PASSWORD="secretpassword",
        POSTGRES_DB="taller",
        JWT_SECRET_KEY="supersecretkeythatisatleast32characterslong!",
        ACCESS_TOKEN_EXPIRE_SECONDS=60,
    )

    pasado = datetime(2020, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    token = crear_access_token(
        usuario_id=1,
        roles=["CLIENTE"],
        settings=settings,
        ahora=pasado,
    )

    with pytest.raises(TokenInvalidoError) as exc_info:
        decodificar_access_token(token, settings)

    assert "vencido" in str(exc_info.value).lower() or "expirado" in str(exc_info.value).lower()


def test_decodificar_token_firma_invalida_falla():
    from app.core.security import (
        TokenInvalidoError,
        crear_access_token,
        decodificar_access_token,
    )

    settings_1 = Settings(
        POSTGRES_USER="taller",
        POSTGRES_PASSWORD="secretpassword",
        POSTGRES_DB="taller",
        JWT_SECRET_KEY="supersecretkeythatisatleast32characterslong!",
    )
    settings_2 = Settings(
        POSTGRES_USER="taller",
        POSTGRES_PASSWORD="secretpassword",
        POSTGRES_DB="taller",
        JWT_SECRET_KEY="anotherdifferentsecretkeythatis32charslong!",
    )

    token = crear_access_token(
        usuario_id=1,
        roles=["CLIENTE"],
        settings=settings_1,
    )

    with pytest.raises(TokenInvalidoError):
        decodificar_access_token(token, settings_2)
