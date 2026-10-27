import asyncio
from datetime import datetime
from typing import Any

import bcrypt
import jwt

from app.core.config import Settings
from app.core.database import ahora_utc


class TokenInvalidoError(Exception):
    """Lanzada cuando un token JWT no se puede decodificar, está vencido o tiene firma errónea."""
    pass


async def hashear_password(
    password: str,
    settings: Settings,
    semaforo: asyncio.Semaphore,
) -> str:
    """Calcula el hash bcrypt de una contraseña en un hilo aparte y bajo semáforo (regla 9).

    Se llama a bcrypt a través del módulo bcrypt para permitir espiar/contar
    las llamadas en los tests.
    """
    password_bytes = password.encode("utf-8")
    async with semaforo:
        hash_bytes = await asyncio.to_thread(
            bcrypt.hashpw,
            password_bytes,
            bcrypt.gensalt(rounds=settings.BCRYPT_COST),
        )
    return hash_bytes.decode("utf-8")


async def verificar_password(
    password: str,
    password_hash: str | bytes,
    semaforo: asyncio.Semaphore,
) -> bool:
    """Verifica si la contraseña coincide con el hash, ejecutando bcrypt fuera del bucle.

    Acepta password_hash como str o bytes.
    """
    hash_bytes = (
        password_hash.encode("utf-8")
        if isinstance(password_hash, str)
        else password_hash
    )
    password_bytes = password.encode("utf-8")
    async with semaforo:
        return await asyncio.to_thread(
            bcrypt.checkpw,
            password_bytes,
            hash_bytes,
        )


def crear_access_token(
    usuario_id: int,
    roles: list[str],
    settings: Settings,
    ahora: datetime | None = None,
) -> str:
    """Emite un token JWT firmado con sub, iat fraccionario, exp y roles (regla 10).

    iat no se trunca a segundos: se almacena como float con fracciones de segundo
    para posibilitar la comparación exacta sin truncar con password_cambiada_en (RN-07).
    """
    instante = ahora or ahora_utc()
    iat = float(instante.timestamp())
    exp = iat + float(settings.ACCESS_TOKEN_EXPIRE_SECONDS)

    payload = {
        "sub": str(usuario_id),
        "iat": iat,
        "exp": exp,
        "roles": list(roles),
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )


def decodificar_access_token(
    token: str,
    settings: Settings,
) -> dict[str, Any]:
    """Decodifica y valida la firma y vigencia de un JWT.

    Lanza TokenInvalidoError si el token no es válido o está vencido.
    """
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenInvalidoError("Token vencido o expirado") from e
    except jwt.PyJWTError as e:
        raise TokenInvalidoError("Token inválido") from e
