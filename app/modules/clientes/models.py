from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, Index, text
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.modules.ordenes.models import OrdenTrabajo
    from app.modules.usuarios.models import Usuario

_RAISE = {"lazy": "raise"}


class Cliente(SQLModel, table=True):
    __tablename__ = "cliente"

    id: int | None = Field(default=None, primary_key=True)
    # UNIQUE (uno a uno con usuario); NULL = cliente sin acceso a la API.
    usuario_id: int | None = Field(default=None, foreign_key="usuario.id", unique=True)
    nombre: str
    documento: str = Field(unique=True)
    telefono: str

    usuario: Optional["Usuario"] = Relationship(
        back_populates="cliente", sa_relationship_kwargs=_RAISE
    )
    vehiculos: list["Vehiculo"] = Relationship(
        back_populates="cliente", sa_relationship_kwargs=_RAISE
    )


class Vehiculo(SQLModel, table=True):
    __tablename__ = "vehiculo"
    __table_args__ = (
        CheckConstraint("anio BETWEEN 1950 AND 2100", name="anio_rango"),
        # La patente es única sólo entre los vigentes: un auto vendido se puede
        # registrar de nuevo (borrado lógico), por eso no es un UNIQUE común.
        Index(
            "uq_vehiculo_patente_vigente",
            "patente",
            unique=True,
            postgresql_where=text("borrado_en IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    cliente_id: int = Field(foreign_key="cliente.id", index=True)
    patente: str
    marca: str
    modelo: str
    anio: int
    borrado_en: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))

    cliente: Cliente = Relationship(back_populates="vehiculos", sa_relationship_kwargs=_RAISE)
    ordenes: list["OrdenTrabajo"] = Relationship(
        back_populates="vehiculo", sa_relationship_kwargs=_RAISE
    )
