"""solo agregado

Migración escrita a mano (la 1 es autogenerate): instala el sólo agregado de
RN-15 con un disparador de la base en las tres tablas de historial. Vale para
cualquier cliente (la API, psql, un script), no sólo para la aplicación.

Leída antes de aplicarla por Belén Calvo el 25/10/2026: revisé la función y los
tres triggers (BEFORE UPDATE OR DELETE, FOR EACH STATEMENT) sobre
historial_estado_orden, movimiento_stock e historial_precio_repuesto, y que el
downgrade los borre en orden inverso. TRUNCATE queda permitido a propósito para seed.py.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-25 23:07:48.811811

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, Sequence[str], None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# SQL literal (regla 17): cada sentencia está escrita completa, sin interpolar nada.


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE FUNCTION rechazar_cambio_solo_agregado() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'La tabla % es de sólo agregado: no se permite %', TG_TABLE_NAME, TG_OP;
        END
        $$
        """
    )
    # FOR EACH STATEMENT (y no FOR EACH ROW): rechaza también un UPDATE/DELETE que
    # no toca ninguna fila, así el rechazo no depende de que la tabla tenga datos.
    # No cubre TRUNCATE a propósito: seed.py lo usa para volver al estado inicial.
    op.execute(
        """
        CREATE TRIGGER trg_historial_estado_orden_solo_agregado
        BEFORE UPDATE OR DELETE ON historial_estado_orden
        FOR EACH STATEMENT EXECUTE FUNCTION rechazar_cambio_solo_agregado()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_movimiento_stock_solo_agregado
        BEFORE UPDATE OR DELETE ON movimiento_stock
        FOR EACH STATEMENT EXECUTE FUNCTION rechazar_cambio_solo_agregado()
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_historial_precio_repuesto_solo_agregado
        BEFORE UPDATE OR DELETE ON historial_precio_repuesto
        FOR EACH STATEMENT EXECUTE FUNCTION rechazar_cambio_solo_agregado()
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER IF EXISTS trg_historial_precio_repuesto_solo_agregado ON historial_precio_repuesto")
    op.execute("DROP TRIGGER IF EXISTS trg_movimiento_stock_solo_agregado ON movimiento_stock")
    op.execute("DROP TRIGGER IF EXISTS trg_historial_estado_orden_solo_agregado ON historial_estado_orden")
    op.execute("DROP FUNCTION IF EXISTS rechazar_cambio_solo_agregado()")
