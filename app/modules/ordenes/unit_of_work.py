"""Unit of Work del módulo órdenes (CH-08).

Compone los repositorios del módulo con LA MISMA sesión. El router lo construye con
`get_ordenes_uow` y el servicio lo abre con `async with`; nunca lo construye (regla 14).
"""
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.clientes.repository import VehiculoRepository
from app.modules.ordenes.repository import (
    EstadoOrdenRepository,
    HistorialEstadoOrdenRepository,
    OrdenRepository,
)
from app.modules.repuestos.repository import RepuestoRepository
from app.modules.usuarios.repository import AsignacionRolRepository


class OrdenesUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.ordenes = OrdenRepository(session)
        self.historial = HistorialEstadoOrdenRepository(session)
        self.estados = EstadoOrdenRepository(session)
        self.vehiculos = VehiculoRepository(session)
        self.roles = AsignacionRolRepository(session)
        # crear usa get_by_id; terminar usa get_by_id_including_deleted y mover_stock (CH-07).
        self.repuestos = RepuestoRepository(session)


def get_ordenes_uow(session: AsyncSession = Depends(get_session)) -> OrdenesUnitOfWork:
    """Dependencia con la que el router construye el UoW (una sesión por petición)."""
    return OrdenesUnitOfWork(session)
