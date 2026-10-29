"""Repositorios del módulo repuestos (CH-07).

Ningún método confirma: el commit es del UnitOfWork (regla 13). `mover_stock` es el
único lugar donde se escribe `repuesto.stock` (RN-14, DD-14).
"""
from collections.abc import Mapping
from typing import Any, TypeVar

from sqlmodel import SQLModel, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.paginacion import Pagina, ParametrosPagina
from app.core.repository import BaseRepository, SoftDeleteRepository
from app.modules.repuestos.models import HistorialPrecio, MovimientoStock, Repuesto

T = TypeVar("T", bound=SQLModel)


class StockInsuficiente(Exception):
    """El descuento dejaría el stock en negativo. Órdenes la importa de acá (CH-08)."""

    def __init__(self, codigo: str, disponible: int, pedido: int) -> None:
        self.codigo = codigo
        self.disponible = disponible
        self.pedido = pedido
        super().__init__(f"Stock insuficiente de {codigo}: hay {disponible} y se piden {pedido}")


class RepuestoRepository(SoftDeleteRepository[Repuesto]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Repuesto)

    async def update(self, entidad: Repuesto, cambios: Mapping[str, Any] | None = None) -> Repuesto:
        # el stock no se edita por PATCH: sólo cambia con movimientos (RN-14)
        if "stock" in (cambios or {}):
            raise ValueError("El stock sólo se modifica desde mover_stock (RN-14)")
        return await super().update(entidad, cambios)

    async def listar(self, q: str | None, pagina: ParametrosPagina) -> Pagina[Repuesto]:
        """Vigentes por id; `q` busca en la descripción con parámetro ligado (C-16)."""
        consulta = self._consulta_base()
        if q is not None and q.strip():
            consulta = consulta.where(col(Repuesto.descripcion).ilike(f"%{q.strip()}%"))
        return await self._paginar(consulta, pagina)

    async def mover_stock(
        self,
        repuesto: Repuesto,
        cantidad: int,
        *,
        motivo: str,
        usuario_id: int,
        orden_id: int | None = None,
    ) -> MovimientoStock:
        """Único punto de escritura de `repuesto.stock` (RN-14, DD-14).

        Positiva suma, negativa descuenta. Sólo hace flush: NO confirma ni abre el UoW,
        porque lo llama quien ya tiene la transacción abierta (alta, reposición y terminar
        orden). Si confirmara acá, con stock faltante en el segundo ítem quedarían
        escrituras a medias (RN-13, C-11).
        """
        if cantidad == 0:
            raise ValueError("La cantidad del movimiento no puede ser cero")
        if repuesto.stock + cantidad < 0:
            raise StockInsuficiente(repuesto.codigo, repuesto.stock, abs(cantidad))
        repuesto.stock += cantidad
        self.session.add(repuesto)
        movimiento = MovimientoStock(
            repuesto_id=repuesto.id,
            orden_id=orden_id,
            usuario_id=usuario_id,
            cantidad=cantidad,
            motivo=motivo,
        )
        self.session.add(movimiento)
        await self.session.flush()
        return movimiento


class _SoloAgregadoRepository(BaseRepository[T]):
    """Tablas de sólo agregado (RN-15): la base ya las protege con un disparador,
    acá ni siquiera se ofrece modificar o borrar."""

    async def update(self, entidad: T, cambios: Mapping[str, Any] | None = None) -> T:
        raise RuntimeError("Tabla de sólo agregado (RN-15)")

    async def delete(self, entidad: T) -> None:
        raise RuntimeError("Tabla de sólo agregado (RN-15)")

    async def listar_por_repuesto(self, repuesto_id: int) -> list[T]:
        consulta = (
            self._consulta_base()
            .where(col(self.modelo.repuesto_id) == repuesto_id)
            .order_by(self._pk)
        )
        return list((await self.session.exec(consulta)).all())


class MovimientoStockRepository(_SoloAgregadoRepository[MovimientoStock]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, MovimientoStock)


class HistorialPrecioRepository(_SoloAgregadoRepository[HistorialPrecio]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, HistorialPrecio)
