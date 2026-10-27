from datetime import datetime

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import ahora_utc
from app.core.repository import BaseRepository
from app.modules.usuarios.models import (
    AsignacionRol,
    EventoSeguridad,
    IntentoAcceso,
    Usuario,
)


class UsuarioRepository(BaseRepository[Usuario]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Usuario)

    async def get_by_email(self, email: str) -> Usuario | None:
        statement = select(Usuario).where(Usuario.email == email)
        result = await self.session.exec(statement)
        return result.first()

    async def get_by_id_con_asignaciones(self, usuario_id: int) -> Usuario | None:
        statement = (
            select(Usuario)
            .where(Usuario.id == usuario_id)
            .options(selectinload(Usuario.asignaciones))
        )
        result = await self.session.exec(statement)
        return result.first()


class AsignacionRolRepository(BaseRepository[AsignacionRol]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AsignacionRol)

    async def listar_roles_vigentes(
        self, usuario_id: int, ahora: datetime | None = None
    ) -> list[str]:
        instante = ahora or ahora_utc()
        statement = (
            select(AsignacionRol.rol)
            .where(
                AsignacionRol.usuario_id == usuario_id,
                AsignacionRol.revocada_en.is_(None),
                (AsignacionRol.vence_en.is_(None) | (AsignacionRol.vence_en > instante)),
            )
            .order_by(AsignacionRol.rol)
        )
        result = await self.session.exec(statement)
        return list(result.all())


class IntentoAccesoRepository(BaseRepository[IntentoAcceso]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, IntentoAcceso)

    async def contar_fallos_vigentes_y_primer_fallo(
        self, email: str, ip: str, desde: datetime
    ) -> tuple[int, datetime | None]:
        stmt_exito = (
            select(IntentoAcceso.cuando)
            .where(
                IntentoAcceso.email == email,
                IntentoAcceso.ip == ip,
                IntentoAcceso.exito == True,  # noqa: E712
            )
            .order_by(IntentoAcceso.cuando.desc())
            .limit(1)
        )
        res_exito = await self.session.exec(stmt_exito)
        ultimo_exito = res_exito.first()

        condiciones = [
            IntentoAcceso.email == email,
            IntentoAcceso.ip == ip,
            IntentoAcceso.exito == False,  # noqa: E712
            IntentoAcceso.cuando >= desde,
        ]
        if ultimo_exito is not None and ultimo_exito >= desde:
            condiciones.append(IntentoAcceso.cuando > ultimo_exito)

        stmt_fallos = (
            select(IntentoAcceso.cuando)
            .where(*condiciones)
            .order_by(IntentoAcceso.cuando.asc())
        )
        res_fallos = await self.session.exec(stmt_fallos)
        fallos = res_fallos.all()
        cantidad = len(fallos)
        primer_fallo = fallos[0] if cantidad > 0 else None
        return cantidad, primer_fallo


class EventoSeguridadRepository(BaseRepository[EventoSeguridad]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, EventoSeguridad)

    async def registrar(self, actor: str, accion: str) -> EventoSeguridad:
        evento = EventoSeguridad(actor=actor, accion=accion)
        return await self.add(evento)
