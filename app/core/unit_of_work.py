"""Unit of Work base (CH-03): el único lugar que confirma o revierte una transacción.

Patrón para un UoW concreto de módulo (el router lo construye, el servicio lo abre):

    class ClientesUoW(UnitOfWork):
        def __init__(self, session):
            super().__init__(session)
            self.clientes = ClienteRepository(session)
            self.vehiculos = VehiculoRepository(session)

    # router.py: dependencia que lo construye con la sesión de la petición
    def get_clientes_uow(session: AsyncSession = Depends(get_session)) -> ClientesUoW:
        return ClientesUoW(session)

    # service.py: lo recibe SIN abrir y lo abre con `async with`; nunca lo construye
    async def crear_vehiculo(uow: ClientesUoW, datos):
        async with uow:
            ...

Reglas:
- Salir del bloque sin excepción confirma; con excepción revierte y la deja pasar.
  No hay `commit()` público: confirmar es salir del bloque, así una operación
  (RN-02, RN-13, RN-20) se confirma toda junta o no se confirma.
- NUNCA cierra la sesión: la creó `get_session` y es quien la cierra.
- Si un servicio captura una excepción dentro del bloque y sigue, el UoW confirma
  lo que haya: es decisión explícita del servicio.
- Abrir el mismo UoW dos veces seguidas es válido (cada bloque, una transacción);
  anidarlo no está soportado.
"""
from typing import Self

from sqlmodel.ext.asyncio.session import AsyncSession


class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, tipo, excepcion, traza) -> None:
        if excepcion is not None:
            await self.session.rollback()
            return
        try:
            await self.session.commit()
        except BaseException:
            await self.session.rollback()
            raise
