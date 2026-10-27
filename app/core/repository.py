"""Repositorios genéricos (CH-03): el acceso a datos que heredan todos los módulos.

Convenciones (reglas 13 y 17 de CLAUDE.md):
- `BaseRepository[T]` recibe la sesión Y la clase del modelo: el parámetro de tipo
  no existe en tiempo de ejecución, así que la clase hay que pasarla.
- Las escrituras (`add`, `update`, `delete`) hacen `flush()`: la clave generada y los
  errores de restricción aparecen en el momento. NUNCA `commit()`: confirmar es
  exclusivo del Unit of Work.
- `get_by_id` usa `select` y no `session.get()`: `session.get` devuelve lo que haya
  en el identity map sin aplicar filtros, y el borrado lógico necesita que el filtro
  de `borrado_en` se aplique siempre.
- Precarga: los métodos genéricos no cargan relaciones. Un repositorio concreto declara
  `options(selectinload(...))` (colecciones) o `joinedload(...)` (muchos-a-uno)
  DENTRO del método que la usa, partiendo de `self._consulta_base()`. La carga
  perezosa está prohibida (los modelos usan `lazy="raise"`).
- `_paginar` recibe consultas de UNA fila por entidad: una colección con `joinedload`
  multiplicaría filas e inflaría el total, por eso las colecciones se precargan con
  `selectinload`. El total y los ítems salen de la MISMA consulta (mismos filtros).
- Los filtros se arman con `select()` y parámetros ligados, nunca concatenando SQL.
"""
from collections.abc import Mapping
from typing import Any, Generic, TypeVar

from sqlalchemy import func, inspect
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import SelectOfScalar

from app.core.database import ahora_utc
from app.core.paginacion import (
    Pagina,
    PaginaInexistente,
    ParametrosPagina,
    calcular_paginas,
)

T = TypeVar("T", bound=SQLModel)


class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, modelo: type[T]) -> None:
        mapeo = inspect(modelo)
        columnas_pk = mapeo.primary_key
        if len(columnas_pk) != 1:
            raise TypeError(f"{modelo.__name__} necesita una clave primaria simple")
        self.session = session
        self.modelo = modelo
        self._pk = getattr(modelo, mapeo.get_property_by_column(columnas_pk[0]).key)
        self._columnas = {a.key for a in mapeo.column_attrs}

    def _consulta_base(self) -> SelectOfScalar:
        """Punto de extensión: la consulta de la que parten todas las lecturas."""
        return select(self.modelo)

    async def get_by_id(self, id: Any) -> T | None:
        resultado = await self.session.exec(self._consulta_base().where(self._pk == id))
        return resultado.first()

    async def get_all(self, *, offset: int = 0, limit: int | None = None) -> list[T]:
        """Entidades en orden estable por clave primaria (sin orden el desplazamiento no es estable)."""
        consulta = self._consulta_base().order_by(self._pk).offset(offset)
        if limit is not None:
            consulta = consulta.limit(limit)
        return list((await self.session.exec(consulta)).all())

    async def count(self) -> int:
        return await self._contar(self._consulta_base())

    async def add(self, entidad: T) -> T:
        self.session.add(entidad)
        await self.session.flush()
        return entidad

    async def update(self, entidad: T, cambios: Mapping[str, Any] | None = None) -> T:
        """Aplica sólo las claves de `cambios` (p. ej. `model_dump(exclude_unset=True)` del PATCH).

        Una clave que no es columna del modelo es un error de programación: ValueError.
        Sin `cambios`, sólo sincroniza lo que el servicio ya modificó en la entidad.
        """
        desconocidas = sorted(set(cambios or {}) - self._columnas)
        if desconocidas:
            raise ValueError(
                f"{self.modelo.__name__} no tiene las columnas: {', '.join(desconocidas)}"
            )
        for campo, valor in (cambios or {}).items():
            setattr(entidad, campo, valor)
        self.session.add(entidad)
        await self.session.flush()
        return entidad

    async def delete(self, entidad: T) -> None:
        """Borrado físico. Hace flush para que una FK violada falle dentro del bloque."""
        await self.session.delete(entidad)
        await self.session.flush()

    async def _contar(self, consulta: SelectOfScalar) -> int:
        sub = consulta.order_by(None).subquery()
        return (await self.session.exec(select(func.count()).select_from(sub))).one()

    async def _paginar(self, consulta: SelectOfScalar, pagina: ParametrosPagina) -> Pagina[T]:
        """Una página de `consulta`; el total se cuenta con los mismos filtros que los ítems.

        Si la página pedida no existe lanza PaginaInexistente SIN pedir los ítems.
        """
        total = await self._contar(consulta)
        pages = calcular_paginas(total, pagina.size)
        if pagina.page > pages:
            raise PaginaInexistente(pagina.page, pages)
        if not consulta._order_by_clauses:
            consulta = consulta.order_by(self._pk)
        consulta = consulta.offset((pagina.page - 1) * pagina.size).limit(pagina.size)
        items = list((await self.session.exec(consulta)).all())
        return Pagina(items=items, total=total, page=pagina.page, size=pagina.size, pages=pages)


class SoftDeleteRepository(BaseRepository[T]):
    """Repositorio de modelos con borrado lógico (columna `borrado_en`).

    Lo usan vehículo y repuesto. Todas las lecturas heredadas (`get_by_id`, `get_all`,
    `count`, `_paginar`) parten de `_consulta_base()`, que excluye los dados de baja.
    `get_by_id_including_deleted` es para quien necesita ver también la baja, p. ej.
    terminar una orden con un repuesto dado de baja (DD-14).
    """

    def __init__(self, session: AsyncSession, modelo: type[T]) -> None:
        if "borrado_en" not in inspect(modelo).column_attrs:
            raise TypeError(
                f"{modelo.__name__} no tiene la columna borrado_en: no admite borrado lógico"
            )
        super().__init__(session, modelo)

    def _consulta_base(self) -> SelectOfScalar:
        return select(self.modelo).where(self.modelo.borrado_en.is_(None))

    async def get_by_id_including_deleted(self, id: Any) -> T | None:
        resultado = await self.session.exec(select(self.modelo).where(self._pk == id))
        return resultado.first()

    async def soft_delete(self, entidad: T) -> T:
        """Marca `borrado_en` con el instante actual (con zona). Una baja repetida conserva la primera fecha."""
        if entidad.borrado_en is None:
            entidad.borrado_en = ahora_utc()
        self.session.add(entidad)
        await self.session.flush()
        return entidad
