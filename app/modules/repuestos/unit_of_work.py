"""Unit of Work del módulo repuestos (CH-07).

Compone los tres repositorios con LA MISMA sesión. El router lo construye con
`get_repuestos_uow` y se lo pasa al servicio sin abrirlo; el servicio lo abre con
`async with` y nunca lo construye (regla 14).
"""
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.repuestos.repository import (
    HistorialPrecioRepository,
    MovimientoStockRepository,
    RepuestoRepository,
)


class RepuestosUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repuestos = RepuestoRepository(session)
        self.movimientos = MovimientoStockRepository(session)
        self.historial_precios = HistorialPrecioRepository(session)


def get_repuestos_uow(session: AsyncSession = Depends(get_session)) -> RepuestosUnitOfWork:
    """Dependencia con la que el router construye el UoW (una sesión por petición)."""
    return RepuestosUnitOfWork(session)
