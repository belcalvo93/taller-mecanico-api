"""CH-08 grupo 1: catálogo de estados de sólo lectura y GET /estados-orden (C-17, RN-19)."""
import inspect

from fastapi import FastAPI
from sqlalchemy import text

import main
import seed
from app.core.repository import BaseRepository
from app.modules.ordenes.repository import EstadoOrdenRepository
from app.modules.ordenes.schemas import EstadoOrdenCodigo
from tests.ordenes_comun import ADMIN, LAURA, sesion


async def test_listar_por_posicion_devuelve_los_cuatro_del_seed(sembrada, sesiones):
    async with sesiones() as s:
        estados = await EstadoOrdenRepository(s).listar_por_posicion()
    assert [(e.codigo, e.posicion, e.es_final) for e in estados] == [
        ("PENDIENTE", 1, False), ("EN_REPARACION", 2, False),
        ("TERMINADA", 3, True), ("CANCELADA", 4, True),
    ]


async def test_get_trae_uno_y_devuelve_none_si_no_existe(sembrada, sesiones):
    async with sesiones() as s:
        repo = EstadoOrdenRepository(s)
        assert (await repo.get("PENDIENTE")).descripcion.startswith("Ingresada")
        assert (await repo.get("TERMINADA")).es_final is True
        assert await repo.get("NO_EXISTE") is None


def test_el_repositorio_es_de_solo_lectura_y_no_hereda_del_generico():
    assert not issubclass(EstadoOrdenRepository, BaseRepository)
    for escritura in ("add", "update", "delete", "soft_delete"):
        assert not hasattr(EstadoOrdenRepository, escritura), escritura
    assert "session" in inspect.signature(EstadoOrdenRepository.__init__).parameters


def test_el_enum_coincide_con_los_codigos_del_seed():
    assert {e.value for e in EstadoOrdenCodigo} == {c[0] for c in seed.CATALOGO}
    assert len(EstadoOrdenCodigo) == 4


async def test_catalogo_para_admin_y_para_un_cliente(sembrada, client):
    for usuario in (ADMIN, LAURA):
        r = await client.get("/estados-orden", headers=await sesion(client, usuario))
        assert r.status_code == 200
        cuerpo = r.json()
        assert [e["codigo"] for e in cuerpo] == ["PENDIENTE", "EN_REPARACION", "TERMINADA", "CANCELADA"]
        assert [e["posicion"] for e in cuerpo] == [1, 2, 3, 4]
        assert [e["es_final"] for e in cuerpo] == [False, False, True, True]
        assert set(cuerpo[0]) == {"codigo", "descripcion", "posicion", "es_final"}


async def test_catalogo_sin_cookie_401(sembrada, client):
    assert (await client.get("/estados-orden")).status_code == 401


async def test_no_hay_rutas_de_escritura_del_catalogo(sembrada, client):
    h = await sesion(client, ADMIN)
    for metodo in ("POST", "PUT", "PATCH", "DELETE"):
        r = await client.request(metodo, "/estados-orden", headers=h)
        assert r.status_code == 405, metodo
    async with sembrada.connect() as c:
        assert (await c.execute(text("SELECT count(*) FROM estado_orden"))).scalar() == 4


def _rutas(grupo) -> set[tuple[str, str]]:
    app = FastAPI()
    app.include_router(grupo)
    return {(m.upper(), r) for r, ops in app.openapi()["paths"].items() for m in ops}


def test_la_ruta_esta_en_el_grupo_protegido_y_no_en_el_abierto():
    assert ("GET", "/estados-orden") in _rutas(main.rutas_protegidas)
    assert "/estados-orden" not in {r for _, r in _rutas(main.rutas_abiertas)}
