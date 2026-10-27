from sqlmodel.ext.asyncio.session import AsyncSession


class UnitOfWork:
    """Unit of Work base como gestor de contexto asincrónico (regla 14).

    Confirma al salir del bloque sin excepción (commit), revierte si sale con
    excepción (rollback), y NO cierra la sesión (no la creó).
    Único lugar del sistema donde se confirma la transacción.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            await self.rollback()
        else:
            await self.commit()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()
