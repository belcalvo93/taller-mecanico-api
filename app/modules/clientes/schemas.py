"""Contratos de entrada y salida del módulo clientes (CH-06), separados de los modelos.

Entradas con extra="forbid": un campo no declarado (por ejemplo `usuario_id`) es
422, no se ignora. Todo lo que el contrato puede rechazar se rechaza acá, antes de
llegar a la base: ninguna entrada inválida termina en 500 (RN-18).
"""
from typing import Annotated

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
)

ANIO_MINIMO = 1950  # mismo rango que el CHECK ck_vehiculo_anio_rango de la base
ANIO_MAXIMO = 2100


def _texto(maximo: int):
    """Texto obligatorio, sin espacios alrededor y sin el carácter NUL (PostgreSQL
    lo rechaza y la petición terminaría en 500)."""
    return Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=maximo, pattern=r"^[^\x00]*$"
        ),
    ]


def _normalizar_patente(valor: object) -> object:
    # Mayúsculas y sin espacios: "ab 123 cd" no puede esquivar el índice único de "AB123CD".
    if isinstance(valor, str):
        return "".join(valor.split()).upper()
    return valor


Patente = Annotated[
    str,
    BeforeValidator(_normalizar_patente),
    StringConstraints(pattern=r"^[A-Z0-9]{4,10}$"),
]
Anio = Annotated[int, Field(ge=ANIO_MINIMO, le=ANIO_MAXIMO)]


class _Entrada(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClienteCrear(_Entrada):
    """Alta por la recepción. No lleva `usuario_id`: el vínculo con un usuario sólo
    lo crea el auto-registro (RN-02)."""

    nombre: _texto(120)
    documento: _texto(20)
    telefono: _texto(30)


class VehiculoCrear(_Entrada):
    patente: Patente
    marca: _texto(60)
    modelo: _texto(60)
    anio: Anio


class _Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VehiculoLeer(_Salida):
    id: int
    cliente_id: int
    patente: str
    marca: str
    modelo: str
    anio: int


class ClienteLeer(_Salida):
    id: int
    usuario_id: int | None
    nombre: str
    documento: str
    telefono: str


class ClienteConVehiculos(ClienteLeer):
    vehiculos: list[VehiculoLeer]

    @field_validator("vehiculos")
    @classmethod
    def _por_id(cls, vehiculos: list[VehiculoLeer]) -> list[VehiculoLeer]:
        # selectinload no garantiza el orden: el contrato lo fija.
        return sorted(vehiculos, key=lambda v: v.id)
