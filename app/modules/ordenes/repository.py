"""Repositorios del módulo órdenes (CH-08).

Cada método declara adentro su propia precarga: la carga perezosa está prohibida
(las relaciones tienen lazy="raise"). Ningún método confirma: el commit es del
UnitOfWork (regla 13).
"""
from sqlalchemy.orm import contains_eager, joinedload, selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.paginacion import Pagina, ParametrosPagina
from app.core.repository import BaseRepository
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import EstadoOrden, HistorialEstadoOrden, ItemOrden, OrdenTrabajo
from app.modules.repuestos.models import Repuesto


class EstadoOrdenRepository:
    """Catálogo de estados: SÓLO LECTURA (RN-19, AP-02).

    No hereda de BaseRepository (su PK es `codigo`, no `id`) y no ofrece `add`,
    `update` ni `delete`: desde la API el catálogo no se escribe, lo llena seed.py.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def listar_por_posicion(self) -> list[EstadoOrden]:
        consulta = select(EstadoOrden).order_by(col(EstadoOrden.posicion))
        return list((await self.session.exec(consulta)).all())

    async def get(self, codigo: str) -> EstadoOrden | None:
        consulta = select(EstadoOrden).where(EstadoOrden.codigo == codigo)
        return (await self.session.exec(consulta)).first()


class HistorialEstadoOrdenRepository(BaseRepository[HistorialEstadoOrden]):
    """Sólo agrega: la tabla es de sólo agregado (RN-15, trigger de la migración 2)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, HistorialEstadoOrden)


class OrdenRepository(BaseRepository[OrdenTrabajo]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrdenTrabajo)

    async def get_detalle(self, id: int) -> OrdenTrabajo | None:
        """La orden con vehículo, cliente, ítems, repuesto de cada ítem e historial en
        3 SELECT fijos (orden+vehículo+cliente; ítems+repuestos; historial), sin
        importar cuántos ítems o líneas tenga (C-15).

        `populate_existing`: tras una transición la orden ya está en el identity map
        (expire_on_commit=False) con colecciones viejas; sin esto el detalle saldría
        desactualizado o tocaría una relación lazy="raise".
        """
        consulta = (
            self._consulta_base()
            .where(OrdenTrabajo.id == id)
            .options(
                joinedload(OrdenTrabajo.vehiculo).joinedload(Vehiculo.cliente),
                selectinload(OrdenTrabajo.items).joinedload(ItemOrden.repuesto),
                selectinload(OrdenTrabajo.historial),
            )
            .execution_options(populate_existing=True)
        )
        return (await self.session.exec(consulta)).first()

    async def get_para_transicion(self, id: int) -> OrdenTrabajo | None:
        """La orden BLOQUEADA (FOR UPDATE) con vehículo→cliente (para saber el dueño)
        e ítems (para terminar). El bloqueo evita que dos peticiones simultáneas hagan
        la misma transición y dupliquen el historial. `of=` porque PostgreSQL no admite
        FOR UPDATE sobre el lado nulo de un outer join."""
        consulta = (
            self._consulta_base()
            .where(OrdenTrabajo.id == id)
            .options(
                joinedload(OrdenTrabajo.vehiculo).joinedload(Vehiculo.cliente),
                selectinload(OrdenTrabajo.items),
            )
            .with_for_update(of=OrdenTrabajo)
            .execution_options(populate_existing=True)
        )
        return (await self.session.exec(consulta)).first()

    async def bloquear_repuestos(self, ids: list[int]) -> dict[int, Repuesto]:
        """Los repuestos dados BLOQUEADOS (FOR UPDATE), en orden ascendente de id, con los
        valores frescos de la base (`populate_existing`). Incluye los dados de baja (DD-14).
        Sin este bloqueo dos órdenes que comparten repuesto leerían el mismo stock y una
        descontaría de más o pisaría a la otra (lost update). Orden fijo de bloqueo: evita
        interbloqueos entre terminaciones simultáneas (design D6). Sólo lectura: la
        escritura del stock sigue siendo de `mover_stock` (RN-14)."""
        if not ids:
            return {}
        consulta = (
            select(Repuesto)
            .where(col(Repuesto.id).in_(ids))
            .order_by(col(Repuesto.id))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return {r.id: r for r in (await self.session.exec(consulta)).all()}

    async def listar(self, estado: str | None, pagina: ParametrosPagina) -> Pagina[OrdenTrabajo]:
        """Listado del personal por id. joinedload de muchos-a-uno: una fila por orden,
        no infla el total de `_paginar`. El filtro es un parámetro ligado."""
        consulta = self._consulta_base().options(
            joinedload(OrdenTrabajo.vehiculo).joinedload(Vehiculo.cliente)
        )
        if estado is not None:
            consulta = consulta.where(OrdenTrabajo.estado == estado)
        return await self._paginar(consulta.order_by(col(OrdenTrabajo.id)), pagina)

    async def listar_de_usuario(
        self, usuario_id: int, pagina: ParametrosPagina
    ) -> Pagina[OrdenTrabajo]:
        """Las órdenes de los vehículos del cliente vinculado al usuario (RN-17). Incluye
        las de vehículos dados de baja: son historia del cliente. Sin ficha → vacía."""
        consulta = (
            self._consulta_base()
            .join(Vehiculo, col(OrdenTrabajo.vehiculo_id) == col(Vehiculo.id))
            .join(Cliente, col(Vehiculo.cliente_id) == col(Cliente.id))
            .where(Cliente.usuario_id == usuario_id)
            .options(contains_eager(OrdenTrabajo.vehiculo).contains_eager(Vehiculo.cliente))
            .order_by(col(OrdenTrabajo.id))
        )
        return await self._paginar(consulta, pagina)
