"""Unit of Work del módulo órdenes (CH-08).

Compone los repositorios del módulo con LA MISMA sesión. El router lo construye con
`get_ordenes_uow` y el servicio lo abre con `async with`; nunca lo construye (regla 14).
"""
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.core.repository import SoftDeleteRepository
from app.modules.clientes.repository import VehiculoRepository
from app.modules.ordenes.repository import (
    EstadoOrdenRepository,
    HistorialEstadoOrdenRepository,
    OrdenRepository,
)
from app.modules.repuestos.models import Repuesto
from app.modules.usuarios.repository import AsignacionRolRepository


class OrdenesUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.ordenes = OrdenRepository(session)
        self.historial = HistorialEstadoOrdenRepository(session)
        self.estados = EstadoOrdenRepository(session)
        self.vehiculos = VehiculoRepository(session)
        self.roles = AsignacionRolRepository(session)
        # PROVISORIO hasta que CH-07 mergee (design D2): el genérico ya ofrece lo que
        # usan crear (get_by_id) y terminar (get_by_id_including_deleted). Al llegar
        # CH-07 se cambia SOLO esta línea por RepuestoRepository(session).
        self.repuestos = SoftDeleteRepository(session, Repuesto)


def get_ordenes_uow(session: AsyncSession = Depends(get_session)) -> OrdenesUnitOfWork:
    """Dependencia con la que el router construye el UoW (una sesión por petición)."""
    return OrdenesUnitOfWork(session)
