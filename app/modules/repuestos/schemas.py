"""Contratos de entrada y salida del módulo repuestos (CH-07), separados de los modelos.

Entradas con extra="forbid": `stock` y `codigo` en un PATCH, o `stock` en el alta, son
422 y no se ignoran (RN-14). Todo lo que el contrato puede rechazar se rechaza acá,
antes de llegar a la base: ninguna entrada inválida termina en 500 (RN-18).
"""
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ENTERO_MAXIMO = 2_147_483_647  # los enteros de la base son INTEGER


def _texto(maximo: int):
    """Texto obligatorio, sin espacios alrededor y sin el carácter NUL (PostgreSQL
    lo rechaza y la petición terminaría en 500)."""
    return Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=maximo, pattern=r"^[^\x00]*$"
        ),
    ]


# NUMERIC(10, 2): más cifras o más decimales los rechazaría la base
Precio = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepuestoCrear(_Entrada):
    codigo: _texto(40)
    descripcion: _texto(200)
    precio: Precio
    stock_inicial: Annotated[int, Field(ge=0, le=ENTERO_MAXIMO)] = 0


class RepuestoActualizar(_Entrada):
    """PATCH: sólo lo enviado. Sin `codigo` ni `stock` (el stock sólo cambia con movimientos)."""

    descripcion: _texto(200) | None = None
    precio: Precio | None = None

    @field_validator("descripcion", "precio", mode="before")
    @classmethod
    def _no_null(cls, valor: object) -> object:
        # "no enviado" es válido, pero un null explícito no: sería borrar un dato obligatorio
        if valor is None:
            raise ValueError("no puede ser null")
        return valor


class ReposicionCrear(_Entrada):
    cantidad: Annotated[int, Field(gt=0, le=ENTERO_MAXIMO)]
    motivo: _texto(200) = "Reposición"


class _Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class RepuestoLeer(_Salida):
    id: int
    codigo: str
    descripcion: str
    precio: Decimal
    stock: int


class MovimientoStockLeer(_Salida):
    id: int
    repuesto_id: int
    orden_id: int | None
    usuario_id: int
    cantidad: int
    motivo: str
    cuando: datetime


class HistorialPrecioLeer(_Salida):
    id: int
    repuesto_id: int
    usuario_id: int
    precio_anterior: Decimal
    precio_nuevo: Decimal
    cuando: datetime
