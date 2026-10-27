import asyncio

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings
from app.core.security import hashear_password
from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import AsignacionRol, Usuario
from app.modules.usuarios.schemas import (
    ACCION_ALTA_CLIENTE,
    RegistroRequest,
    RegistroResponse,
)
from app.modules.usuarios.unit_of_work import UsuarioUnitOfWork


class EmailDuplicadoError(Exception):
    pass


class DocumentoDuplicadoError(Exception):
    pass


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
