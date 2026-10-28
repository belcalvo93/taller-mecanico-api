"""Reglas de negocio de clientes y vehículos (CH-06).

Cada función recibe el Unit of Work ya construido por el router y lo abre con
`async with`; nunca lo construye ni confirma por su cuenta (regla 14). Lanza
errores de dominio: el router los traduce a HTTP.

Unicidad (RN-01, regla 6): la garantiza la base. No se consulta antes; si el
INSERT choca, el UoW revierte al salir del bloque y recién ahí se mira QUÉ
restricción saltó, por su nombre (nunca por el texto del error, que depende del
idioma del servidor y no se devuelve al cliente, RN-18).
"""
from sqlalchemy.exc import IntegrityError

from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.clientes.schemas import ClienteCrear, VehiculoCrear
from app.modules.clientes.unit_of_work import ClientesUnitOfWork

# Nombres fijados por la convención de CH-02 (design D3 de esquema-y-migraciones).
UQ_DOCUMENTO = "uq_cliente_documento"
UQ_PATENTE_VIGENTE = "uq_vehiculo_patente_vigente"


class ClienteNoEncontrado(Exception):
    pass


class VehiculoNoEncontrado(Exception):
    pass


class DocumentoDuplicado(Exception):
    pass


class PatenteDuplicada(Exception):
    pass


class VehiculoConOrdenesAbiertas(Exception):
    pass


def _restriccion_violada(exc: IntegrityError) -> str | None:
    """Nombre de la restricción que informa PostgreSQL (asyncpg lo deja en la causa)."""
    causa = getattr(exc.orig, "__cause__", None)
    return getattr(causa, "constraint_name", None)


async def crear_cliente(uow: ClientesUnitOfWork, datos: ClienteCrear) -> Cliente:
    try:
        async with uow:
            cliente = await uow.clientes.add(Cliente(**datos.model_dump()))
    except IntegrityError as exc:
        if _restriccion_violada(exc) == UQ_DOCUMENTO:
            raise DocumentoDuplicado from None
        raise
    return cliente


async def obtener_cliente(uow: ClientesUnitOfWork, cliente_id: int) -> Cliente:
    async with uow:
        cliente = await uow.clientes.get_con_vehiculos_vigentes(cliente_id)
    if cliente is None:
        raise ClienteNoEncontrado
    return cliente


async def crear_vehiculo(
    uow: ClientesUnitOfWork, cliente_id: int, datos: VehiculoCrear
) -> Vehiculo:
    try:
        async with uow:
            # 404 antes del INSERT (design D3): el índice único se evalúa antes que
            # la FK, y un cliente inexistente con patente repetida daría 409.
            if await uow.clientes.get_by_id(cliente_id) is None:
                raise ClienteNoEncontrado
            vehiculo = await uow.vehiculos.add(Vehiculo(cliente_id=cliente_id, **datos.model_dump()))
    except IntegrityError as exc:
        if _restriccion_violada(exc) == UQ_PATENTE_VIGENTE:
            raise PatenteDuplicada from None
        raise
    return vehiculo


async def dar_de_baja_vehiculo(uow: ClientesUnitOfWork, vehiculo_id: int) -> None:
    """Borrado lógico (RN-16): la fila y sus órdenes viejas se conservan."""
    async with uow:
        vehiculo = await uow.vehiculos.get_by_id(vehiculo_id)  # excluye los ya dados de baja
        if vehiculo is None:
            raise VehiculoNoEncontrado
        if await uow.vehiculos.tiene_ordenes_abiertas(vehiculo_id):
            raise VehiculoConOrdenesAbiertas
        await uow.vehiculos.soft_delete(vehiculo)


async def listar_mis_vehiculos(uow: ClientesUnitOfWork, usuario_id: int) -> list[Vehiculo]:
    """Lo propio (RN-17): los vehículos vigentes del cliente vinculado al usuario."""
    async with uow:
        return await uow.vehiculos.listar_vigentes_de_usuario(usuario_id)
