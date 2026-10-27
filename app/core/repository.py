from typing import Any, Generic, Sequence, TypeVar

from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import ahora_utc

T = TypeVar("T", bound=SQLModel)


class BaseRepository(Generic[T]):
    """Repositorio base genérico para acceso a datos (regla 13).

    Recibe en su constructor la sesión y la clase del modelo.
    add y update hacen flush(), NUNCA commit().
    """

    def __init__(self, session: AsyncSession, model_cls: type[T]) -> None:
        self.session = session
        self.model_cls = model_cls

    async def get_by_id(self, id_: Any) -> T | None:
        return await self.session.get(self.model_cls, id_)

    async def get_all(self, offset: int = 0, limit: int = 100) -> Sequence[T]:
        statement = select(self.model_cls).offset(offset).limit(limit)
        result = await self.session.exec(statement)
        return result.all()

    async def count(self) -> int:
        statement = select(func.count()).select_from(self.model_cls)
        result = await self.session.exec(statement)
        return result.one() or 0

    async def add(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def update(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()


class SoftDeleteRepository(BaseRepository[T]):
    """Repositorio con filtrado automático de borrado lógico por 'borrado_en'."""

    async def get_by_id(self, id_: Any) -> T | None:
        statement = select(self.model_cls).where(
            self.model_cls.id == id_,  # type: ignore[attr-defined]
            self.model_cls.borrado_en.is_(None),  # type: ignore[attr-defined]
        )
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_id_including_deleted(self, id_: Any) -> T | None:
        return await super().get_by_id(id_)

    async def soft_delete(self, entity: T) -> T:
        entity.borrado_en = ahora_utc()  # type: ignore[attr-defined]
        return await self.update(entity)
