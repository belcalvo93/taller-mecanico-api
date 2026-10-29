"""CH-07: servicio de repuestos sobre el UoW real y taller_test sembrada.

Seed: repuestos 1 FIL-001 ($8500, stock 10, un cambio de precio 8000 -> 8500), 2 FRE-010
(stock 4), 3 BUJ-100 (stock 2, está en la orden 2 EN_REPARACION) y 4 ACE-530 (stock 20).
"""
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.core.database import crear_fabrica_sesiones
from app.core.paginacion import ParametrosPagina
from app.modules.repuestos import service
from app.modules.repuestos.schemas import ReposicionCrear, RepuestoActualizar, RepuestoCrear
from app.modules.repuestos.unit_of_work import RepuestosUnitOfWork

ADMIN = 1


@pytest.fixture
async def uow(sembrada):
    async with crear_fabrica_sesiones(sembrada)() as s:
        yield RepuestosUnitOfWork(s)


async def _filas(motor, sql: str, **params):
    async with motor.connect() as c:
        return (await c.execute(text(sql), params)).all()


def _nuevo(**cambios) -> RepuestoCrear:
    base = {"codigo": "FIL-010", "descripcion": "Filtro de aire", "precio": "5500.00", "stock_inicial": 15}
    return RepuestoCrear(**{**base, **cambios})


# --- crear_repuesto (3.1) --------------------------------------------------------------------

async def test_crear_con_stock_inicial_registra_el_movimiento(uow, sembrada):
    repuesto = await service.crear_repuesto(uow, _nuevo(), ADMIN)
    assert (repuesto.id, repuesto.codigo, repuesto.stock) == (5, "FIL-010", 15)
    movimientos = await _filas(
        sembrada, "SELECT cantidad, motivo, orden_id, usuario_id FROM movimiento_stock WHERE repuesto_id = 5"
    )
    assert movimientos == [(15, "Stock inicial", None, ADMIN)]


async def test_crear_con_stock_inicial_cero_no_inserta_movimiento(uow, sembrada):
    repuesto = await service.crear_repuesto(uow, _nuevo(codigo="SIN-001", stock_inicial=0), ADMIN)
    assert repuesto.stock == 0
    assert await _filas(sembrada, "SELECT id FROM movimiento_stock WHERE repuesto_id = :id", id=repuesto.id) == []


@pytest.mark.parametrize("stock_inicial", [0, 7])
async def test_codigo_vigente_repetido_lanza_y_no_deja_filas(uow, sembrada, stock_inicial):
    with pytest.raises(service.CodigoRepuestoDuplicado):
        await service.crear_repuesto(uow, _nuevo(codigo="FIL-001", stock_inicial=stock_inicial), ADMIN)
    assert (await _filas(sembrada, "SELECT count(*) FROM repuesto"))[0][0] == 4
    assert (await _filas(sembrada, "SELECT count(*) FROM movimiento_stock"))[0][0] == 4


async def test_codigo_de_un_repuesto_dado_de_baja_se_puede_reusar(uow):
    await service.dar_de_baja_repuesto(uow, 1)
    repuesto = await service.crear_repuesto(uow, _nuevo(codigo="FIL-001", stock_inicial=0), ADMIN)
    assert repuesto.id == 5 and repuesto.borrado_en is None


async def test_otro_error_de_integridad_no_se_traduce_a_codigo_duplicado(uow):
    # un usuario inexistente rompe la FK del movimiento: eso no es "código repetido"
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await service.crear_repuesto(uow, _nuevo(codigo="FK-001"), 9999)


# --- actualizar_repuesto (3.2) ---------------------------------------------------------------

async def test_cambio_de_precio_inserta_historial_en_la_misma_transaccion(uow, sembrada):
    repuesto = await service.actualizar_repuesto(uow, 1, RepuestoActualizar(precio="9500.00"), ADMIN)
    assert repuesto.precio == Decimal("9500.00")
    cambios = await _filas(
        sembrada,
        "SELECT precio_anterior, precio_nuevo, usuario_id FROM historial_precio_repuesto "
        "WHERE repuesto_id = 1 ORDER BY id",
    )
    assert cambios == [
        (Decimal("8000.00"), Decimal("8500.00"), ADMIN),
        (Decimal("8500.00"), Decimal("9500.00"), ADMIN),
    ]


async def test_cambio_de_precio_y_descripcion_juntos(uow, sembrada):
    datos = RepuestoActualizar(descripcion="Filtro sintético", precio="8700.00")
    repuesto = await service.actualizar_repuesto(uow, 1, datos, ADMIN)
    assert (repuesto.descripcion, repuesto.precio) == ("Filtro sintético", Decimal("8700.00"))
    assert (await _filas(sembrada, "SELECT count(*) FROM historial_precio_repuesto"))[0][0] == 2


async def test_cambio_solo_de_descripcion_no_toca_el_historial(uow, sembrada):
    repuesto = await service.actualizar_repuesto(uow, 1, RepuestoActualizar(descripcion="Filtro sintético"), ADMIN)
    assert repuesto.descripcion == "Filtro sintético"
    assert (await _filas(sembrada, "SELECT count(*) FROM historial_precio_repuesto"))[0][0] == 1


@pytest.mark.parametrize("precio", ["8500.00", "8500", 8500])
async def test_mismo_precio_no_genera_historial(uow, sembrada, precio):
    repuesto = await service.actualizar_repuesto(uow, 1, RepuestoActualizar(precio=precio), ADMIN)
    assert repuesto.precio == Decimal("8500.00")
    assert (await _filas(sembrada, "SELECT count(*) FROM historial_precio_repuesto"))[0][0] == 1


async def test_actualizar_cuerpo_vacio_no_cambia_nada(uow, sembrada):
    repuesto = await service.actualizar_repuesto(uow, 1, RepuestoActualizar(), ADMIN)
    assert (repuesto.descripcion, repuesto.precio, repuesto.stock) == ("Filtro de aceite", Decimal("8500.00"), 10)


async def test_actualizar_nunca_toca_el_stock(uow):
    repuesto = await service.actualizar_repuesto(uow, 1, RepuestoActualizar(precio="1.00"), ADMIN)
    assert repuesto.stock == 10


@pytest.mark.parametrize("repuesto_id", [999, 3])
async def test_actualizar_inexistente_o_dado_de_baja_lanza(uow, repuesto_id):
    if repuesto_id == 3:
        await service.dar_de_baja_repuesto(uow, 3)
    with pytest.raises(service.RepuestoNoEncontrado):
        await service.actualizar_repuesto(uow, repuesto_id, RepuestoActualizar(precio="1.00"), ADMIN)


# --- baja, reposición y consultas (3.3) -------------------------------------------------------

async def test_baja_de_repuesto_en_orden_abierta_no_da_error(uow, sembrada):
    await service.dar_de_baja_repuesto(uow, 3)  # el 3 está en la orden 2 EN_REPARACION (DD-14)
    filas = await _filas(sembrada, "SELECT borrado_en IS NOT NULL FROM repuesto WHERE id = 3")
    assert filas == [(True,)]
    assert (await _filas(sembrada, "SELECT count(*) FROM item_orden WHERE repuesto_id = 3"))[0][0] == 1


@pytest.mark.parametrize("repuesto_id", [999, 3])
async def test_baja_de_inexistente_o_ya_dado_de_baja_lanza(uow, repuesto_id):
    if repuesto_id == 3:
        await service.dar_de_baja_repuesto(uow, 3)
    with pytest.raises(service.RepuestoNoEncontrado):
        await service.dar_de_baja_repuesto(uow, repuesto_id)


async def test_reponer_suma_stock_y_registra_el_movimiento(uow, sembrada):
    datos = ReposicionCrear(cantidad=5, motivo="Compra a proveedor")
    repuesto = await service.reponer_stock(uow, 3, datos, ADMIN)
    assert repuesto.stock == 7
    movimientos = await _filas(
        sembrada, "SELECT cantidad, motivo, orden_id, usuario_id FROM movimiento_stock WHERE repuesto_id = 3 ORDER BY id"
    )
    assert movimientos[-1] == (5, "Compra a proveedor", None, ADMIN)


async def test_reponer_sin_motivo_usa_el_de_por_defecto(uow, sembrada):
    repuesto = await service.reponer_stock(uow, 1, ReposicionCrear(cantidad=2), ADMIN)
    assert repuesto.stock == 12
    ultimo = (await _filas(sembrada, "SELECT motivo FROM movimiento_stock WHERE repuesto_id = 1 ORDER BY id"))[-1]
    assert ultimo == ("Reposición",)


@pytest.mark.parametrize("repuesto_id", [999, 3])
async def test_reponer_inexistente_o_dado_de_baja_lanza(uow, sembrada, repuesto_id):
    if repuesto_id == 3:
        await service.dar_de_baja_repuesto(uow, 3)
    with pytest.raises(service.RepuestoNoEncontrado):
        await service.reponer_stock(uow, repuesto_id, ReposicionCrear(cantidad=1), ADMIN)
    assert (await _filas(sembrada, "SELECT count(*) FROM movimiento_stock"))[0][0] == 4


async def test_obtener_repuesto_vigente(uow):
    assert (await service.obtener_repuesto(uow, 1)).codigo == "FIL-001"


async def test_listar_repuestos_filtra_y_pagina(uow):
    pagina = await service.listar_repuestos(uow, "aceite", ParametrosPagina())
    assert sorted(r.codigo for r in pagina.items) == ["ACE-530", "FIL-001"]


async def test_movimientos_y_precios_de_un_repuesto_del_seed(uow):
    movimientos = await service.listar_movimientos(uow, 1)
    assert [(m.cantidad, m.motivo) for m in movimientos] == [(10, "Stock inicial")]
    precios = await service.listar_precios(uow, 1)
    assert [(p.precio_anterior, p.precio_nuevo) for p in precios] == [(Decimal("8000.00"), Decimal("8500.00"))]


@pytest.mark.parametrize(
    "consulta", ["obtener_repuesto", "listar_movimientos", "listar_precios"]
)
@pytest.mark.parametrize("repuesto_id", [999, 3])
async def test_consultas_de_inexistente_o_dado_de_baja_lanzan(uow, consulta, repuesto_id):
    if repuesto_id == 3:
        await service.dar_de_baja_repuesto(uow, 3)
    with pytest.raises(service.RepuestoNoEncontrado):
        await getattr(service, consulta)(uow, repuesto_id)
