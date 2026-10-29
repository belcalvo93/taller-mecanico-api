"""Rutas HTTP de órdenes de trabajo y del catálogo de estados (CH-08).
Van en el grupo PROTEGIDO de main.py.

El router construye el Unit of Work con `get_ordenes_uow`, se lo pasa al servicio
sin abrirlo y traduce los errores de dominio a HTTP con mensajes propios (nunca
texto de la base).
"""
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.core.dependencies import get_usuario_actual, requiere_rol
from app.core.paginacion import Pagina, ParametrosPagina, parametros_pagina
from app.modules.ordenes import service
from app.modules.ordenes.schemas import (
    EstadoOrdenCodigo,
    EstadoOrdenLeer,
    OrdenCrear,
    OrdenDetalle,
    OrdenResumen,
)
from app.modules.ordenes.unit_of_work import OrdenesUnitOfWork, get_ordenes_uow
from app.modules.usuarios.models import Usuario

# Los ids son INTEGER: fuera de 1..2^31-1 asyncpg falla y sería un 500 (RN-18).
# No entero o fuera de rango → 422 antes de ejecutar el handler (C-01).
IdRuta = Annotated[int, Path(ge=1, le=2_147_483_647)]
Uow = Annotated[OrdenesUnitOfWork, Depends(get_ordenes_uow)]

_ERRORES: dict[type[Exception], tuple[int, str]] = {
    service.OrdenNoEncontrada: (status.HTTP_404_NOT_FOUND, "Orden no encontrada"),
    service.SinPermisoSobreOrden: (
        status.HTTP_403_FORBIDDEN, "Sin permiso sobre esta orden",
    ),
    service.TransicionInvalida: (status.HTTP_409_CONFLICT, "Transición no permitida"),
    service.CatalogoVacio: (
        status.HTTP_409_CONFLICT,
        "El catálogo de estados está vacío: cargue los datos iniciales",
    ),
    service.VehiculoNoDisponible: (
        status.HTTP_409_CONFLICT, "El vehículo no existe o fue dado de baja",
    ),
    service.RepuestoNoDisponible: (
        status.HTTP_409_CONFLICT, "Algún repuesto no existe o fue dado de baja",
    ),
    service.TotalExcedido: (
        status.HTTP_409_CONFLICT, "El total de la orden supera el máximo permitido",
    ),
}


@contextmanager
def _traducir_errores() -> Iterator[None]:
    try:
        yield
    except tuple(_ERRORES) as exc:
        codigo, mensaje = _ERRORES[type(exc)]
        # Algunos errores arman su propio texto (p. ej. el estado en que está la orden).
        raise HTTPException(codigo, detail=getattr(exc, "mensaje", None) or mensaje) from None


def _respuestas(*codigos: int) -> dict[int | str, dict]:
    """Documenta en Swagger los códigos propios de cada ruta (401/403 incluidos)."""
    textos = {
        401: "Sin sesión", 403: "Sin permiso", 404: "No existe", 409: "Choca con lo guardado",
    }
    return {c: {"description": textos[c]} for c in codigos}


router = APIRouter(tags=["órdenes de trabajo"])


@router.get(
    "/estados-orden",
    response_model=list[EstadoOrdenLeer],
    dependencies=[Depends(get_usuario_actual)],
    responses=_respuestas(401),
)
async def listar_estados_orden(uow: Uow):
    """Catálogo de sólo lectura, por posición. Sólo pide estar autenticado."""
    return await service.listar_estados(uow)


@router.post(
    "/ordenes",
    status_code=status.HTTP_201_CREATED,
    response_model=OrdenDetalle,
    responses=_respuestas(401, 403, 409),
)
async def alta_de_orden(
    datos: OrdenCrear,
    uow: Uow,
    usuario: Usuario = Depends(requiere_rol("RECEPCION", "ADMIN")),
):
    with _traducir_errores():
        return await service.crear_orden(uow, usuario.id, datos)


@router.get(
    "/ordenes",
    response_model=Pagina[OrdenResumen],
    dependencies=[Depends(requiere_rol("RECEPCION", "ADMIN", "MECANICO"))],
    responses=_respuestas(401, 403),
)
async def listar_ordenes(
    uow: Uow,
    pagina: Annotated[ParametrosPagina, Depends(parametros_pagina)],
    estado: Annotated[EstadoOrdenCodigo | None, Query()] = None,
):
    return await service.listar_ordenes(uow, estado, pagina)


@router.get("/mis-ordenes", response_model=Pagina[OrdenResumen], responses=_respuestas(401))
async def mis_ordenes(
    uow: Uow,
    pagina: Annotated[ParametrosPagina, Depends(parametros_pagina)],
    usuario: Usuario = Depends(get_usuario_actual),
):
    """Lo propio sólo pide estar autenticado (RN-17): ningún rol."""
    return await service.listar_mis_ordenes(uow, usuario.id, pagina)


@router.get(
    "/ordenes/{id}", response_model=OrdenDetalle, responses=_respuestas(401, 403, 404),
)
async def ver_orden(id: IdRuta, uow: Uow, usuario: Usuario = Depends(get_usuario_actual)):
    """Personal vigente o dueño del vehículo (RN-17)."""
    with _traducir_errores():
        return await service.obtener_detalle(uow, usuario.id, id)


@router.post(
    "/ordenes/{id}/iniciar", response_model=OrdenDetalle, responses=_respuestas(401, 403, 404, 409),
)
async def iniciar_orden(
    id: IdRuta, uow: Uow, usuario: Usuario = Depends(requiere_rol("MECANICO"))
):
    """Sólo un MECANICO (SU-03): un ADMIN sin ese rol recibe 403."""
    with _traducir_errores():
        return await service.iniciar_orden(uow, usuario.id, id)


@router.post(
    "/ordenes/{id}/terminar", response_model=OrdenDetalle, responses=_respuestas(401, 403, 404, 409),
)
async def terminar_orden(
    id: IdRuta, uow: Uow, usuario: Usuario = Depends(requiere_rol("MECANICO", "ADMIN"))
):
    """Mecánico asignado o ADMIN; el servicio decide cuál (403 antes que 409)."""
    with _traducir_errores():
        return await service.terminar_orden(uow, usuario.id, id)


@router.post(
    "/ordenes/{id}/cancelar", response_model=OrdenDetalle, responses=_respuestas(401, 403, 404, 409),
)
async def cancelar_orden(id: IdRuta, uow: Uow, usuario: Usuario = Depends(get_usuario_actual)):
    """La ruta NO lleva requiere_rol: RECEPCION, ADMIN o el dueño; lo decide el servicio."""
    with _traducir_errores():
        return await service.cancelar_orden(uow, usuario.id, id)
