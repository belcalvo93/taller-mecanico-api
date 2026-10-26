from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, Index, text
from sqlmodel import Field, Relationship, SQLModel

from app.core.database import ahora_utc

# Sin `from __future__ import annotations`: SQLModel no resuelve bien las
# relaciones con anotaciones diferidas. Las de otros módulos van entre comillas.
if TYPE_CHECKING:
    from app.modules.clientes.models import Cliente
    from app.modules.ordenes.models import OrdenTrabajo

# Toda relación es lazy="raise": acceder a una no precargada falla en el acto
# en vez de lanzar una consulta implícita. Los repositorios precargan.
_RAISE = {"lazy": "raise"}


class Usuario(SQLModel, table=True):
    __tablename__ = "usuario"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True)
    nombre: str
    password_hash: str
    activo: bool = True
    debe_cambiar_password: bool = False
    password_cambiada_en: datetime | None = Field(
        default=None, sa_type=DateTime(timezone=True)
    )
    # Sin columna `rol`: los roles son las filas vigentes de asignacion_rol.

    asignaciones: list["AsignacionRol"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={**_RAISE, "foreign_keys": "[AsignacionRol.usuario_id]"},
    )
    cliente: Optional["Cliente"] = Relationship(
        back_populates="usuario",
        sa_relationship_kwargs={**_RAISE, "uselist": False},
    )
    ordenes_asignadas: list["OrdenTrabajo"] = Relationship(
        back_populates="mecanico", sa_relationship_kwargs=_RAISE
    )


class AsignacionRol(SQLModel, table=True):
    __tablename__ = "asignacion_rol"
    __table_args__ = (
        CheckConstraint(
            "rol IN ('ADMIN', 'RECEPCION', 'MECANICO', 'CLIENTE')", name="rol_valido"
        ),
        # Una sola asignación abierta por (usuario, rol); las revocadas no cuentan.
        Index(
            "uq_asignacion_rol_abierta",
            "usuario_id",
            "rol",
            unique=True,
            postgresql_where=text("revocada_en IS NULL"),
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    usuario_id: int = Field(foreign_key="usuario.id", index=True)
    rol: str
    desde: datetime = Field(default_factory=ahora_utc, sa_type=DateTime(timezone=True))
    vence_en: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    revocada_en: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    # NULL = otorgada por el sistema (seed). FK a usuario: decisión D4.
    otorgada_por: int | None = Field(default=None, foreign_key="usuario.id", index=True)

    usuario: Usuario = Relationship(
        back_populates="asignaciones",
        sa_relationship_kwargs={**_RAISE, "foreign_keys": "[AsignacionRol.usuario_id]"},
    )


class IntentoAcceso(SQLModel, table=True):
    __tablename__ = "intento_acceso"
    # Lo consulta el límite de intentos del login (RN-08).
    __table_args__ = (Index("ix_intento_acceso_email_ip_cuando", "email", "ip", "cuando"),)

    id: int | None = Field(default=None, primary_key=True)
    cuando: datetime = Field(default_factory=ahora_utc, sa_type=DateTime(timezone=True))
    email: str
    ip: str
    exito: bool


class EventoSeguridad(SQLModel, table=True):
    __tablename__ = "evento_seguridad"

    id: int | None = Field(default=None, primary_key=True)
    cuando: datetime = Field(default_factory=ahora_utc, sa_type=DateTime(timezone=True))
    actor: str
    accion: str
