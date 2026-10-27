from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import ahora_utc, get_session
from app.core.security import TokenInvalidoError, decodificar_access_token
from app.modules.usuarios.models import AsignacionRol, Usuario


async def get_usuario_actual(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Usuario:
    """Devuelve el usuario autenticado a partir de la cookie access_token (regla 10).

    Lee únicamente la cookie 'access_token', nunca la cabecera Authorization (C-03).
    Responde 401 si:
    - No hay cookie access_token.
    - El token es inválido o expiró.
    - El usuario no existe o está inactivo.
    - El token fue emitido antes del último cambio de contraseña (RN-07, sin truncar).
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=401,
            detail="No autenticado: cookie access_token no provista",
        )

    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()

    try:
        payload = decodificar_access_token(token, settings)
    except TokenInvalidoError as exc:
        raise HTTPException(
            status_code=401,
            detail="No autenticado: token inválido o expirado",
        ) from exc

    try:
        usuario_id = int(payload.get("sub", 0))
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status_code=401,
            detail="No autenticado: claim sub inválido",
        ) from exc

    usuario = await session.get(Usuario, usuario_id)
    if not usuario or not usuario.activo:
        raise HTTPException(
            status_code=401,
            detail="No autenticado: usuario inexistente o inactivo",
        )

    if usuario.password_cambiada_en is not None:
        iat = float(payload.get("iat", 0.0))
        if iat < usuario.password_cambiada_en.timestamp():
            raise HTTPException(
                status_code=401,
                detail="No autenticado: sesión revocada por cambio de contraseña",
            )

    return usuario


def requiere_rol(*roles: str) -> Callable[..., Awaitable[Usuario]]:
    """Fábrica de dependencias de autorización por rol (regla 12, RN-04).

    Consulta los roles vigentes en la base de datos en cada petición
    (no revocados y sin vencer). Los roles en el JWT son sólo informativos.
    Si el usuario no tiene al menos uno de los roles indicados, responde 403.
    """
    roles_esperados = set(roles)

    async def _verificar_rol(
        usuario: Usuario = Depends(get_usuario_actual),
        session: AsyncSession = Depends(get_session),
    ) -> Usuario:
        ahora = ahora_utc()
        statement = select(AsignacionRol.rol).where(
            AsignacionRol.usuario_id == usuario.id,
            AsignacionRol.revocada_en.is_(None),
            (AsignacionRol.vence_en.is_(None) | (AsignacionRol.vence_en > ahora)),
        )
        resultado = await session.exec(statement)
        # Compatible tanto con AsyncSession de SQLModel como con dobles de prueba
        if hasattr(resultado, "scalars"):
            escalares = resultado.scalars()
            roles_vigentes = set(escalares.all() if hasattr(escalares, "all") else escalares)
        elif hasattr(resultado, "all"):
            roles_vigentes = set(resultado.all())
        else:
            roles_vigentes = set(resultado)

        if not roles_esperados.intersection(roles_vigentes):
            raise HTTPException(
                status_code=403,
                detail="Sin permiso: rol insuficiente",
            )

        return usuario

    return _verificar_rol
