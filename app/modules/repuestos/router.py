"""Rutas HTTP de repuestos y stock (CH-07). Van en el grupo PROTEGIDO de main.py.

El router construye el Unit of Work con `get_repuestos_uow`, se lo pasa al servicio
sin abrirlo y traduce los errores de dominio a HTTP con mensajes propios.
"""
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from app.core.dependencies import requiere_rol
from app.core.paginacion import Pagina, ParametrosPagina, parametros_pagina
from app.modules.repuestos import service
from app.modules.repuestos.schemas import (
    HistorialPrecioLeer,
    MovimientoStockLeer,
    ReposicionCrear,
    RepuestoActualizar,
    RepuestoCrear,
    RepuestoLeer,
)
from app.modules.repuestos.unit_of_work import RepuestosUnitOfWork, get_repuestos_uow
from app.modules.usuarios.models import Usuario

# Los ids son INTEGER: fuera de 1..2^31-1 asyncpg falla y sería un 500 (RN-18).
# No entero o fuera de rango -> 422 antes de ejecutar el handler (C-01).
IdRuta = Annotated[int, Path(ge=1, le=2_147_483_647)]
Uow = Annotated[RepuestosUnitOfWork, Depends(get_repuestos_uow)]
Pagina_ = Annotated[ParametrosPagina, Depends(parametros_pagina)]

CATALOGO = [Depends(requiere_rol("ADMIN", "RECEPCION", "MECANICO"))]
solo_admin = requiere_rol("ADMIN")
SOLO_ADMIN = [Depends(solo_admin)]

_ERRORES: dict[type[Exception], tuple[int, str]] = {
    service.RepuestoNoEncontrado: (status.HTTP_404_NOT_FOUND, "Repuesto no encontrado"),
    service.CodigoRepuestoDuplicado: (
        status.HTTP_409_CONFLICT,
        "Ya existe un repuesto vigente con ese código",
    ),
}


@contextmanager
def _traducir_errores() -> Iterator[None]:
    try:
        yield
    except tuple(_ERRORES) as exc:
        codigo, mensaje = _ERRORES[type(exc)]
        raise HTTPException(codigo, detail=mensaje) from None


def _respuestas(*codigos: int) -> dict[int | str, dict]:
    """Documenta en Swagger los códigos propios de cada ruta (401/403 incluidos)."""
    textos = {
        401: "Sin sesión", 403: "Sin un rol vigente que lo permita",
        404: "No existe", 409: "Choca con lo guardado",
    }
    return {c: {"description": textos[c]} for c in codigos}


router = APIRouter(prefix="/repuestos", tags=["repuestos y stock"])


@router.get(
    "",
    response_model=Pagina[RepuestoLeer],
    dependencies=CATALOGO,
    responses=_respuestas(401, 403),
)
async def listar_repuestos(
    uow: Uow,
    pagina: Pagina_,
    q: Annotated[str | None, Query(description="Texto a buscar en la descripción")] = None,
):
    return await service.listar_repuestos(uow, q, pagina)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=RepuestoLeer,
    responses=_respuestas(401, 403, 409),
)
async def alta_de_repuesto(datos: RepuestoCrear, uow: Uow, admin: Usuario = Depends(solo_admin)):
    with _traducir_errores():
        return await service.crear_repuesto(uow, datos, admin.id)


@router.get(
    "/{id}",
    response_model=RepuestoLeer,
    dependencies=CATALOGO,
    responses=_respuestas(401, 403, 404),
)
async def ver_repuesto(id: IdRuta, uow: Uow):
    with _traducir_errores():
        return await service.obtener_repuesto(uow, id)


@router.patch(
    "/{id}",
    response_model=RepuestoLeer,
    responses=_respuestas(401, 403, 404),
)
async def editar_repuesto(
    id: IdRuta, datos: RepuestoActualizar, uow: Uow, admin: Usuario = Depends(solo_admin)
):
    with _traducir_errores():
        return await service.actualizar_repuesto(uow, id, datos, admin.id)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=SOLO_ADMIN,
    responses=_respuestas(401, 403, 404),
)
async def baja_de_repuesto(id: IdRuta, uow: Uow):
    # Nunca 409 por órdenes abiertas: baja lógica (DD-14)
    with _traducir_errores():
        await service.dar_de_baja_repuesto(uow, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{id}/reponer",
    response_model=RepuestoLeer,
    responses=_respuestas(401, 403, 404),
)
async def reponer_repuesto(
    id: IdRuta, datos: ReposicionCrear, uow: Uow, admin: Usuario = Depends(solo_admin)
):
    with _traducir_errores():
        return await service.reponer_stock(uow, id, datos, admin.id)


@router.get(
    "/{id}/movimientos",
    response_model=list[MovimientoStockLeer],
    dependencies=SOLO_ADMIN,
    responses=_respuestas(401, 403, 404),
)
async def movimientos_de_stock(id: IdRuta, uow: Uow):
    with _traducir_errores():
        return await service.listar_movimientos(uow, id)


@router.get(
    "/{id}/precios",
    response_model=list[HistorialPrecioLeer],
    dependencies=SOLO_ADMIN,
    responses=_respuestas(401, 403, 404),
)
async def historial_de_precios(id: IdRuta, uow: Uow):
    with _traducir_errores():
        return await service.listar_precios(uow, id)
