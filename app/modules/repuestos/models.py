from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Index, text
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import ahora_utc

if TYPE_CHECKING:
    from app.modules.ordenes.models import ItemOrden

_RAISE = {"lazy": "raise"}


class Repuesto(SQLModel, table=True):
    __tablename__ = "repuesto"
    __table_args__ = (
        CheckConstraint("precio > 0", name="precio_positivo"),
        CheckConstraint("stock >= 0", name="stock_no_negativo"),
        # El código es único sólo entre los vigentes (borrado lógico).
        Index(
            "uq_repuesto_codigo_vigente",
            "codigo",
            unique=True,
            postgresql_where=text("borrado_en IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    codigo: str
    descripcion: str
    precio: Decimal = Field(max_digits=10, decimal_places=2)
    stock: int
    borrado_en: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    items: list["ItemOrden"] = Relationship(
        back_populates="repuesto", sa_relationship_kwargs=_RAISE
    )
    movimientos: list["MovimientoStock"] = Relationship(
        back_populates="repuesto", sa_relationship_kwargs=_RAISE
    )
    historial_precios: list["HistorialPrecio"] = Relationship(
        back_populates="repuesto", sa_relationship_kwargs=_RAISE
    )


class MovimientoStock(SQLModel, table=True):
    """Sólo agregado (RN-15): el disparador lo instala la migración 2."""

    __tablename__ = "movimiento_stock"
    __table_args__ = (CheckConstraint("cantidad <> 0", name="cantidad_no_cero"),)

    id: int | None = Field(default=None, primary_key=True)
    repuesto_id: int = Field(foreign_key="repuesto.id", index=True)
    orden_id: int | None = Field(default=None, foreign_key="orden_trabajo.id", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    cantidad: int
    motivo: str
    cuando: datetime = Field(default_factory=ahora_utc, sa_type=DateTime(timezone=True))

    repuesto: Repuesto = Relationship(
        back_populates="movimientos", sa_relationship_kwargs=_RAISE
    )


class HistorialPrecio(SQLModel, table=True):
    """Sólo agregado (RN-15). La tabla se llama historial_precio_repuesto."""

    __tablename__ = "historial_precio_repuesto"
    __table_args__ = (
        CheckConstraint("precio_nuevo > 0", name="precio_nuevo_positivo"),
        CheckConstraint("precio_nuevo <> precio_anterior", name="precio_distinto"),
    )

    id: int | None = Field(default=None, primary_key=True)
    repuesto_id: int = Field(foreign_key="repuesto.id", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    precio_anterior: Decimal = Field(max_digits=10, decimal_places=2)
    precio_nuevo: Decimal = Field(max_digits=10, decimal_places=2)
    cuando: datetime = Field(default_factory=ahora_utc, sa_type=DateTime(timezone=True))

    repuesto: Repuesto = Relationship(
        back_populates="historial_precios", sa_relationship_kwargs=_RAISE
    )
