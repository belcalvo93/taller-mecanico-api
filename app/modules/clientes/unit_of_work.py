"""Unit of Work del módulo clientes (CH-06).

Compone los repositorios que usa el módulo, todos con LA MISMA sesión. El router
lo construye con `get_clientes_uow` y se lo pasa al servicio sin abrirlo; el
servicio lo abre con `async with` y nunca lo construye (regla 14).
"""
from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.clientes.repository import ClienteRepository, VehiculoRepository


class ClientesUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.clientes = ClienteRepository(session)
        self.vehiculos = VehiculoRepository(session)


def get_clientes_uow(session: AsyncSession = Depends(get_session)) -> ClientesUnitOfWork:
    """Dependencia con la que el router construye el UoW (una sesión por petición)."""
    return ClientesUnitOfWork(session)
