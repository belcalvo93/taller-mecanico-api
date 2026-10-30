"""Reglas de negocio de órdenes de trabajo (CH-08).

Cada función recibe el Unit of Work ya construido por el router y lo abre con
`async with`; nunca lo construye ni confirma por su cuenta (regla 14). Lanza
errores de dominio: el router los traduce a HTTP con mensajes propios.
"""
import asyncio
import logging
from decimal import Decimal

from sqlalchemy.exc import IntegrityError

from app.core.paginacion import Pagina, ParametrosPagina
from app.modules.ordenes.models import EstadoOrden, HistorialEstadoOrden, ItemOrden, OrdenTrabajo
from app.modules.ordenes.schemas import (
    EstadoOrdenCodigo,
    OrdenCrear,
    OrdenDetalle,
    OrdenResumen,
    armar_detalle,
    armar_resumen,
)
from app.modules.ordenes.unit_of_work import OrdenesUnitOfWork
from app.modules.repuestos.repository import StockInsuficiente as StockInsuficienteRepuesto

# Quienes ven cualquier orden (RN-17): el resto sólo ve las de sus vehículos.
ROLES_DE_PERSONAL = frozenset({"RECEPCION", "ADMIN", "MECANICO"})

# Restricción de la base que es la segunda línea de defensa del stock (design D4).
CK_STOCK_NO_NEGATIVO = "ck_repuesto_stock_no_negativo"

logger = logging.getLogger("taller.avisos")
if logger.level == logging.NOTSET:
    logger.setLevel(logging.INFO)
if not logger.handlers:
    # uvicorn no configura el logger raíz: sin esto el aviso no se vería en la consola.
    # `propagate` queda activo para que caplog lo capture en los tests (design D11).
    logger.addHandler(logging.StreamHandler())

# Máximo de NUMERIC(12,2): más allá el INSERT daría un error numérico (500, RN-18).
TOTAL_MAXIMO = Decimal("9999999999.99")


class OrdenNoEncontrada(Exception):
    pass


class SinPermisoSobreOrden(Exception):
    pass


class TransicionInvalida(Exception):
    """La orden no está en un estado desde el cual se pueda hacer la acción."""

    def __init__(self, estado: str, accion: str) -> None:
        self.mensaje = f"La orden está en {estado}: no se puede {accion}"
        super().__init__(self.mensaje)


class CatalogoVacio(Exception):
    pass


class VehiculoNoDisponible(Exception):
    pass


class RepuestoNoDisponible(Exception):
    pass


class TotalExcedido(Exception):
    pass


class StockInsuficiente(Exception):
    """No alcanza el stock de algún ítem: terminar no escribe nada (C-11)."""

    def __init__(self, codigo: str | None = None) -> None:
        self.mensaje = (
            f"No hay stock suficiente de {codigo}" if codigo else "No hay stock suficiente"
        )
        super().__init__(self.mensaje)


def _restriccion_violada(exc: IntegrityError) -> str | None:
    causa = getattr(exc, "orig", None)
    causa = getattr(causa, "__cause__", None) or causa
    return getattr(causa, "constraint_name", None)


async def listar_estados(uow: OrdenesUnitOfWork) -> list[EstadoOrden]:
    async with uow:
        return await uow.estados.listar_por_posicion()


async def _detalle(uow: OrdenesUnitOfWork, orden_id: int) -> OrdenDetalle:
    """Segundo bloque, ya confirmado el primero: la orden recién escrita, releída con
    la precarga fija del detalle."""
    async with uow:
        orden = await uow.ordenes.get_detalle(orden_id)
    if orden is None:
        raise OrdenNoEncontrada
    return armar_detalle(orden)


async def crear_orden(uow: OrdenesUnitOfWork, usuario_id: int, datos: OrdenCrear) -> OrdenDetalle:
    """RN-10, RN-16 y RN-19 en UN solo bloque: orden, ítems e historial se confirman
    juntos o no se escribe nada (cualquier excepción revierte)."""
    async with uow:
        # 1. Sin catálogo no hay nada que validar (RN-19).
        if await uow.estados.get(EstadoOrdenCodigo.PENDIENTE) is None:
            raise CatalogoVacio
        # 2. Vehículo vigente (RN-16): inexistente y dado de baja dan lo mismo.
        if await uow.vehiculos.get_by_id(datos.vehiculo_id) is None:
            raise VehiculoNoDisponible
        # 3. Repuestos vigentes (RN-16). No es una consulta previa de unicidad: un
        #    repuesto dado de baja no violaría ninguna FK, hay que mirarlo.
        items: list[ItemOrden] = []
        total = Decimal("0.00")
        for pedido in datos.items:
            repuesto = await uow.repuestos.get_by_id(pedido.repuesto_id)
            if repuesto is None:
                raise RepuestoNoDisponible
            # El precio se COPIA al ítem: la orden no sigue al repuesto (RN-10).
            items.append(ItemOrden(
                repuesto_id=repuesto.id, cantidad=pedido.cantidad, precio_unitario=repuesto.precio,
            ))
            total += pedido.cantidad * repuesto.precio
        # 4. El total lo calcula el servidor, en decimal exacto.
        if total > TOTAL_MAXIMO:
            raise TotalExcedido
        # 5. Escritura.
        orden = OrdenTrabajo(
            vehiculo_id=datos.vehiculo_id, estado=EstadoOrdenCodigo.PENDIENTE.value,
            falla=datos.falla, total=total, items=items,
        )
        await uow.ordenes.add(orden)
        await uow.historial.add(HistorialEstadoOrden(
            orden_id=orden.id, desde_estado=None,
            hasta_estado=EstadoOrdenCodigo.PENDIENTE.value, usuario_id=usuario_id,
        ))
        orden_id = orden.id
    return await _detalle(uow, orden_id)


async def obtener_detalle(uow: OrdenesUnitOfWork, usuario_id: int, orden_id: int) -> OrdenDetalle:
    """404 antes que 403 (una orden inexistente no tiene relación con nadie). Lo ve el
    personal vigente o el dueño del vehículo (RN-17)."""
    async with uow:
        orden = await uow.ordenes.get_detalle(orden_id)
        if orden is None:
            raise OrdenNoEncontrada
        roles = await uow.roles.listar_roles_vigentes(usuario_id)
        es_personal = bool(ROLES_DE_PERSONAL.intersection(roles))
        if not es_personal and orden.vehiculo.cliente.usuario_id != usuario_id:
            raise SinPermisoSobreOrden
        return armar_detalle(orden)


def _pagina_de_resumenes(pagina: Pagina[OrdenTrabajo]) -> Pagina[OrdenResumen]:
    return Pagina[OrdenResumen](
        items=[armar_resumen(o) for o in pagina.items],
        total=pagina.total, page=pagina.page, size=pagina.size, pages=pagina.pages,
    )


async def listar_ordenes(
    uow: OrdenesUnitOfWork, estado: EstadoOrdenCodigo | None, pagina: ParametrosPagina
) -> Pagina[OrdenResumen]:
    async with uow:
        encontradas = await uow.ordenes.listar(estado.value if estado else None, pagina)
        return _pagina_de_resumenes(encontradas)


async def listar_mis_ordenes(
    uow: OrdenesUnitOfWork, usuario_id: int, pagina: ParametrosPagina
) -> Pagina[OrdenResumen]:
    """Lo propio (RN-17): el filtro por dueño va en la consulta, nunca se trae de más."""
    async with uow:
        encontradas = await uow.ordenes.listar_de_usuario(usuario_id, pagina)
        return _pagina_de_resumenes(encontradas)


async def _orden_para_transicion(uow: OrdenesUnitOfWork, orden_id: int) -> OrdenTrabajo:
    """Dentro del bloque: la orden bloqueada, o 404 (antes que cualquier 403)."""
    orden = await uow.ordenes.get_para_transicion(orden_id)
    if orden is None:
        raise OrdenNoEncontrada
    return orden


async def _pasar_a(
    uow: OrdenesUnitOfWork, orden: OrdenTrabajo, nuevo: EstadoOrdenCodigo, usuario_id: int
) -> None:
    """Cambia el estado y agrega EXACTAMENTE una línea de historial (RN-15)."""
    anterior = orden.estado
    orden.estado = nuevo.value
    await uow.ordenes.update(orden)
    await uow.historial.add(HistorialEstadoOrden(
        orden_id=orden.id, desde_estado=anterior, hasta_estado=nuevo.value, usuario_id=usuario_id,
    ))


async def iniciar_orden(uow: OrdenesUnitOfWork, usuario_id: int, orden_id: int) -> OrdenDetalle:
    """RN-11: PENDIENTE → EN_REPARACION y queda asignada al mecánico que la inicia.
    El rol MECANICO lo exige la ruta (SU-03)."""
    async with uow:
        orden = await _orden_para_transicion(uow, orden_id)
        if orden.estado != EstadoOrdenCodigo.PENDIENTE:
            raise TransicionInvalida(orden.estado, "iniciar")
        orden.mecanico_id = usuario_id
        await _pasar_a(uow, orden, EstadoOrdenCodigo.EN_REPARACION, usuario_id)
    return await _detalle(uow, orden_id)


async def cancelar_orden(uow: OrdenesUnitOfWork, usuario_id: int, orden_id: int) -> OrdenDetalle:
    """RN-12: PENDIENTE → CANCELADA. Permiso ANTES que estado (403 antes que 409):
    RECEPCION o ADMIN vigentes, o el dueño del vehículo (RN-17)."""
    async with uow:
        orden = await _orden_para_transicion(uow, orden_id)
        roles = set(await uow.roles.listar_roles_vigentes(usuario_id))
        es_dueno = orden.vehiculo.cliente.usuario_id == usuario_id
        if not (roles & {"RECEPCION", "ADMIN"}) and not es_dueno:
            raise SinPermisoSobreOrden
        if orden.estado != EstadoOrdenCodigo.PENDIENTE:
            raise TransicionInvalida(orden.estado, "cancelar")
        await _pasar_a(uow, orden, EstadoOrdenCodigo.CANCELADA, usuario_id)
    return await _detalle(uow, orden_id)


async def terminar_orden(uow: OrdenesUnitOfWork, usuario_id: int, orden_id: int) -> OrdenDetalle:
    """RN-11, RN-13, RN-14: EN_REPARACION → TERMINADA descontando stock, todo en UN
    solo bloque (RN-13). Permiso (mecánico asignado o ADMIN) ANTES que estado.

    Si algún ítem no tiene stock, el bloque revierte entero: estado, stock, movimientos
    e historial quedan como estaban (C-11). Los errores de stock se traducen FUERA del
    bloque, ya con la transacción deshecha."""
    try:
        async with uow:
            orden = await _orden_para_transicion(uow, orden_id)
            roles = await uow.roles.listar_roles_vigentes(usuario_id)
            if "ADMIN" not in roles and orden.mecanico_id != usuario_id:
                raise SinPermisoSobreOrden
            if orden.estado != EstadoOrdenCodigo.EN_REPARACION:
                raise TransicionInvalida(orden.estado, "terminar")
            # Por repuesto_id: dos terminaciones simultáneas toman los bloqueos de fila
            # en el mismo orden (design D6). Un movimiento por ítem, por el único punto
            # de escritura de stock (RN-14). Con repuestos dados de baja también (DD-14).
            for item in sorted(orden.items, key=lambda i: i.repuesto_id):
                repuesto = await uow.repuestos.get_by_id_including_deleted(item.repuesto_id)
                await uow.repuestos.mover_stock(
                    repuesto, -item.cantidad, motivo=f"Orden {orden.id} terminada",
                    usuario_id=usuario_id, orden_id=orden.id,
                )
            await _pasar_a(uow, orden, EstadoOrdenCodigo.TERMINADA, usuario_id)
    except StockInsuficienteRepuesto as exc:
        raise StockInsuficiente(exc.codigo) from None
    except IntegrityError as exc:
        # Segunda línea de defensa: el CHECK de la base frenó lo que el control en
        # Python no vio (por nombre de restricción, como CH-06). Nada de texto de la base.
        if _restriccion_violada(exc) == CK_STOCK_NO_NEGATIVO:
            raise StockInsuficiente from None
        raise
    return await _detalle(uow, orden_id)


async def avisar_cliente(orden_id: int, cliente: str, patente: str) -> None:
    """Aviso simulado al cliente (design D11). Corre DESPUÉS de enviada la respuesta
    (BackgroundTasks) y sólo si terminar confirmó: nunca demora ni rompe la respuesta."""
    await asyncio.sleep(0.5)
    logger.info("Aviso a %s: su vehículo %s (orden %s) está listo para retirar", cliente, patente, orden_id)
