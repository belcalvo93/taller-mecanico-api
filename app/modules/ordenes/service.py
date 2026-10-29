"""Reglas de negocio de órdenes de trabajo (CH-08).

Cada función recibe el Unit of Work ya construido por el router y lo abre con
`async with`; nunca lo construye ni confirma por su cuenta (regla 14). Lanza
errores de dominio: el router los traduce a HTTP con mensajes propios.
"""
from decimal import Decimal

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

# Quienes ven cualquier orden (RN-17): el resto sólo ve las de sus vehículos.
ROLES_DE_PERSONAL = frozenset({"RECEPCION", "ADMIN", "MECANICO"})

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
    """RN-11, RN-13, RN-14: EN_REPARACION → TERMINADA descontando stock, todo en un
    solo bloque. Permiso (mecánico asignado o ADMIN) ANTES que estado."""
    async with uow:
        orden = await _orden_para_transicion(uow, orden_id)
        roles = await uow.roles.listar_roles_vigentes(usuario_id)
        if "ADMIN" not in roles and orden.mecanico_id != usuario_id:
            raise SinPermisoSobreOrden
        if orden.estado != EstadoOrdenCodigo.EN_REPARACION:
            raise TransicionInvalida(orden.estado, "terminar")
        # CH-07: acá va el descuento de stock por el punto único de escritura
        # (design D4), un movimiento por ítem, ordenado por repuesto_id. Hasta que
        # CH-07 esté en main esto NO puede terminar la orden sin descontar: falla
        # (el bloque revierte) en vez de dejar una orden TERMINADA sin stock.
        raise NotImplementedError("CH-07: falta el punto único de escritura de stock")
        await _pasar_a(uow, orden, EstadoOrdenCodigo.TERMINADA, usuario_id)  # pragma: no cover
    return await _detalle(uow, orden_id)
