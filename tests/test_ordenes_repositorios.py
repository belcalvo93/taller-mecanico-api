"""CH-08 grupo 3: repositorios de órdenes y Unit of Work del módulo.

Base sembrada: orden 1 PENDIENTE (vehículo 1, de Laura; FIL-001x1 y ACE-530x4) y
orden 2 EN_REPARACION (vehículo 3, de Jorge, mecánico 4; BUJ-100x4).
"""
import pytest
from sqlalchemy import func, text
from sqlmodel import select

from app.core.paginacion import PaginaInexistente, ParametrosPagina
from app.core.repository import BaseRepository, SoftDeleteRepository
from app.modules.clientes.repository import VehiculoRepository
from app.modules.ordenes.models import HistorialEstadoOrden
from app.modules.ordenes.repository import (
    EstadoOrdenRepository,
    HistorialEstadoOrdenRepository,
    OrdenRepository,
)
from app.modules.ordenes.unit_of_work import OrdenesUnitOfWork, get_ordenes_uow
from app.modules.repuestos.models import Repuesto
from app.modules.repuestos.repository import RepuestoRepository
from app.modules.usuarios.repository import AsignacionRolRepository
from tests.ordenes_comun import crear_orden


def pag(page=1, size=20):
    return ParametrosPagina(page=page, size=size)


# --- 3.1 get_detalle --------------------------------------------------------------------

async def test_get_detalle_trae_todo_sin_tocar_relaciones_perezosas(sembrada, sesiones):
    async with sesiones() as s:
        orden = await OrdenRepository(s).get_detalle(2)
    assert orden.vehiculo.patente == "AD789GH"
    assert orden.vehiculo.cliente.nombre == "Jorge Gómez"
    assert [(i.cantidad, i.repuesto.codigo) for i in orden.items] == [(4, "BUJ-100")]
    assert [(h.desde_estado, h.hasta_estado) for h in orden.historial] == [
        (None, "PENDIENTE"), ("PENDIENTE", "EN_REPARACION")]


async def test_get_detalle_inexistente_es_none(sembrada, sesiones):
    async with sesiones() as s:
        assert await OrdenRepository(s).get_detalle(999) is None


# --- 3.2 sin N+1 -------------------------------------------------------------------------

async def _sentencias_del_detalle(sesiones, sentencias, orden_id):
    async with sesiones() as s:
        sentencias.clear()
        orden = await OrdenRepository(s).get_detalle(orden_id)
        for i in orden.items:
            _ = i.repuesto.codigo
        _ = orden.vehiculo.cliente.nombre, list(orden.historial)
        return len(sentencias)


async def test_get_detalle_misma_cantidad_de_sentencias_con_2_y_4_items(sembrada, sesiones, sentencias):
    o2 = await crear_orden(sembrada, 1, [1, 2], lineas_historial=1)
    o4 = await crear_orden(sembrada, 1, [1, 2, 3, 4], lineas_historial=1)
    n2 = await _sentencias_del_detalle(sesiones, sentencias, o2)
    n4 = await _sentencias_del_detalle(sesiones, sentencias, o4)
    assert n2 == n4 == 3


async def test_get_detalle_misma_cantidad_con_historial_de_1_y_de_3_lineas(sembrada, sesiones, sentencias):
    a = await crear_orden(sembrada, 1, [1, 2], lineas_historial=1)
    b = await crear_orden(sembrada, 1, [1, 2], lineas_historial=3)
    na = await _sentencias_del_detalle(sesiones, sentencias, a)
    nb = await _sentencias_del_detalle(sesiones, sentencias, b)
    assert na == nb == 3


# --- 3.3 populate_existing -----------------------------------------------------------------

async def test_get_detalle_tras_modificar_en_la_misma_sesion_devuelve_lo_nuevo(sembrada, sesiones):
    async with sesiones() as s:
        repo = OrdenRepository(s)
        orden = await repo.get_para_transicion(1)  # cargada con ítems, sin historial
        orden.estado = "EN_REPARACION"
        await HistorialEstadoOrdenRepository(s).add(HistorialEstadoOrden(
            orden_id=1, desde_estado="PENDIENTE", hasta_estado="EN_REPARACION", usuario_id=5))
        detalle = await repo.get_detalle(1)
        assert detalle.estado == "EN_REPARACION"
        assert [(h.desde_estado, h.hasta_estado) for h in detalle.historial] == [
            (None, "PENDIENTE"), ("PENDIENTE", "EN_REPARACION")]
        assert sorted(i.repuesto.codigo for i in detalle.items) == ["ACE-530", "FIL-001"]


# --- 3.4 listar -------------------------------------------------------------------------------

async def test_listar_sin_filtro_trae_las_dos_por_id(sembrada, sesiones):
    async with sesiones() as s:
        p = await OrdenRepository(s).listar(None, pag())
    assert [o.id for o in p.items] == [1, 2]
    assert (p.total, p.page, p.size, p.pages) == (2, 1, 20, 1)
    assert p.items[0].vehiculo.cliente.nombre == "Laura Cliente"  # precargado


async def test_listar_con_estado(sembrada, sesiones):
    async with sesiones() as s:
        repo = OrdenRepository(s)
        pendientes = await repo.listar("PENDIENTE", pag())
        en_reparacion = await repo.listar("EN_REPARACION", pag())
        terminadas = await repo.listar("TERMINADA", pag())
    assert ([o.id for o in pendientes.items], pendientes.total) == ([1], 1)
    assert ([o.id for o in en_reparacion.items], en_reparacion.total) == ([2], 1)
    assert (terminadas.items, terminadas.total, terminadas.pages) == ([], 0, 1)


async def test_listar_pagina_inexistente(sembrada, sesiones):
    async with sesiones() as s:
        repo = OrdenRepository(s)
        with pytest.raises(PaginaInexistente):
            await repo.listar(None, pag(page=3, size=1))
        assert [o.id for o in (await repo.listar(None, pag(page=2, size=1))).items] == [2]


# --- 3.5 listar_de_usuario ------------------------------------------------------------------

async def test_listar_de_usuario(sembrada, sesiones):
    async with sesiones() as s:
        repo = OrdenRepository(s)
        laura = await repo.listar_de_usuario(6, pag())
        recepcion = await repo.listar_de_usuario(3, pag())
    assert [o.id for o in laura.items] == [1] and laura.total == 1
    assert laura.items[0].vehiculo.cliente.nombre == "Laura Cliente"
    assert (recepcion.items, recepcion.total, recepcion.pages) == ([], 0, 1)


async def test_listar_de_usuario_incluye_ordenes_de_vehiculos_dados_de_baja(sembrada, sesiones):
    nueva = await crear_orden(sembrada, 2, [1])
    async with sembrada.begin() as c:
        await c.execute(text("UPDATE vehiculo SET borrado_en = now() WHERE id = 2"))
    async with sesiones() as s:
        p = await OrdenRepository(s).listar_de_usuario(6, pag())
    assert [o.id for o in p.items] == [1, nueva]


# --- 3.6 get_para_transicion ----------------------------------------------------------------

async def test_get_para_transicion_precarga_y_bloquea(sembrada, sesiones, sentencias):
    async with sesiones() as s:
        sentencias.clear()
        orden = await OrdenRepository(s).get_para_transicion(1)
        assert orden.vehiculo.cliente.usuario_id == 6
        assert sorted(i.repuesto_id for i in orden.items) == [1, 4]
        assert any("FOR UPDATE" in q.upper() for q in sentencias)
        assert any(q.upper().rstrip().endswith("OF ORDEN_TRABAJO") for q in sentencias)


async def test_get_para_transicion_inexistente_es_none(sembrada, sesiones):
    async with sesiones() as s:
        assert await OrdenRepository(s).get_para_transicion(999) is None


# --- 3.7 historial -----------------------------------------------------------------------------

async def test_historial_add_hace_flush_sin_confirmar(sembrada, sesiones):
    cuenta = select(func.count()).select_from(HistorialEstadoOrden).where(HistorialEstadoOrden.orden_id == 1)
    async with sesiones() as s, sesiones() as otra:
        h = await HistorialEstadoOrdenRepository(s).add(HistorialEstadoOrden(
            orden_id=1, desde_estado="PENDIENTE", hasta_estado="CANCELADA", usuario_id=6))
        assert h.id is not None  # flush
        assert (await otra.exec(cuenta)).one() == 1  # la otra sesión aún no la ve
        await s.commit()
        await otra.rollback()
        assert (await otra.exec(cuenta)).one() == 2


def test_historial_repository_es_un_base_repository():
    assert issubclass(HistorialEstadoOrdenRepository, BaseRepository)


# --- 3.8 UoW ---------------------------------------------------------------------------------------

async def test_el_uow_comparte_la_sesion_y_compone_los_repositorios(sembrada, sesiones):
    async with sesiones() as s:
        uow = OrdenesUnitOfWork(s)
        assert isinstance(uow.ordenes, OrdenRepository)
        assert isinstance(uow.historial, HistorialEstadoOrdenRepository)
        assert isinstance(uow.estados, EstadoOrdenRepository)
        assert isinstance(uow.vehiculos, VehiculoRepository)
        assert isinstance(uow.roles, AsignacionRolRepository)
        # el repositorio real de CH-07, con el punto único de stock (design D2)
        assert isinstance(uow.repuestos, RepuestoRepository) and uow.repuestos.modelo is Repuesto
        assert isinstance(uow.repuestos, SoftDeleteRepository)
        for repo in (uow.ordenes, uow.historial, uow.estados, uow.vehiculos, uow.roles, uow.repuestos):
            assert repo.session is s
        assert uow.session is s


async def test_get_ordenes_uow_lo_construye_con_la_sesion(sembrada, sesiones):
    async with sesiones() as s:
        assert get_ordenes_uow(s).session is s
