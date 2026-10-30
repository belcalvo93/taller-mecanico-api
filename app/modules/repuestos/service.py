"""Reglas de negocio de repuestos y stock (CH-07).

Cada función recibe el Unit of Work ya construido por el router y lo abre con
`async with`; nunca lo construye ni confirma por su cuenta (regla 14). Lanza errores
de dominio: el router los traduce a HTTP.

El stock sólo se escribe con `uow.repuestos.mover_stock` (RN-14): acá no se asigna
`repuesto.stock` en ningún lado.

Unicidad del código (RN-01, regla 6): la garantiza la base. No se consulta antes; si el
INSERT choca, el UoW revierte al salir del bloque y recién ahí se mira QUÉ restricción
saltó, por su nombre (el texto del error no se devuelve al cliente, RN-18).
"""
from sqlalchemy.exc import IntegrityError

from app.core.paginacion import Pagina, ParametrosPagina
from app.modules.repuestos.models import HistorialPrecio, MovimientoStock, Repuesto
from app.modules.repuestos.schemas import ReposicionCrear, RepuestoActualizar, RepuestoCrear
from app.modules.repuestos.unit_of_work import RepuestosUnitOfWork

# Nombre fijado por la convención de CH-02.
UQ_CODIGO_VIGENTE = "uq_repuesto_codigo_vigente"


class RepuestoNoEncontrado(Exception):
    pass


class CodigoRepuestoDuplicado(Exception):
    pass


def _restriccion_violada(exc: IntegrityError) -> str | None:
    """Nombre de la restricción que informa PostgreSQL (asyncpg lo deja en la causa)."""
    causa = getattr(exc.orig, "__cause__", None)
    return getattr(causa, "constraint_name", None)


async def _vigente(uow: RepuestosUnitOfWork, repuesto_id: int) -> Repuesto:
    repuesto = await uow.repuestos.get_by_id(repuesto_id)  # excluye los dados de baja
    if repuesto is None:
        raise RepuestoNoEncontrado
    return repuesto


async def listar_repuestos(
    uow: RepuestosUnitOfWork, q: str | None, pagina: ParametrosPagina
) -> Pagina[Repuesto]:
    async with uow:
        return await uow.repuestos.listar(q, pagina)


async def obtener_repuesto(uow: RepuestosUnitOfWork, repuesto_id: int) -> Repuesto:
    async with uow:
        return await _vigente(uow, repuesto_id)


async def crear_repuesto(
    uow: RepuestosUnitOfWork, datos: RepuestoCrear, usuario_id: int
) -> Repuesto:
    try:
        async with uow:
            # nace con stock 0: la restricción de movimiento_stock prohíbe cantidad 0, y
            # el stock inicial entra por el mismo punto único que cualquier otro movimiento
            repuesto = await uow.repuestos.add(
                Repuesto(codigo=datos.codigo, descripcion=datos.descripcion, precio=datos.precio, stock=0)
            )
            if datos.stock_inicial > 0:
                await uow.repuestos.mover_stock(
                    repuesto, datos.stock_inicial, motivo="Stock inicial", usuario_id=usuario_id
                )
    except IntegrityError as exc:
        if _restriccion_violada(exc) == UQ_CODIGO_VIGENTE:
            raise CodigoRepuestoDuplicado from None
        raise
    return repuesto


async def actualizar_repuesto(
    uow: RepuestosUnitOfWork, repuesto_id: int, datos: RepuestoActualizar, usuario_id: int
) -> Repuesto:
    cambios = datos.model_dump(exclude_unset=True)
    async with uow:
        repuesto = await _vigente(uow, repuesto_id)
        precio_anterior = repuesto.precio
        await uow.repuestos.update(repuesto, cambios)
        # historial sólo si el precio cambió de verdad (RN-20); en la misma transacción
        if "precio" in cambios and cambios["precio"] != precio_anterior:
            await uow.historial_precios.add(
                HistorialPrecio(
                    repuesto_id=repuesto.id,
                    usuario_id=usuario_id,
                    precio_anterior=precio_anterior,
                    precio_nuevo=cambios["precio"],
                )
            )
    return repuesto


async def dar_de_baja_repuesto(uow: RepuestosUnitOfWork, repuesto_id: int) -> None:
    """Borrado lógico. Nunca da conflicto por órdenes abiertas (DD-14): terminarlas
    igual descuenta el stock de un repuesto dado de baja."""
    async with uow:
        await uow.repuestos.soft_delete(await _vigente(uow, repuesto_id))


async def reponer_stock(
    uow: RepuestosUnitOfWork, repuesto_id: int, datos: ReposicionCrear, usuario_id: int
) -> Repuesto:
    async with uow:
        repuesto = await _vigente(uow, repuesto_id)
        await uow.repuestos.mover_stock(
            repuesto, datos.cantidad, motivo=datos.motivo, usuario_id=usuario_id
        )
    return repuesto


async def listar_movimientos(uow: RepuestosUnitOfWork, repuesto_id: int) -> list[MovimientoStock]:
    async with uow:
        await _vigente(uow, repuesto_id)
        return await uow.movimientos.listar_por_repuesto(repuesto_id)


async def listar_precios(uow: RepuestosUnitOfWork, repuesto_id: int) -> list[HistorialPrecio]:
    async with uow:
        await _vigente(uow, repuesto_id)
        return await uow.historial_precios.listar_por_repuesto(repuesto_id)
