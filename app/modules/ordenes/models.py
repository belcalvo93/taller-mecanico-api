from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, UniqueConstraint
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import ahora_utc

if TYPE_CHECKING:
    from app.modules.clientes.models import Vehiculo
    from app.modules.repuestos.models import Repuesto
    from app.modules.usuarios.models import Usuario

_RAISE = {"lazy": "raise"}


class EstadoOrden(SQLModel, table=True):
    """Catálogo de estados (funciona como un enum). La migración lo crea vacío y
    lo llena seed.py; no hay endpoints para crear, editar ni borrar estados."""

    __tablename__ = "estado_orden"

    codigo: str = Field(primary_key=True)
    descripcion: str
    posicion: int = Field(unique=True)
    es_final: bool = False

    ordenes: list["OrdenTrabajo"] = Relationship(
        back_populates="estado_orden", sa_relationship_kwargs=_RAISE
    )


class OrdenTrabajo(SQLModel, table=True):
    __tablename__ = "orden_trabajo"
    __table_args__ = (CheckConstraint("total >= 0", name="total_no_negativo"),)

    id: int | None = Field(default=None, primary_key=True)
    vehiculo_id: int = Field(foreign_key="vehiculo.id", index=True)
    mecanico_id: int | None = Field(default=None, foreign_key="usuario.id", index=True)
    # FK al catálogo, nunca un CHECK con la lista de estados.
    estado: str = Field(foreign_key="estado_orden.codigo", index=True)
    falla: str
    creada_en: datetime = Field(default_factory=ahora_utc, sa_type=DateTime(timezone=True))
    total: Decimal = Field(max_digits=12, decimal_places=2)

    vehiculo: "Vehiculo" = Relationship(back_populates="ordenes", sa_relationship_kwargs=_RAISE)
    mecanico: Optional["Usuario"] = Relationship(
        back_populates="ordenes_asignadas", sa_relationship_kwargs=_RAISE
    )
    # La columna se llama `estado`, por eso la relación es `estado_orden`.
    estado_orden: EstadoOrden = Relationship(
        back_populates="ordenes", sa_relationship_kwargs=_RAISE
    )
    # Composición: los ítems no existen sin su orden.
    items: list["ItemOrden"] = Relationship(
        back_populates="orden",
        sa_relationship_kwargs={**_RAISE, "cascade": "all, delete-orphan"},
    )
    historial: list["HistorialEstadoOrden"] = Relationship(
        back_populates="orden",
        sa_relationship_kwargs={**_RAISE, "order_by": "HistorialEstadoOrden.id"},
    )


class ItemOrden(SQLModel, table=True):
    __tablename__ = "item_orden"
    __table_args__ = (
        UniqueConstraint("orden_id", "repuesto_id"),
        CheckConstraint("cantidad > 0", name="cantidad_positiva"),
        CheckConstraint("precio_unitario > 0", name="precio_unitario_positivo"),
    )

    id: int | None = Field(default=None, primary_key=True)
    orden_id: int = Field(foreign_key="orden_trabajo.id", index=True)
    repuesto_id: int = Field(foreign_key="repuesto.id", index=True)
    cantidad: int
    # Foto del precio al momento de la orden (RN): no sigue al precio del repuesto.
    precio_unitario: Decimal = Field(max_digits=10, decimal_places=2)

    orden: OrdenTrabajo = Relationship(back_populates="items", sa_relationship_kwargs=_RAISE)
    repuesto: "Repuesto" = Relationship(back_populates="items", sa_relationship_kwargs=_RAISE)


class HistorialEstadoOrden(SQLModel, table=True):
    """Sólo agregado (RN-15): el disparador lo instala la migración 2."""

    __tablename__ = "historial_estado_orden"

    id: int | None = Field(default=None, primary_key=True)
    orden_id: int = Field(foreign_key="orden_trabajo.id", index=True)
    desde_estado: str | None = Field(
        default=None, foreign_key="estado_orden.codigo", index=True
    )
    hasta_estado: str = Field(foreign_key="estado_orden.codigo", index=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    cuando: datetime = Field(default_factory=ahora_utc, sa_type=DateTime(timezone=True))

    orden: OrdenTrabajo = Relationship(back_populates="historial", sa_relationship_kwargs=_RAISE)
