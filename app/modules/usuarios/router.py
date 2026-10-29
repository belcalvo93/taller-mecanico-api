from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status

from app.core.dependencies import get_usuario_actual, requiere_rol
from app.core.paginacion import Pagina, ParametrosPagina, parametros_pagina
from app.core.security import decodificar_access_token
from app.modules.usuarios import service
from app.modules.usuarios.models import Usuario
from app.modules.usuarios.schemas import (
    AltaPersonalRequest,
    AsignacionRolResponse,
    AsignarRolRequest,
    CambiarPasswordRequest,
    EventoSeguridadResponse,
    LoginRequest,
    LoginResponse,
    MensajeResponse,
    RegistroRequest,
    RegistroResponse,
    RolValido,
    UsuarioPersonalResponse,
    UsuarioYoResponse,
)
from app.modules.usuarios.unit_of_work import UsuarioUnitOfWork, get_usuario_uow

router = APIRouter(prefix="/auth", tags=["auth"])
usuarios_router = APIRouter(tags=["usuarios y roles"])

COOKIE = "access_token"
IdRuta = Annotated[int, Path(ge=1, le=2_147_483_647)]
RolRuta = Annotated[RolValido, Path()]


def _poner_cookie(response: Response, token: str, request: Request) -> None:
    """El token viaja SÓLO en esta cookie (regla 10): nunca en el cuerpo."""
    settings = request.app.state.settings
    response.set_cookie(
        key=COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
        secure=settings.COOKIE_SECURE,
        path="/",
    )


@router.post(
    "/registro",
    response_model=RegistroResponse,
    status_code=status.HTTP_201_CREATED,
)
async def registro(
    datos: RegistroRequest,
    request: Request,
    uow: UsuarioUnitOfWork = Depends(get_usuario_uow),
) -> RegistroResponse:
    settings = request.app.state.settings
    semaforo = request.app.state.bcrypt_semaforo

    try:
        return await service.registrar_cliente(datos, uow, settings, semaforo)
    except service.EmailDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except service.DocumentoDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post("/login", response_model=LoginResponse)
async def login(
    datos: LoginRequest,
    request: Request,
    response: Response,
    uow: UsuarioUnitOfWork = Depends(get_usuario_uow),
) -> LoginResponse:
    estado = request.app.state
    ip = request.client.host if request.client else "desconocida"
    try:
        usuario, token = await service.login(
            datos,
            ip,
            uow,
            estado.session_factory,
            estado.settings,
            estado.bcrypt_semaforo,
            estado.hash_ficticio,
        )
    except service.LimiteIntentosError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos fallidos. Intentá de nuevo más tarde",
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc
    except service.CredencialesInvalidasError as exc:
        # Mismo código y mismo cuerpo exista o no el correo (RN-09).
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        ) from exc

    _poner_cookie(response, token, request)
    return LoginResponse(
        mensaje="Sesión iniciada",
        debe_cambiar_password=usuario.debe_cambiar_password,
        expira_en_segundos=estado.settings.ACCESS_TOKEN_EXPIRE_SECONDS,
    )


@router.post("/logout", response_model=MensajeResponse)
async def logout(request: Request, response: Response) -> MensajeResponse:
    settings = request.app.state.settings
    response.delete_cookie(
        key=COOKIE,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        path="/",
    )
    return MensajeResponse(mensaje="Sesión cerrada")


@router.get("/yo", response_model=UsuarioYoResponse)
async def yo(
    request: Request,
    usuario: Usuario = Depends(get_usuario_actual),
    uow: UsuarioUnitOfWork = Depends(get_usuario_uow),
) -> UsuarioYoResponse:
    # get_usuario_actual ya validó la cookie: decodificarla de nuevo no puede fallar.
    payload = decodificar_access_token(request.cookies[COOKIE], request.app.state.settings)
    return await service.obtener_identidad(usuario, list(payload.get("roles", [])), uow)


@router.post("/cambiar-password", response_model=MensajeResponse)
async def cambiar_password(
    datos: CambiarPasswordRequest,
    request: Request,
    response: Response,
    usuario: Usuario = Depends(get_usuario_actual),
    uow: UsuarioUnitOfWork = Depends(get_usuario_uow),
) -> MensajeResponse:
    estado = request.app.state
    payload = decodificar_access_token(request.cookies[COOKIE], estado.settings)
    try:
        token = await service.cambiar_password(
            usuario,
            float(payload["iat"]),
            datos,
            uow,
            estado.settings,
            estado.bcrypt_semaforo,
        )
    except (service.PasswordActualIncorrectaError, service.CredencialesInvalidasError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc

    _poner_cookie(response, token, request)
    return MensajeResponse(mensaje="Contraseña actualizada")


# --- CH-05: Rutas protegidas de administración de usuarios, roles y eventos ---


@usuarios_router.post(
    "/usuarios",
    response_model=UsuarioPersonalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def alta_personal(
    datos: AltaPersonalRequest,
    request: Request,
    admin: Usuario = Depends(requiere_rol("ADMIN")),
    uow: UsuarioUnitOfWork = Depends(get_usuario_uow),
) -> UsuarioPersonalResponse:
    estado = request.app.state
    try:
        return await service.crear_personal(
            admin, datos, uow, estado.settings, estado.bcrypt_semaforo
        )
    except service.EmailDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@usuarios_router.get(
    "/usuarios/{id}/roles",
    response_model=list[AsignacionRolResponse],
)
async def ver_roles_usuario(
    id: IdRuta,
    _admin: Usuario = Depends(requiere_rol("ADMIN")),
    uow: UsuarioUnitOfWork = Depends(get_usuario_uow),
) -> list[AsignacionRolResponse]:
    try:
        return await service.listar_roles_usuario(id, uow)
    except service.UsuarioNoEncontradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@usuarios_router.post(
    "/usuarios/{id}/roles",
    response_model=AsignacionRolResponse,
    status_code=status.HTTP_201_CREATED,
)
async def asignar_rol_usuario(
    id: IdRuta,
    datos: AsignarRolRequest,
    admin: Usuario = Depends(requiere_rol("ADMIN")),
    uow: UsuarioUnitOfWork = Depends(get_usuario_uow),
) -> AsignacionRolResponse:
    try:
        return await service.asignar_rol(admin, id, datos, uow)
    except service.UsuarioNoEncontradoError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except service.RolYaVigenteError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@usuarios_router.delete(
    "/usuarios/{id}/roles/{rol}",
    response_model=AsignacionRolResponse,
)
async def revocar_rol_usuario(
    id: IdRuta,
    rol: RolRuta,
    admin: Usuario = Depends(requiere_rol("ADMIN")),
    uow: UsuarioUnitOfWork = Depends(get_usuario_uow),
) -> AsignacionRolResponse:
    try:
        return await service.revocar_rol(admin, id, rol, uow)
    except (service.UsuarioNoEncontradoError, service.RolNoEncontradoError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except service.AutoproteccionAdminError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@usuarios_router.get(
    "/eventos",
    response_model=Pagina[EventoSeguridadResponse],
)
async def listar_eventos(
    pagina: ParametrosPagina = Depends(parametros_pagina),
    _admin: Usuario = Depends(requiere_rol("ADMIN")),
    uow: UsuarioUnitOfWork = Depends(get_usuario_uow),
) -> Pagina[EventoSeguridadResponse]:
    return await service.listar_eventos_seguridad(pagina, uow)
