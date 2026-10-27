"""Rutas HTTP de clientes y vehículos (CH-06). Van en el grupo PROTEGIDO de main.py.

El router construye el Unit of Work con `get_clientes_uow`, se lo pasa al servicio
sin abrirlo y traduce los errores de dominio a HTTP con mensajes propios.
"""
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status

from app.core.dependencies import get_usuario_actual, requiere_rol
from app.modules.clientes import service
from app.modules.clientes.schemas import (
    ClienteConVehiculos,
    ClienteCrear,
    ClienteLeer,
    VehiculoCrear,
    VehiculoLeer,
)
from app.modules.clientes.unit_of_work import ClientesUnitOfWork, get_clientes_uow
from app.modules.usuarios.models import Usuario

# Los ids son INTEGER: fuera de 1..2^31-1 asyncpg falla y sería un 500 (RN-18).
# No entero o fuera de rango → 422 antes de ejecutar el handler (C-01).
IdRuta = Annotated[int, Path(ge=1, le=2_147_483_647)]
Uow = Annotated[ClientesUnitOfWork, Depends(get_clientes_uow)]

SOLO_PERSONAL = [Depends(requiere_rol("RECEPCION", "ADMIN"))]

_ERRORES: dict[type[Exception], tuple[int, str]] = {
    service.ClienteNoEncontrado: (status.HTTP_404_NOT_FOUND, "Cliente no encontrado"),
    service.VehiculoNoEncontrado: (status.HTTP_404_NOT_FOUND, "Vehículo no encontrado"),
    service.DocumentoDuplicado: (status.HTTP_409_CONFLICT, "Ya existe un cliente con ese documento"),
    service.PatenteDuplicada: (status.HTTP_409_CONFLICT, "Ya hay un vehículo vigente con esa patente"),
    service.VehiculoConOrdenesAbiertas: (
        status.HTTP_409_CONFLICT,
        "El vehículo tiene órdenes abiertas: no se puede dar de baja",
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


router = APIRouter(tags=["clientes y vehículos"])


@router.post(
    "/clientes",
    status_code=status.HTTP_201_CREATED,
    response_model=ClienteLeer,
    dependencies=SOLO_PERSONAL,
    responses=_respuestas(401, 403, 409),
)
async def alta_de_cliente(datos: ClienteCrear, uow: Uow):
    with _traducir_errores():
        return await service.crear_cliente(uow, datos)


@router.get(
    "/clientes/{id}",
    response_model=ClienteConVehiculos,
    dependencies=SOLO_PERSONAL,
    responses=_respuestas(401, 403, 404),
)
async def ver_cliente(id: IdRuta, uow: Uow):
    with _traducir_errores():
        return await service.obtener_cliente(uow, id)


@router.post(
    "/clientes/{id}/vehiculos",
    status_code=status.HTTP_201_CREATED,
    response_model=VehiculoLeer,
    dependencies=SOLO_PERSONAL,
    responses=_respuestas(401, 403, 404, 409),
)
async def alta_de_vehiculo(id: IdRuta, datos: VehiculoCrear, uow: Uow):
    with _traducir_errores():
        return await service.crear_vehiculo(uow, id, datos)


@router.delete(
    "/vehiculos/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    dependencies=SOLO_PERSONAL,
    responses=_respuestas(401, 403, 404, 409),
)
async def baja_de_vehiculo(id: IdRuta, uow: Uow):
    with _traducir_errores():
        await service.dar_de_baja_vehiculo(uow, id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/mis-vehiculos", response_model=list[VehiculoLeer], responses=_respuestas(401))
async def mis_vehiculos(uow: Uow, usuario: Usuario = Depends(get_usuario_actual)):
    """Lo propio sólo pide estar autenticado (RN-17): ningún rol."""
    return await service.listar_mis_vehiculos(uow, usuario.id)
