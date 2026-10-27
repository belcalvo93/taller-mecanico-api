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


# --- BaseRepository ------------------------------------------------------------
import pytest  # noqa: E402
from sqlalchemy import insert, select  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.core.repository import BaseRepository  # noqa: E402
from tests.nucleo_modelos import CosaPrueba, DetallePrueba  # noqa: E402


async def insertar_cosas(sesiones, *filas: dict) -> None:
    """Inserta y CONFIRMA filas con SQL Core desde una sesión aparte (datos de partida)."""
    async with sesiones() as s:
        await (await s.connection()).execute(insert(CosaPrueba.__table__), list(filas))
        await s.commit()


async def test_get_by_id_inexistente_devuelve_none(sesion):
    """Identificador inexistente."""
    assert await BaseRepository(sesion, CosaPrueba).get_by_id(999) is None


async def test_get_by_id_existente_devuelve_la_entidad(sesion, sesiones):
    """Identificador existente."""
    await insertar_cosas(sesiones, {"id": 7, "nombre": "uno", "etiqueta": "x"})
    cosa = await BaseRepository(sesion, CosaPrueba).get_by_id(7)
    assert cosa is not None
    assert (cosa.id, cosa.nombre, cosa.etiqueta) == (7, "uno", "x")


# --- Ayudas ---------------------------------------------------------------------
from pathlib import Path  # noqa: E402

from sqlalchemy import event, func  # noqa: E402
from sqlalchemy.exc import InvalidRequestError  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.core.paginacion import ParametrosPagina, PaginaInexistente  # noqa: E402


def solo_select(sentencias: list[str]) -> int:
    return len([s for s in sentencias if s.lstrip().upper().startswith("SELECT")])


async def contar_filas(sesion, tabla) -> int:
    conexion = await sesion.connection()
    return (await conexion.execute(select(func.count()).select_from(tabla))).scalar_one()


class CosasRepo(BaseRepository[CosaPrueba]):
    """Repositorio concreto de prueba: métodos con nombre propio sobre _consulta_base/_paginar."""

    def __init__(self, session):
        super().__init__(session, CosaPrueba)

    async def listar_por_etiqueta(self, etiqueta: str, pagina: ParametrosPagina):
        consulta = self._consulta_base().where(CosaPrueba.etiqueta == etiqueta)
        return await self._paginar(consulta, pagina)

    async def get_con_detalles(self, id: int):
        consulta = (
            self._consulta_base()
            .where(CosaPrueba.id == id)
            .options(selectinload(CosaPrueba.detalles))
        )
        return (await self.session.exec(consulta)).first()


# --- add ------------------------------------------------------------------------
async def test_add_asigna_la_clave_y_no_confirma(sesion, sesiones):
    """add asigna la clave y no confirma."""
    cosa = await BaseRepository(sesion, CosaPrueba).add(CosaPrueba(nombre="a"))
    assert cosa.id is not None
    async with sesiones() as otra:
        assert await BaseRepository(otra, CosaPrueba).get_by_id(cosa.id) is None


async def test_lo_agregado_se_pierde_si_nadie_confirma(sesion, sesiones):
    """Lo agregado se pierde si nadie confirma."""
    cosa = await BaseRepository(sesion, CosaPrueba).add(CosaPrueba(nombre="a"))
    await sesion.rollback()
    async with sesiones() as otra:
        assert await BaseRepository(otra, CosaPrueba).get_by_id(cosa.id) is None


async def test_una_violacion_de_unicidad_aparece_en_el_add(sesion):
    """Una violación de restricción aparece en la escritura."""
    repo = BaseRepository(sesion, CosaPrueba)
    await repo.add(CosaPrueba(nombre="repetido"))
    with pytest.raises(IntegrityError):
        await repo.add(CosaPrueba(nombre="repetido"))


# --- update ---------------------------------------------------------------------
async def _fila_en_base(sesion, id):
    t = CosaPrueba.__table__
    conexion = await sesion.connection()
    return (await conexion.execute(select(t.c.etiqueta, t.c.nombre).where(t.c.id == id))).one()


async def test_update_aplica_solo_los_campos_indicados(sesion):
    """update aplica sólo los campos indicados."""
    repo = BaseRepository(sesion, CosaPrueba)
    cosa = await repo.add(CosaPrueba(nombre="n", etiqueta="a"))
    await repo.update(cosa, {"etiqueta": "b"})
    assert tuple(await _fila_en_base(sesion, cosa.id)) == ("b", "n")


async def test_update_rechaza_claves_que_no_son_columnas(sesion):
    repo = BaseRepository(sesion, CosaPrueba)
    cosa = await repo.add(CosaPrueba(nombre="n"))
    with pytest.raises(ValueError, match="no_existe"):
        await repo.update(cosa, {"no_existe": 1})
    assert not hasattr(cosa, "no_existe")


async def test_update_sin_cambios_sincroniza_lo_modificado_a_mano(sesion):
    repo = BaseRepository(sesion, CosaPrueba)
    cosa = await repo.add(CosaPrueba(nombre="n", etiqueta="a"))
    cosa.etiqueta = "z"
    await repo.update(cosa)
    assert (await _fila_en_base(sesion, cosa.id)).etiqueta == "z"


# --- delete ---------------------------------------------------------------------
async def test_delete_borra_de_verdad(sesion):
    """delete borra de verdad."""
    repo = BaseRepository(sesion, CosaPrueba)
    cosa = await repo.add(CosaPrueba(nombre="n"))
    await repo.delete(cosa)
    assert await repo.get_by_id(cosa.id) is None
    assert await contar_filas(sesion, CosaPrueba.__table__) == 0


# --- get_all / count ------------------------------------------------------------
async def test_tabla_vacia(sesion):
    """Tabla vacía."""
    repo = BaseRepository(sesion, CosaPrueba)
    assert await repo.get_all() == []
    assert await repo.count() == 0


async def test_desplazamiento_y_limite_por_clave_primaria(sesion, sesiones):
    """Desplazamiento y límite: orden por PK aunque se hayan insertado desordenadas."""
    ids = [30, 10, 50, 20, 40]
    await insertar_cosas(sesiones, *({"id": i, "nombre": f"c{i}"} for i in ids))
    repo = BaseRepository(sesion, CosaPrueba)
    pagina = await repo.get_all(offset=2, limit=2)
    assert [c.id for c in pagina] == [30, 40]
    assert [c.id for c in await repo.get_all()] == [10, 20, 30, 40, 50]
    assert await repo.count() == 5


# --- dos repositorios, una sesión -----------------------------------------------
async def test_dos_repositorios_sobre_la_misma_sesion(sesion):
    """Dos repositorios de clases distintas sobre la misma sesión."""
    cosas, detalles = BaseRepository(sesion, CosaPrueba), BaseRepository(sesion, DetallePrueba)
    cosa = await cosas.add(CosaPrueba(nombre="n"))
    await detalles.add(DetallePrueba(cosa_id=cosa.id, texto="t", codigo="k1"))
    await detalles.add(DetallePrueba(cosa_id=cosa.id, texto="u", codigo="k2"))
    assert (await cosas.count(), await detalles.count()) == (1, 2)
    await sesion.rollback()
    assert (await cosas.count(), await detalles.count()) == (0, 0)


# --- _paginar -------------------------------------------------------------------
async def _cinco_cosas(sesiones):
    await insertar_cosas(
        sesiones,
        {"id": 1, "nombre": "a", "etiqueta": "x"},
        {"id": 2, "nombre": "b", "etiqueta": "y"},
        {"id": 3, "nombre": "c", "etiqueta": "x"},
        {"id": 4, "nombre": "d", "etiqueta": "y"},
        {"id": 5, "nombre": "e", "etiqueta": "x"},
    )


async def test_paginar_cuenta_el_total_con_el_filtro(sesion, sesiones):
    """Total con el filtro aplicado."""
    await _cinco_cosas(sesiones)
    pagina = await CosasRepo(sesion).listar_por_etiqueta("x", ParametrosPagina(page=1, size=2))
    assert [c.id for c in pagina.items] == [1, 3]
    assert (pagina.total, pagina.page, pagina.size, pagina.pages) == (3, 1, 2, 2)


async def test_paginar_ultima_pagina_parcial(sesion, sesiones):
    await _cinco_cosas(sesiones)
    pagina = await CosasRepo(sesion).listar_por_etiqueta("x", ParametrosPagina(page=2, size=2))
    assert [c.id for c in pagina.items] == [5]


async def test_paginar_filtro_sin_coincidencias(sesion, sesiones):
    """Filtro sin coincidencias: página vacía con total 0 y pages 1."""
    await _cinco_cosas(sesiones)
    pagina = await CosasRepo(sesion).listar_por_etiqueta("nada", ParametrosPagina(page=1, size=20))
    assert (pagina.items, pagina.total, pagina.pages) == ([], 0, 1)


async def test_paginar_pagina_inexistente_no_pide_los_items(sesion, sesiones, sentencias):
    await _cinco_cosas(sesiones)
    sentencias.clear()
    with pytest.raises(PaginaInexistente) as info:
        await CosasRepo(sesion).listar_por_etiqueta("x", ParametrosPagina(page=3, size=2))
    assert info.value.mensaje == "La página 3 no existe: hay 2"
    assert solo_select(sentencias) == 1


# --- precarga -------------------------------------------------------------------
async def test_relacion_no_precargada_falla_sin_consultar(sesion, sesiones, sentencias):
    """Relación no precargada."""
    await insertar_cosas(sesiones, {"id": 1, "nombre": "a"})
    cosa = await BaseRepository(sesion, CosaPrueba).get_by_id(1)
    antes = len(sentencias)
    with pytest.raises(InvalidRequestError):
        cosa.detalles
    assert len(sentencias) == antes


@pytest.mark.parametrize("cantidad", [1, 5])
async def test_relacion_precargada_por_el_metodo_tiene_consultas_fijas(
    sesion, sesiones, sentencias, cantidad
):
    """Relación precargada por el método: 2 consultas sin importar cuántos detalles haya."""
    await insertar_cosas(sesiones, {"id": 1, "nombre": "a"})
    async with sesiones() as s:
        conexion = await s.connection()
        await conexion.execute(
            insert(DetallePrueba.__table__),
            [{"cosa_id": 1, "texto": "t", "codigo": f"k{i}"} for i in range(cantidad)],
        )
        await s.commit()
    sentencias.clear()
    cosa = await CosasRepo(sesion).get_con_detalles(1)
    assert len(cosa.detalles) == cantidad
    assert solo_select(sentencias) == 2


# --- sin commit -----------------------------------------------------------------
def test_el_repositorio_no_confirma_nunca():
    """Las escrituras sincronizan sin confirmar: el módulo no contiene .commit(."""
    raiz = Path(__file__).resolve().parent.parent
    texto = (raiz / "app" / "core" / "repository.py").read_text(encoding="utf-8")
    assert ".commit(" not in texto


# --- SoftDeleteRepository -------------------------------------------------------
from datetime import datetime, timezone  # noqa: E402

from sqlalchemy import update as sql_update  # noqa: E402

from app.core.repository import SoftDeleteRepository  # noqa: E402


class CosasBorrablesRepo(SoftDeleteRepository[CosaPrueba]):
    def __init__(self, session):
        super().__init__(session, CosaPrueba)

    async def listar_por_etiqueta(self, etiqueta: str, pagina: ParametrosPagina):
        consulta = self._consulta_base().where(CosaPrueba.etiqueta == etiqueta)
        return await self._paginar(consulta, pagina)


async def _dar_de_baja_con_sql(sesiones, id: int) -> None:
    async with sesiones() as s:
        conexion = await s.connection()
        await conexion.execute(
            sql_update(CosaPrueba.__table__)
            .where(CosaPrueba.__table__.c.id == id)
            .values(borrado_en=datetime(2026, 1, 1, tzinfo=timezone.utc))
        )
        await s.commit()


async def test_el_dado_de_baja_deja_de_aparecer(sesion, sesiones):
    """El dado de baja deja de aparecer."""
    await insertar_cosas(
        sesiones, {"id": 1, "nombre": "a"}, {"id": 2, "nombre": "b"}, {"id": 3, "nombre": "c"}
    )
    await _dar_de_baja_con_sql(sesiones, 2)
    repo = SoftDeleteRepository(sesion, CosaPrueba)
    assert [c.id for c in await repo.get_all()] == [1, 3]
    assert await repo.count() == 2
    assert await repo.get_by_id(2) is None
    assert (await repo.get_by_id(1)).nombre == "a"


async def test_modelo_sin_columna_de_baja(sesion):
    """Modelo sin columna de baja."""
    with pytest.raises(TypeError, match="borrado_en"):
        SoftDeleteRepository(sesion, DetallePrueba)


async def test_soft_delete_conserva_la_fila_con_instante_con_zona(sesion):
    """La fila se conserva."""
    repo = SoftDeleteRepository(sesion, CosaPrueba)
    cosa = await repo.add(CosaPrueba(nombre="n", etiqueta="e"))
    await repo.soft_delete(cosa)
    fila = (
        await (await sesion.connection()).execute(
            select(CosaPrueba.__table__.c.nombre, CosaPrueba.__table__.c.borrado_en).where(
                CosaPrueba.__table__.c.id == cosa.id
            )
        )
    ).one()
    assert fila.nombre == "n"
    assert fila.borrado_en.utcoffset() is not None
    assert await repo.get_by_id(cosa.id) is None
    assert await repo.count() == 0


async def test_baja_repetida_conserva_el_primer_instante(sesion):
    """Baja repetida."""
    repo = SoftDeleteRepository(sesion, CosaPrueba)
    cosa = await repo.add(CosaPrueba(nombre="n"))
    await repo.soft_delete(cosa)
    primero = cosa.borrado_en
    await repo.soft_delete(cosa)
    assert cosa.borrado_en == primero


async def test_get_by_id_including_deleted(sesion, sesiones):
    """Entidad dada de baja / Entidad inexistente."""
    await insertar_cosas(sesiones, {"id": 1, "nombre": "a"}, {"id": 2, "nombre": "b"})
    await _dar_de_baja_con_sql(sesiones, 2)
    repo = SoftDeleteRepository(sesion, CosaPrueba)
    baja = await repo.get_by_id_including_deleted(2)
    assert baja is not None and baja.borrado_en is not None
    assert (await repo.get_by_id_including_deleted(1)).borrado_en is None
    assert await repo.get_by_id_including_deleted(999) is None


async def test_paginado_con_borrado_logico(sesion, sesiones):
    """Paginado con borrado lógico: la dada de baja no aparece ni cuenta en total."""
    await _cinco_cosas(sesiones)
    await _dar_de_baja_con_sql(sesiones, 3)
    pagina = await CosasBorrablesRepo(sesion).listar_por_etiqueta(
        "x", ParametrosPagina(page=1, size=2)
    )
    assert [c.id for c in pagina.items] == [1, 5]
    assert (pagina.total, pagina.pages) == (2, 1)


async def test_get_by_id_no_devuelve_del_identity_map_a_la_dada_de_baja(sesion):
    """La baja hecha en la misma sesión tampoco se ve (por eso get_by_id no usa session.get)."""
    repo = SoftDeleteRepository(sesion, CosaPrueba)
    cosa = await repo.add(CosaPrueba(nombre="n"))
    await repo.soft_delete(cosa)
    assert await repo.get_by_id(cosa.id) is None
