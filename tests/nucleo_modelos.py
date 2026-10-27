"""Modelos de prueba del núcleo (CH-03, design D6).

Viven en el esquema `nucleo_prueba` de `taller_test` y en una base declarativa
con registro y MetaData PROPIOS: nunca en `SQLModel.metadata`. Así el test de
las 13 tablas y `alembic check` no los ven. No son modelos de la app.
"""
from datetime import datetime

from sqlalchemy import DateTime, MetaData, UniqueConstraint
from sqlalchemy.orm import registry
from sqlmodel import Field, Relationship, SQLModel

ESQUEMA = "nucleo_prueba"

_registro = registry(metadata=MetaData(schema=ESQUEMA))
_RAISE = {"lazy": "raise"}


class BasePrueba(SQLModel, registry=_registro):
    pass


class CosaPrueba(BasePrueba, table=True):
    __tablename__ = "cosa_prueba"

    id: int | None = Field(default=None, primary_key=True)
    nombre: str = Field(unique=True)
    etiqueta: str | None = None
    borrado_en: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    detalles: list["DetallePrueba"] = Relationship(
        back_populates="cosa", sa_relationship_kwargs=_RAISE
    )


class DetallePrueba(BasePrueba, table=True):
    __tablename__ = "detalle_prueba"
    # codigo UNIQUE diferido: el flush pasa y el error aparece recién al confirmar.
    __table_args__ = (
        UniqueConstraint(
            "codigo", name="uq_detalle_prueba_codigo", deferrable=True, initially="DEFERRED"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    cosa_id: int = Field(foreign_key=f"{ESQUEMA}.cosa_prueba.id", index=True)
    texto: str = ""
    codigo: str | None = None

    cosa: CosaPrueba = Relationship(back_populates="detalles", sa_relationship_kwargs=_RAISE)
