"""Contratos de entrada y salida del módulo órdenes (CH-08), separados de los modelos.

Entradas con extra="forbid": precio, total, estado o fecha en el cuerpo es 422, no
se ignora (RN-10: los calcula el servidor). Todo lo que el contrato puede rechazar
se rechaza acá, antes de llegar a la base: ninguna entrada inválida termina en 500
(RN-18).
"""
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PlainSerializer,
    StringConstraints,
    model_validator,
)

ID_MAXIMO = 2_147_483_647  # INTEGER de PostgreSQL: más allá asyncpg falla y sería un 500
CANTIDAD_MAXIMA = 10_000
ITEMS_MAXIMOS = 50
CENTAVO = Decimal("0.01")

# Los importes viajan como texto decimal con dos decimales ("68000.00").
Importe = Annotated[
    Decimal, PlainSerializer(lambda v: str(v.quantize(CENTAVO)), return_type=str, when_used="json")
]
IdEntero = Annotated[int, Field(ge=1, le=ID_MAXIMO)]
Falla = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500, pattern=r"^[^\x00]*$")
]


class EstadoOrdenCodigo(StrEnum):
    """Los códigos del catálogo `estado_orden` (los carga seed.py). Un test verifica
    que coinciden; el servicio nombra los estados con este enum, nunca con cadenas."""

    PENDIENTE = "PENDIENTE"
    EN_REPARACION = "EN_REPARACION"
    TERMINADA = "TERMINADA"
    CANCELADA = "CANCELADA"


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemOrdenCrear(_Entrada):
    repuesto_id: IdEntero
    cantidad: Annotated[int, Field(ge=1, le=CANTIDAD_MAXIMA)]


class OrdenCrear(_Entrada):
    vehiculo_id: IdEntero
    falla: Falla
    items: Annotated[list[ItemOrdenCrear], Field(min_length=1, max_length=ITEMS_MAXIMOS)]

    @model_validator(mode="after")
    def _sin_repuestos_repetidos(self) -> "OrdenCrear":
        ids = [i.repuesto_id for i in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("un repuesto no puede repetirse en los ítems de la orden")
        return self


class _Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EstadoOrdenLeer(_Salida):
    codigo: str
    descripcion: str
    posicion: int
    es_final: bool


class ItemOrdenLeer(_Salida):
    repuesto_id: int
    codigo: str
    descripcion: str
    cantidad: int
    precio_unitario: Importe
    subtotal: Importe


class HistorialLeer(_Salida):
    desde_estado: str | None
    hasta_estado: str
    usuario_id: int
    cuando: datetime


class OrdenResumen(_Salida):
    id: int
    estado: str
    patente: str
    cliente: str
    total: Importe
    creada_en: datetime
    mecanico_id: int | None
    falla: str


class OrdenDetalle(OrdenResumen):
    items: list[ItemOrdenLeer]
    historial: list[HistorialLeer]


def armar_resumen(orden) -> OrdenResumen:
    """Función pura: necesita `vehiculo` y su `cliente` ya precargados."""
    return OrdenResumen(
        id=orden.id, estado=orden.estado, patente=orden.vehiculo.patente,
        cliente=orden.vehiculo.cliente.nombre, total=orden.total, creada_en=orden.creada_en,
        mecanico_id=orden.mecanico_id, falla=orden.falla,
    )


def armar_detalle(orden) -> OrdenDetalle:
    """Función pura (se prueba sin base): arma la salida desde una orden con vehículo,
    cliente, ítems (con su repuesto) e historial ya precargados (design D7)."""
    items = [
        ItemOrdenLeer(
            repuesto_id=i.repuesto_id, codigo=i.repuesto.codigo, descripcion=i.repuesto.descripcion,
            cantidad=i.cantidad, precio_unitario=i.precio_unitario,
            subtotal=i.cantidad * i.precio_unitario,
        )
        for i in sorted(orden.items, key=lambda i: i.id)  # selectinload no garantiza el orden
    ]
    historial = [HistorialLeer.model_validate(h) for h in orden.historial]
    return OrdenDetalle(
        **armar_resumen(orden).model_dump(), items=items, historial=historial,
    )
