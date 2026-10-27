import asyncio
import math
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings
from app.core.database import ahora_utc
from app.core.security import crear_access_token, hashear_password, verificar_password
from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import AsignacionRol, IntentoAcceso, Usuario
from app.modules.usuarios.schemas import (
    ACCION_ALTA_CLIENTE,
    ACCION_CAMBIO_PASSWORD,
    CambiarPasswordRequest,
    LoginRequest,
    RegistroRequest,
    RegistroResponse,
    UsuarioYoResponse,
)
from app.modules.usuarios.unit_of_work import UsuarioUnitOfWork

# RN-08: 5 fallos del mismo (email, ip) dentro de 60 s bloquean el login.
MAX_FALLOS = 5
VENTANA_SEGUNDOS = 60


class EmailDuplicadoError(Exception):
    pass


class DocumentoDuplicadoError(Exception):
    pass


class CredencialesInvalidasError(Exception):
    pass


class PasswordActualIncorrectaError(Exception):
    pass


class LimiteIntentosError(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Demasiados intentos fallidos")
        self.retry_after = retry_after


async def registrar_cliente(
    datos: RegistroRequest,
    uow: UsuarioUnitOfWork,
    settings: Settings,
    semaforo: asyncio.Semaphore,
) -> RegistroResponse:
    # 1. bcrypt se calcula ANTES de abrir la transacción (regla 9)
    password_hash = await hashear_password(datos.password, settings, semaforo)

    try:
        async with uow:
            usuario = Usuario(
                email=datos.email,
                nombre=datos.nombre,
                password_hash=password_hash,
                activo=True,
                debe_cambiar_password=False,
            )
            await uow.usuarios.add(usuario)

            asignacion = AsignacionRol(
                usuario_id=usuario.id,  # type: ignore[arg-type]
                rol="CLIENTE",
            )
            await uow.asignaciones_rol.add(asignacion)

            cliente = Cliente(
                usuario_id=usuario.id,
                nombre=datos.nombre,
                documento=datos.documento,
                telefono=datos.telefono,
            )
            await uow.clientes.add(cliente)

            await uow.eventos_seguridad.registrar(
                actor=usuario.email,
                accion=ACCION_ALTA_CLIENTE,
            )
    except IntegrityError as exc:
        constraint = getattr(exc.orig, "constraint_name", None) or str(exc)
        if "uq_usuario_email" in constraint or "email" in constraint:
            raise EmailDuplicadoError("El correo electrónico ya está registrado") from exc
        if "uq_cliente_documento" in constraint or "documento" in constraint:
            raise DocumentoDuplicadoError(
                "El documento ya pertenece a un cliente registrado"
            ) from exc
        raise

    return RegistroResponse(
        id=usuario.id,  # type: ignore[arg-type]
        email=usuario.email,
        nombre=usuario.nombre,
        documento=cliente.documento,
        telefono=cliente.telefono,
        cliente_id=cliente.id,
    )


async def login(
    datos: LoginRequest,
    ip: str,
    uow: UsuarioUnitOfWork,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    semaforo: asyncio.Semaphore,
    hash_ficticio: bytes,
) -> tuple[Usuario, str]:
    """Orden estricto de la regla 11: límite de intentos → verificación → registro del intento.

    Devuelve (usuario, token). Lanza LimiteIntentosError (429) o CredencialesInvalidasError (401).
    """
    ahora = ahora_utc()

    # Paso 1 — límite de intentos (RN-08): una consulta, sin hash. Las lecturas van en
    # un bloque del UoW para que la conexión se libere antes de llamar a bcrypt (regla 9).
    async with uow:
        cantidad, primer_fallo = await uow.intentos_acceso.contar_fallos_vigentes_y_primer_fallo(
            datos.email, ip, ahora - timedelta(seconds=VENTANA_SEGUNDOS)
        )
        if cantidad >= MAX_FALLOS and primer_fallo is not None:
            restante = primer_fallo + timedelta(seconds=VENTANA_SEGUNDOS) - ahora
            raise LimiteIntentosError(max(1, math.ceil(restante.total_seconds())))
        usuario = await uow.usuarios.get_by_email(datos.email)

    # Paso 2 — verificación SIEMPRE con bcrypt (RN-09): contra el hash real si el usuario
    # existe y está activo, o contra el hash ficticio del lifespan. Mismo costo, mismo 401.
    if usuario is not None and usuario.activo:
        es_valido = await verificar_password(datos.password, usuario.password_hash, semaforo)
    else:
        await verificar_password(datos.password, hash_ficticio, semaforo)
        es_valido = False

    # Paso 3 — el intento se registra en una sesión y transacción PROPIAS (Ejercicio 7,
    # regla 11). Por qué: si se escribiera en la sesión de la petición, un 401 posterior
    # o cualquier error revertiría la fila y el límite de intentos nunca se activaría.
    # Costo: es una segunda conexión del pool por cada login y la fila queda confirmada
    # aunque la petición falle (es lo buscado, pero no participa del UoW de la petición).
    async with session_factory() as sesion_intento:
        async with UsuarioUnitOfWork(sesion_intento) as uow_intento:
            await uow_intento.intentos_acceso.add(
                IntentoAcceso(email=datos.email, ip=ip, exito=es_valido, cuando=ahora)
            )

    if not es_valido or usuario is None:
        raise CredencialesInvalidasError("Credenciales inválidas")

    # Paso 4 — token con los roles vigentes al emitirlo (informativos; el permiso real
    # se consulta en la base en cada petición).
    async with uow:
        roles = await uow.asignaciones_rol.listar_roles_vigentes(usuario.id)  # type: ignore[arg-type]
    token = crear_access_token(usuario.id, roles, settings)  # type: ignore[arg-type]
    return usuario, token


async def obtener_identidad(
    usuario: Usuario,
    roles_token: list[str],
    uow: UsuarioUnitOfWork,
) -> UsuarioYoResponse:
    async with uow:
        roles_vigentes = await uow.asignaciones_rol.listar_roles_vigentes(usuario.id)  # type: ignore[arg-type]
    return UsuarioYoResponse(
        id=usuario.id,  # type: ignore[arg-type]
        email=usuario.email,
        nombre=usuario.nombre,
        activo=usuario.activo,
        debe_cambiar_password=usuario.debe_cambiar_password,
        roles_vigentes=roles_vigentes,
        roles_token=roles_token,
    )


async def cambiar_password(
    usuario: Usuario,
    iat_token_actual: float,
    datos: CambiarPasswordRequest,
    uow: UsuarioUnitOfWork,
    settings: Settings,
    semaforo: asyncio.Semaphore,
) -> str:
    """Cambia la contraseña y devuelve un token nuevo, posterior al cambio (RN-07)."""
    usuario_id = usuario.id
    hash_actual = usuario.password_hash
    # get_usuario_actual leyó el usuario con la sesión de la petición y dejó abierta
    # una transacción de sólo lectura. Se cierra (no hay nada que confirmar) para que
    # bcrypt no corra con una conexión tomada (regla 9). Los valores necesarios ya se
    # copiaron arriba: el rollback expira las instancias.
    await uow.session.rollback()

    if not await verificar_password(datos.password_actual, hash_actual, semaforo):
        raise PasswordActualIncorrectaError("La contraseña actual es incorrecta")
    nuevo_hash = await hashear_password(datos.password_nueva, settings, semaforo)

    async with uow:
        # Estrictamente posterior al iat del token con el que se pidió el cambio, aunque
        # el reloj no haya avanzado (resolución del reloj de Windows): así esa cookie
        # cae de inmediato, sin sleep.
        instante_cambio = max(
            ahora_utc(),
            datetime.fromtimestamp(iat_token_actual, tz=timezone.utc) + timedelta(microseconds=1),
        )
        en_base = await uow.usuarios.get_by_id(usuario_id)
        if en_base is None:  # borrado entre la autenticación y el cambio
            raise CredencialesInvalidasError("Credenciales inválidas")
        await uow.usuarios.update(
            en_base,
            {
                "password_hash": nuevo_hash,
                "password_cambiada_en": instante_cambio,
                "debe_cambiar_password": False,
            },
        )
        await uow.eventos_seguridad.registrar(actor=en_base.email, accion=ACCION_CAMBIO_PASSWORD)

    async with uow:
        roles = await uow.asignaciones_rol.listar_roles_vigentes(usuario_id)  # type: ignore[arg-type]
    # iat = instante_cambio → iat >= password_cambiada_en: el token nuevo pasa.
    return crear_access_token(usuario_id, roles, settings, ahora=instante_cambio)  # type: ignore[arg-type]
