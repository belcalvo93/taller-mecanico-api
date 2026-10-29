"""CH-07: repositorios y Unit of Work del módulo repuestos, contra taller_test sembrada.

Datos del seed: repuestos 1 FIL-001 (stock 10), 2 FRE-010 (stock 4), 3 BUJ-100 (stock 2,
figura en la orden 2 EN_REPARACION) y 4 ACE-530 (stock 20). Cada uno tiene un movimiento
"Stock inicial"; el 1 además tiene un cambio de precio (8000 -> 8500). Usuario 1 = admin.
"""
from decimal import Decimal

import pytest

from app.core.database import crear_fabrica_sesiones
from app.core.paginacion import PaginaInexistente, ParametrosPagina
from app.core.repository import SoftDeleteRepository
from app.modules.repuestos.models import HistorialPrecio, MovimientoStock, Repuesto
from app.modules.repuestos.repository import (
    HistorialPrecioRepository,
    MovimientoStockRepository,
    RepuestoRepository,
    StockInsuficiente,
)
from app.modules.repuestos.unit_of_work import RepuestosUnitOfWork, get_repuestos_uow

ADMIN = 1


@pytest.fixture
async def sesion(sembrada):
    async with crear_fabrica_sesiones(sembrada)() as s:
        yield s
        await s.rollback()


# --- RepuestoRepository: baja lógica y stock bloqueado (1.1) ---------------------------

async def test_repuesto_repository_es_soft_delete_de_repuesto(sesion):
    repo = RepuestoRepository(sesion)
    assert isinstance(repo, SoftDeleteRepository) and repo.modelo is Repuesto


async def test_get_by_id_excluye_los_dados_de_baja_y_including_deleted_los_ve(sesion):
    repo = RepuestoRepository(sesion)
    await repo.soft_delete(await repo.get_by_id(3))
    assert await repo.get_by_id(3) is None
    assert (await repo.get_by_id_including_deleted(3)).codigo == "BUJ-100"
    assert (await repo.get_by_id(1)).codigo == "FIL-001"


async def test_update_rechaza_stock_y_no_toca_nada(sesion):
    repo = RepuestoRepository(sesion)
    repuesto = await repo.get_by_id(1)
    with pytest.raises(ValueError, match="mover_stock"):
        await repo.update(repuesto, {"stock": 99})
    assert repuesto.stock == 10


async def test_update_rechaza_stock_aunque_venga_con_otros_campos(sesion):
    repo = RepuestoRepository(sesion)
    repuesto = await repo.get_by_id(2)
    with pytest.raises(ValueError):
        await repo.update(repuesto, {"descripcion": "Otra", "stock": 1})
    assert repuesto.descripcion == "Pastillas de freno delanteras"


async def test_update_sigue_aplicando_descripcion_y_precio(sesion):
    repo = RepuestoRepository(sesion)
    repuesto = await repo.get_by_id(4)
    await repo.update(repuesto, {"descripcion": "Aceite sintético 5W30"})
    assert (await repo.get_by_id(4)).descripcion == "Aceite sintético 5W30"


# --- RepuestoRepository.listar (1.2) ---------------------------------------------------------

async def test_listar_sin_filtro_trae_los_4_vigentes_por_id(sesion):
    pagina = await RepuestoRepository(sesion).listar(None, ParametrosPagina())
    assert [r.id for r in pagina.items] == [1, 2, 3, 4]
    assert (pagina.total, pagina.page, pagina.size, pagina.pages) == (4, 1, 20, 1)


@pytest.mark.parametrize("q", ["filtro", "FILTRO", "  Filtro  "])
async def test_listar_busca_en_descripcion_sin_distinguir_mayusculas(sesion, q):
    pagina = await RepuestoRepository(sesion).listar(q, ParametrosPagina())
    assert [r.codigo for r in pagina.items] == ["FIL-001"]
    assert pagina.total == 1


async def test_listar_con_q_en_blanco_no_filtra(sesion):
    pagina = await RepuestoRepository(sesion).listar("   ", ParametrosPagina())
    assert pagina.total == 4


async def test_listar_con_comillas_busca_literal_y_no_rompe(sesion):
    pagina = await RepuestoRepository(sesion).listar("' OR '1'='1", ParametrosPagina())
    assert pagina.items == []
    assert (pagina.total, pagina.page, pagina.size, pagina.pages) == (0, 1, 20, 1)


async def test_listar_no_ve_los_dados_de_baja(sesion):
    repo = RepuestoRepository(sesion)
    await repo.soft_delete(await repo.get_by_id(2))
    pagina = await repo.listar(None, ParametrosPagina())
    assert [r.id for r in pagina.items] == [1, 3, 4]
    assert pagina.total == 3


async def test_listar_el_total_cuenta_con_los_mismos_filtros(sesion):
    # "de" aparece en "Filtro de aceite", "Pastillas de freno delanteras", "Bujía de encendido"
    pagina = await RepuestoRepository(sesion).listar("de", ParametrosPagina(page=2, size=2))
    assert pagina.total == 3 and pagina.pages == 2
    assert [r.codigo for r in pagina.items] == ["BUJ-100"]


async def test_listar_pagina_inexistente_lanza_error(sesion):
    with pytest.raises(PaginaInexistente):
        await RepuestoRepository(sesion).listar(None, ParametrosPagina(page=2))


# --- Tablas de sólo agregado (1.3, RN-15) ------------------------------------------------------

async def test_movimientos_listar_por_repuesto_en_orden_de_id(sesion):
    repo = MovimientoStockRepository(sesion)
    await repo.add(MovimientoStock(repuesto_id=1, usuario_id=ADMIN, cantidad=5, motivo="Compra"))
    await repo.add(MovimientoStock(repuesto_id=2, usuario_id=ADMIN, cantidad=1, motivo="Otro repuesto"))
    await repo.add(MovimientoStock(repuesto_id=1, usuario_id=ADMIN, cantidad=-2, motivo="Ajuste"))
    movimientos = await repo.listar_por_repuesto(1)
    assert [(m.motivo, m.cantidad) for m in movimientos] == [
        ("Stock inicial", 10), ("Compra", 5), ("Ajuste", -2),
    ]
    assert movimientos == sorted(movimientos, key=lambda m: m.id)


async def test_movimientos_de_un_repuesto_sin_otros_movimientos(sesion):
    movimientos = await MovimientoStockRepository(sesion).listar_por_repuesto(3)
    assert [(m.motivo, m.cantidad) for m in movimientos] == [("Stock inicial", 2)]


async def test_historial_precios_listar_por_repuesto_en_orden_de_id(sesion):
    repo = HistorialPrecioRepository(sesion)
    await repo.add(HistorialPrecio(
        repuesto_id=1, usuario_id=ADMIN, precio_anterior=Decimal("8500.00"), precio_nuevo=Decimal("9000.00"),
    ))
    cambios = await repo.listar_por_repuesto(1)
    assert [(c.precio_anterior, c.precio_nuevo) for c in cambios] == [
        (Decimal("8000.00"), Decimal("8500.00")), (Decimal("8500.00"), Decimal("9000.00")),
    ]


async def test_historial_precios_de_un_repuesto_sin_cambios_es_lista_vacia(sesion):
    assert await HistorialPrecioRepository(sesion).listar_por_repuesto(2) == []


@pytest.mark.parametrize("repo_cls", [MovimientoStockRepository, HistorialPrecioRepository])
async def test_tablas_de_solo_agregado_no_se_actualizan_ni_se_borran(sesion, repo_cls):
    repo = repo_cls(sesion)
    fila = (await repo.listar_por_repuesto(1))[0]
    with pytest.raises(RuntimeError, match="sólo agregado"):
        await repo.update(fila, {"repuesto_id": 2})
    with pytest.raises(RuntimeError, match="sólo agregado"):
        await repo.delete(fila)


# --- mover_stock: punto único de escritura (1.4, RN-14, DD-14) ---------------------------

async def _stock_en_la_base(motor, repuesto_id: int) -> int:
    # sesión aparte: sólo ve lo que se confirmó
    async with crear_fabrica_sesiones(motor)() as otra:
        return (await RepuestoRepository(otra).get_by_id(repuesto_id)).stock


async def test_mover_stock_positivo_suma_y_agrega_el_movimiento(sesion):
    repo = RepuestoRepository(sesion)
    repuesto = await repo.get_by_id(3)
    movimiento = await repo.mover_stock(repuesto, 5, motivo="Compra a proveedor", usuario_id=ADMIN)
    assert repuesto.stock == 7
    assert movimiento.id is not None
    assert (movimiento.repuesto_id, movimiento.cantidad) == (3, 5)
    assert (movimiento.motivo, movimiento.usuario_id, movimiento.orden_id) == ("Compra a proveedor", ADMIN, None)
    movimientos = await MovimientoStockRepository(sesion).listar_por_repuesto(3)
    assert [m.cantidad for m in movimientos] == [2, 5]


async def test_mover_stock_negativo_descuenta_y_guarda_la_orden(sesion):
    repo = RepuestoRepository(sesion)
    repuesto = await repo.get_by_id(1)
    movimiento = await repo.mover_stock(repuesto, -4, motivo="Orden terminada", usuario_id=ADMIN, orden_id=2)
    assert repuesto.stock == 6
    assert (movimiento.cantidad, movimiento.orden_id) == (-4, 2)


async def test_mover_stock_puede_dejar_el_stock_en_cero(sesion):
    repo = RepuestoRepository(sesion)
    repuesto = await repo.get_by_id(3)
    await repo.mover_stock(repuesto, -2, motivo="Orden terminada", usuario_id=ADMIN)
    assert repuesto.stock == 0


async def test_mover_stock_insuficiente_lanza_y_no_deja_nada(sesion):
    repo = RepuestoRepository(sesion)
    repuesto = await repo.get_by_id(3)
    with pytest.raises(StockInsuficiente) as exc:
        await repo.mover_stock(repuesto, -5, motivo="Orden terminada", usuario_id=ADMIN)
    assert (exc.value.codigo, exc.value.disponible, exc.value.pedido) == ("BUJ-100", 2, 5)
    assert repuesto.stock == 2
    assert len(await MovimientoStockRepository(sesion).listar_por_repuesto(3)) == 1


async def test_mover_stock_con_cantidad_cero_es_error_de_programacion(sesion):
    repo = RepuestoRepository(sesion)
    repuesto = await repo.get_by_id(1)
    with pytest.raises(ValueError, match="cero"):
        await repo.mover_stock(repuesto, 0, motivo="Nada", usuario_id=ADMIN)
    assert repuesto.stock == 10


async def test_mover_stock_no_confirma_nada_por_su_cuenta(sesion, sembrada):
    repo = RepuestoRepository(sesion)
    repuesto = await repo.get_by_id(1)
    await repo.mover_stock(repuesto, 5, motivo="Compra", usuario_id=ADMIN)
    assert await _stock_en_la_base(sembrada, 1) == 10  # sin commit, la base no se enteró
    await sesion.rollback()
    assert await _stock_en_la_base(sembrada, 1) == 10


async def test_mover_stock_descuenta_de_un_repuesto_dado_de_baja_leido_con_including_deleted(sesion):
    # DD-14: una orden abierta con un repuesto dado de baja igual lo descuenta al terminar
    repo = RepuestoRepository(sesion)
    await repo.soft_delete(await repo.get_by_id(3))
    repuesto = await repo.get_by_id_including_deleted(3)
    await repo.mover_stock(repuesto, -2, motivo="Orden terminada", usuario_id=ADMIN, orden_id=2)
    assert repuesto.stock == 0 and repuesto.borrado_en is not None


# --- RepuestosUnitOfWork (1.5) ---------------------------------------------------------------

async def test_unit_of_work_compone_los_tres_repositorios_con_la_misma_sesion(sesion):
    uow = RepuestosUnitOfWork(sesion)
    assert isinstance(uow.repuestos, RepuestoRepository)
    assert isinstance(uow.movimientos, MovimientoStockRepository)
    assert isinstance(uow.historial_precios, HistorialPrecioRepository)
    assert uow.repuestos.session is uow.movimientos.session is uow.historial_precios.session is sesion


async def test_get_repuestos_uow_construye_el_uow_con_la_sesion_recibida(sesion):
    assert get_repuestos_uow(sesion).session is sesion


async def test_mover_stock_dentro_del_uow_confirma_al_salir(sembrada):
    async with crear_fabrica_sesiones(sembrada)() as s:
        uow = RepuestosUnitOfWork(s)
        async with uow:
            repuesto = await uow.repuestos.get_by_id(3)
            await uow.repuestos.mover_stock(repuesto, 5, motivo="Compra", usuario_id=ADMIN)
    assert await _stock_en_la_base(sembrada, 3) == 7


async def test_si_el_bloque_falla_despues_de_mover_stock_se_revierte_todo(sembrada):
    async with crear_fabrica_sesiones(sembrada)() as s:
        uow = RepuestosUnitOfWork(s)
        with pytest.raises(RuntimeError):
            async with uow:
                repuesto = await uow.repuestos.get_by_id(3)
                await uow.repuestos.mover_stock(repuesto, 5, motivo="Compra", usuario_id=ADMIN)
                raise RuntimeError("falla posterior")
    assert await _stock_en_la_base(sembrada, 3) == 2
    async with crear_fabrica_sesiones(sembrada)() as otra:
        assert len(await MovimientoStockRepository(otra).listar_por_repuesto(3)) == 1


async def test_descuento_de_dos_repuestos_es_todo_o_nada(sembrada):
    # como terminar una orden con dos ítems y falta stock en el segundo (C-11)
    async with crear_fabrica_sesiones(sembrada)() as s:
        uow = RepuestosUnitOfWork(s)
        with pytest.raises(StockInsuficiente):
            async with uow:
                filtro = await uow.repuestos.get_by_id(1)
                bujia = await uow.repuestos.get_by_id(3)
                await uow.repuestos.mover_stock(filtro, -4, motivo="Orden terminada", usuario_id=ADMIN, orden_id=2)
                await uow.repuestos.mover_stock(bujia, -4, motivo="Orden terminada", usuario_id=ADMIN, orden_id=2)
    assert await _stock_en_la_base(sembrada, 1) == 10
    assert await _stock_en_la_base(sembrada, 3) == 2
