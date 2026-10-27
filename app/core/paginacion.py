"""Paginación común de todos los listados (CH-03).

- Parámetros `page` (>= 1, por defecto 1) y `size` (1..100, por defecto 20),
  validados por el contrato: FastAPI responde 422 sin ejecutar el listado.
- Envoltorio `Pagina[T]` con exactamente `items`, `total`, `page`, `size`, `pages`.
- `pages` vale al menos 1: con cero resultados hay una página, vacía. Por eso
  pedir `page=2` sin resultados es una página inexistente ("hay 1").
- `PaginaInexistente` la lanza el repositorio; `responder_pagina_inexistente` la
  traduce a 422 `{"detail": "La página 3 no existe: hay 2"}` y se registra una vez
  en `main.py`, para que ningún listado termine en 500 por esto.
"""
from math import ceil
from typing import Generic, TypeVar

from fastapi import Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

T = TypeVar("T")


def calcular_paginas(total: int, size: int) -> int:
    """Páginas necesarias para `total` elementos, redondeando hacia arriba, con mínimo 1."""
    return max(1, ceil(total / size))


class PaginaInexistente(Exception):
    """Se pidió una página mayor que la cantidad de páginas que hay."""

    def __init__(self, page: int, pages: int) -> None:
        self.page = page
        self.pages = pages
        self.mensaje = f"La página {page} no existe: hay {pages}"
        super().__init__(self.mensaje)


class ParametrosPagina(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)


def parametros_pagina(
    page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)
) -> ParametrosPagina:
    """Dependencia de los listados: `Depends(parametros_pagina)`."""
    return ParametrosPagina(page=page, size=size)


class Pagina(BaseModel, Generic[T]):
    """Respuesta estándar de los listados."""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


async def responder_pagina_inexistente(request: Request, exc: PaginaInexistente) -> JSONResponse:
    """Manejador de `PaginaInexistente`: 422 con mensaje propio, sin traza."""
    return JSONResponse(status_code=422, content={"detail": exc.mensaje})
