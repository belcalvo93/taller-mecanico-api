"""Repositorios genéricos (CH-03) contra PostgreSQL real, con modelos de prueba
en el esquema `nucleo_prueba` (nunca en la metadata de la app)."""
from sqlmodel import SQLModel


def test_los_modelos_de_prueba_no_ensucian_la_metadata_de_la_app():
    import app.modules.modelos  # noqa: F401
    from tests import nucleo_modelos

    assert len(SQLModel.metadata.tables) == 13
    assert "nucleo_prueba.cosa_prueba" not in SQLModel.metadata.tables
    tablas_de_prueba = set(nucleo_modelos.BasePrueba.metadata.tables)
    assert tablas_de_prueba == {"nucleo_prueba.cosa_prueba", "nucleo_prueba.detalle_prueba"}


# --- Fixtures del esquema de prueba -------------------------------------------
from sqlalchemy import text  # noqa: E402


async def _tablas_de_prueba(motor) -> set[str]:
    async with motor.connect() as c:
        filas = await c.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'nucleo_prueba'"
            )
        )
        return {f[0] for f in filas}


async def test_la_fixture_esquema_nucleo_crea_las_dos_tablas(motor, esquema_nucleo):
    assert await _tablas_de_prueba(motor) == {"cosa_prueba", "detalle_prueba"}


async def test_el_esquema_nucleo_se_borra_al_terminar_cada_test(motor):
    """Triangula la fixture: el test anterior no dejó nada colgado."""
    assert await _tablas_de_prueba(motor) == set()
    async with motor.connect() as c:
        hay = await c.scalar(
            text("SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'nucleo_prueba'")
        )
    assert hay == 0
