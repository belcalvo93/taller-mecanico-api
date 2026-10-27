"""Repositorios del módulo clientes (CH-06).

Cada método se nombra por lo que trae y declara adentro su propia precarga:
la carga perezosa está prohibida (las relaciones tienen lazy="raise").
Ningún método confirma: el commit es del UnitOfWork (regla 13).
"""
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.repository import BaseRepository, SoftDeleteRepository
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.ordenes.models import EstadoOrden, OrdenTrabajo


class ClienteRepository(BaseRepository[Cliente]):
    """Repositorio de clientes, compartido entre usuarios y clientes (DD-13).

    La firma la fijó CH-04 (Hernán), que lo usa en el registro (RN-02); CH-06 lo
    extiende sin cambiarla.
    """

    def __init__(self, session: AsyncSession, model_cls: type[Cliente] = Cliente) -> None:
        super().__init__(session, model_cls)

    async def get_con_vehiculos_vigentes(self, id: int) -> Cliente | None:
        """El cliente con sus vehículos NO dados de baja, en dos consultas fijas
        (cliente + vehículos), sin importar cuántos vehículos tenga."""
        consulta = (
            self._consulta_base()
            .where(Cliente.id == id)
            .options(selectinload(Cliente.vehiculos.and_(col(Vehiculo.borrado_en).is_(None))))
        )
        return (await self.session.exec(consulta)).first()


class VehiculoRepository(SoftDeleteRepository[Vehiculo]):
    """Borrado lógico: get_by_id, get_all y count no ven los dados de baja, así
    que un vehículo dado de baja no se puede usar en órdenes nuevas (RN-16)."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Vehiculo)

    async def tiene_ordenes_abiertas(self, vehiculo_id: int) -> bool:
        """Abierta = en un estado que el CATÁLOGO marca como no final (es_final).
        Usa los modelos de CH-02; no depende del módulo ordenes (CH-08)."""
        abiertas = (
            select(OrdenTrabajo.id)
            .join(EstadoOrden, col(OrdenTrabajo.estado) == col(EstadoOrden.codigo))
            .where(OrdenTrabajo.vehiculo_id == vehiculo_id, col(EstadoOrden.es_final).is_(False))
            .exists()
        )
        return (await self.session.exec(select(abiertas))).one()

    async def listar_vigentes_de_usuario(self, usuario_id: int) -> list[Vehiculo]:
        """Los vehículos vigentes del cliente vinculado a `usuario_id` (RN-17):
        el filtro por dueño va en la consulta, nunca se trae de más."""
        consulta = (
            self._consulta_base()
            .join(Cliente, col(Vehiculo.cliente_id) == col(Cliente.id))
            .where(Cliente.usuario_id == usuario_id)
            .order_by(col(Vehiculo.id))
        )
        return list((await self.session.exec(consulta)).all())
