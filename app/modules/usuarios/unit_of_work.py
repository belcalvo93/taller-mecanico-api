from fastapi import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session
from app.core.unit_of_work import UnitOfWork
from app.modules.clientes.repository import ClienteRepository
from app.modules.usuarios.repository import (
    AsignacionRolRepository,
    EventoSeguridadRepository,
    IntentoAccesoRepository,
    UsuarioRepository,
)


class UsuarioUnitOfWork(UnitOfWork):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.usuarios = UsuarioRepository(session)
        self.asignaciones_rol = AsignacionRolRepository(session)
        self.intentos_acceso = IntentoAccesoRepository(session)
        self.eventos_seguridad = EventoSeguridadRepository(session)
        self.clientes = ClienteRepository(session)


async def get_usuario_uow(
    session: AsyncSession = Depends(get_session),
) -> UsuarioUnitOfWork:
    return UsuarioUnitOfWork(session)
