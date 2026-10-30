"""CH-08 grupo 9: terminar una orden descontando stock (RN-13, RN-14, DD-14) - C-11, C-12.

Sesión real (login). Seed: orden 2 EN_REPARACION (vehículo 3, de Jorge, mecánico 4) con
BUJ-100 x4; BUJ-100 (repuesto 3) tiene stock 2. Orden 1 PENDIENTE (FIL-001 x1, ACE-530 x4).
"""
import asyncio
import logging

import pytest
from sqlalchemy import text

from app.modules.ordenes import service
from main import app
from tests.ordenes_comun import (
    ADMIN, MECANICO, MECANICO2, RECEPCION, crear_orden, sesion, sin_texto_de_la_base,
)

BUJIAS, FILTRO, ACEITE = 3, 1, 4


async def _filas(motor, sql: str, **params):
    async with motor.connect() as c:
        return [tuple(f) for f in (await c.execute(text(sql), params)).all()]


async def _escalar(motor, sql: str, **params):
    return (await _filas(motor, sql, **params))[0][0]


async def _stock(motor, repuesto_id: int) -> int:
    return await _escalar(motor, "SELECT stock FROM repuesto WHERE id = :i", i=repuesto_id)


async def _estado(motor, orden_id: int) -> str:
    return await _escalar(motor, "SELECT estado FROM orden_trabajo WHERE id = :i", i=orden_id)


async def _movimientos(motor, orden_id: int):
    return await _filas(
        motor, "SELECT repuesto_id, cantidad, usuario_id, motivo FROM movimiento_stock "
        "WHERE orden_id = :i ORDER BY repuesto_id", i=orden_id)


async def _foto(motor, orden_id: int):
    """Todo lo que terminar podría tocar: debe quedar igual si falla."""
    return (
        await _estado(motor, orden_id),
        await _filas(motor, "SELECT id, stock FROM repuesto ORDER BY id"),
        await _escalar(motor, "SELECT count(*) FROM movimiento_stock"),
        await _escalar(motor, "SELECT count(*) FROM historial_estado_orden WHERE orden_id = :i", i=orden_id),
    )


async def _reponer(client, cantidad: int, repuesto_id: int = BUJIAS):
    r = await client.post(
        f"/repuestos/{repuesto_id}/reponer", json={"cantidad": cantidad},
        headers=await sesion(client, ADMIN))
    assert r.status_code == 200, r.text


# --- C-12: reponer y terminar -----------------------------------------------------------------

async def test_c12_reponer_y_terminar_descuenta_el_stock(sembrada, client):
    await _reponer(client, 10)  # 2 + 10 = 12
    movimientos_antes = await _escalar(sembrada, "SELECT count(*) FROM movimiento_stock")
    r = await client.post("/ordenes/2/terminar", headers=await sesion(client, MECANICO))
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado"] == "TERMINADA"
    assert [(h["desde_estado"], h["hasta_estado"], h["usuario_id"]) for h in cuerpo["historial"]][-1] == (
        "EN_REPARACION", "TERMINADA", MECANICO)
    assert await _stock(sembrada, BUJIAS) == 8
    assert await _movimientos(sembrada, 2) == [(BUJIAS, -4, MECANICO, "Orden 2 terminada")]
    assert await _escalar(sembrada, "SELECT count(*) FROM movimiento_stock") == movimientos_antes + 1
    assert await _estado(sembrada, 2) == "TERMINADA"


async def test_c12_triangulado_stock_justo_deja_cero(sembrada, client):
    await _reponer(client, 2)  # 2 + 2 = 4: justo lo que pide la orden
    r = await client.post("/ordenes/2/terminar", headers=await sesion(client, MECANICO))
    assert r.status_code == 200
    assert await _stock(sembrada, BUJIAS) == 0


# --- un movimiento por ítem ---------------------------------------------------------------------

async def test_un_movimiento_por_item_con_cantidades_negativas(sembrada, client):
    orden = await crear_orden(sembrada, 3, [FILTRO, ACEITE], estado="EN_REPARACION", mecanico_id=MECANICO,
                              lineas_historial=1)
    r = await client.post(f"/ordenes/{orden}/terminar", headers=await sesion(client, ADMIN))
    assert r.status_code == 200
    assert await _movimientos(sembrada, orden) == [
        (FILTRO, -1, ADMIN, f"Orden {orden} terminada"), (ACEITE, -1, ADMIN, f"Orden {orden} terminada")]
    assert await _stock(sembrada, FILTRO) == 9 and await _stock(sembrada, ACEITE) == 19
    assert r.json()["historial"][-1]["usuario_id"] == ADMIN


# --- C-11: stock insuficiente -------------------------------------------------------------------

async def test_c11_sin_stock_409_y_nada_cambia(sembrada, client):
    antes = await _foto(sembrada, 2)
    r = await client.post("/ordenes/2/terminar", headers=await sesion(client, MECANICO))
    assert r.status_code == 409
    assert "BUJ-100" in r.json()["detail"]
    sin_texto_de_la_base(r)
    assert await _foto(sembrada, 2) == antes
    assert await _estado(sembrada, 2) == "EN_REPARACION" and await _stock(sembrada, BUJIAS) == 2


async def test_c11_falta_en_el_segundo_item_revierte_el_primero(sembrada, client):
    # Dos ítems: el primero (FIL-001, id 1) alcanza; el segundo (BUJ-100, id 3) no.
    orden = await crear_orden(sembrada, 3, [FILTRO], estado="EN_REPARACION", mecanico_id=MECANICO)
    async with sembrada.begin() as c:
        await c.execute(text(
            "INSERT INTO item_orden (orden_id, repuesto_id, cantidad, precio_unitario) VALUES (:o, :r, 5, 100)"),
            {"o": orden, "r": BUJIAS})
    antes = await _foto(sembrada, orden)
    r = await client.post(f"/ordenes/{orden}/terminar", headers=await sesion(client, MECANICO))
    assert r.status_code == 409
    assert await _foto(sembrada, orden) == antes
    assert await _stock(sembrada, FILTRO) == 10 and await _movimientos(sembrada, orden) == []


async def test_check_de_la_base_tambien_da_409(sembrada, client, monkeypatch):
    """Segunda línea de defensa (D4): si el control en Python no lo frena, el CHECK
    `ck_repuesto_stock_no_negativo` falla en el commit y se traduce al mismo 409."""
    from app.modules.repuestos.repository import RepuestoRepository

    async def _sin_control(self, repuesto, cantidad, *, motivo, usuario_id, orden_id=None):
        repuesto.stock += cantidad  # sin comprobar: lo hará la base
        self.session.add(repuesto)
        await self.session.flush()

    monkeypatch.setattr(RepuestoRepository, "mover_stock", _sin_control)
    antes = await _foto(sembrada, 2)
    r = await client.post("/ordenes/2/terminar", headers=await sesion(client, MECANICO))
    assert r.status_code == 409
    sin_texto_de_la_base(r)
    assert await _foto(sembrada, 2) == antes


# --- DD-14: repuesto dado de baja --------------------------------------------------------------

async def test_dd14_repuesto_dado_de_baja_igual_descuenta(sembrada, client):
    await _reponer(client, 10)
    async with sembrada.begin() as c:
        await c.execute(text("UPDATE repuesto SET borrado_en = now() WHERE id = :i"), {"i": BUJIAS})
    r = await client.post("/ordenes/2/terminar", headers=await sesion(client, MECANICO))
    assert r.status_code == 200
    assert await _stock(sembrada, BUJIAS) == 8


# --- ciclo completo -----------------------------------------------------------------------------

async def test_ciclo_crear_iniciar_terminar_deja_tres_lineas_en_orden(sembrada, client):
    alta = await client.post(
        "/ordenes", json={"vehiculo_id": 2, "falla": "Ruido", "items": [{"repuesto_id": ACEITE, "cantidad": 2}]},
        headers=await sesion(client, RECEPCION))
    assert alta.status_code == 201
    orden = alta.json()["id"]
    assert (await client.post(f"/ordenes/{orden}/iniciar", headers=await sesion(client, MECANICO2))).status_code == 200
    r = await client.post(f"/ordenes/{orden}/terminar", headers=await sesion(client, MECANICO2))
    assert r.status_code == 200
    assert [(h["desde_estado"], h["hasta_estado"]) for h in r.json()["historial"]] == [
        (None, "PENDIENTE"), ("PENDIENTE", "EN_REPARACION"), ("EN_REPARACION", "TERMINADA")]
    assert await _stock(sembrada, ACEITE) == 18


async def test_terminada_ya_no_se_cancela_409(sembrada, client):
    """C-13 (parte pendiente): orden terminada por la API -> cancelar da 409."""
    await _reponer(client, 10)
    assert (await client.post("/ordenes/2/terminar", headers=await sesion(client, MECANICO))).status_code == 200
    r = await client.post("/ordenes/2/cancelar", headers=await sesion(client, RECEPCION))
    assert r.status_code == 409
    assert "TERMINADA" in r.json()["detail"]


# --- aviso con BackgroundTasks (D11) ------------------------------------------------------------

async def _terminar_por_asgi(client, orden_id: int, usuario: int, eventos: list):
    """Llama a la app ASGI con un `send` espiado para ver el orden de los hechos."""
    cookie = (await sesion(client, usuario))["Cookie"]
    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
        "scheme": "http", "path": f"/ordenes/{orden_id}/terminar", "raw_path": None,
        "root_path": "", "query_string": b"", "server": ("test", 80), "client": ("127.0.0.1", 1),
        "headers": [(b"cookie", cookie.encode()), (b"host", b"test")], "state": {},
    }

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(mensaje):
        eventos.append(("asgi", mensaje["type"], mensaje.get("status"), mensaje.get("more_body")))

    class _Registro(logging.Handler):
        def emit(self, registro):
            eventos.append(("aviso", registro.getMessage()))

    logger = logging.getLogger("taller.avisos")
    handler = _Registro(level=logging.INFO)
    logger.addHandler(handler)
    try:
        await app(scope, receive, send)
    finally:
        logger.removeHandler(handler)


@pytest.fixture
def sin_espera(monkeypatch):
    original = asyncio.sleep

    async def _rapido(_segundos, *a, **k):
        await original(0)

    monkeypatch.setattr(service.asyncio, "sleep", _rapido)


async def test_el_aviso_sale_despues_de_la_respuesta(sembrada, client, sin_espera):
    await _reponer(client, 10)
    eventos: list = []
    await _terminar_por_asgi(client, 2, MECANICO, eventos)
    cuerpos = [i for i, e in enumerate(eventos) if e[:2] == ("asgi", "http.response.body") and not e[3]]
    avisos = [i for i, e in enumerate(eventos) if e[0] == "aviso"]
    assert len(cuerpos) == 1 and len(avisos) == 1
    assert avisos[0] > cuerpos[0]
    assert ("asgi", "http.response.start", 200, None) in eventos
    texto = eventos[avisos[0]][1]
    assert "2" in texto and "AD789GH" in texto and "Jorge" in texto


@pytest.mark.parametrize("usuario, orden, esperado", [
    (MECANICO, 2, 409),      # C-11: sin stock
    (MECANICO2, 2, 403),     # no asignado
])
async def test_sin_aviso_cuando_terminar_falla(sembrada, client, sin_espera, caplog, usuario, orden, esperado):
    eventos: list = []
    with caplog.at_level(logging.INFO, logger="taller.avisos"):
        await _terminar_por_asgi(client, orden, usuario, eventos)
    assert ("asgi", "http.response.start", esperado, None) in eventos
    assert [e for e in eventos if e[0] == "aviso"] == []
    assert [r for r in caplog.records if r.name == "taller.avisos"] == []


# --- concurrencia: dos órdenes distintas con el mismo repuesto (design D6) -------------------------

@pytest.fixture
def lecturas_simultaneas(monkeypatch):
    """Obliga a que las dos terminaciones lleguen a escribir stock con lo que ya leyeron.

    Envuelve `mover_stock`: cada llamada espera (máx. 1 s) a que la otra también llegue. Sin
    bloqueo de las filas de repuesto ambas leen el mismo stock y se pisan (lost update); con
    el bloqueo la segunda queda esperando el candado, la espera vence y sigue en serie.
    """
    from app.modules.repuestos.repository import RepuestoRepository

    original = RepuestoRepository.mover_stock
    llegadas = 0
    juntas = asyncio.Event()

    async def _con_espera(self, repuesto, cantidad, **kw):
        nonlocal llegadas
        llegadas += 1
        if llegadas >= 2:
            juntas.set()
        try:
            await asyncio.wait_for(juntas.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass
        return await original(self, repuesto, cantidad, **kw)

    monkeypatch.setattr(RepuestoRepository, "mover_stock", _con_espera)


async def _dos_ordenes_con_filtro(motor, stock: int) -> tuple[int, int]:
    async with motor.begin() as c:
        await c.execute(text("UPDATE repuesto SET stock = :s WHERE id = :i"), {"s": stock, "i": FILTRO})
    return (
        await crear_orden(motor, 3, [FILTRO], estado="EN_REPARACION", mecanico_id=MECANICO),
        await crear_orden(motor, 3, [FILTRO], estado="EN_REPARACION", mecanico_id=MECANICO),
    )


async def test_dos_terminaciones_simultaneas_no_gastan_el_mismo_stock(sembrada, client, lecturas_simultaneas):
    a, b = await _dos_ordenes_con_filtro(sembrada, 1)  # alcanza para una sola
    h = await sesion(client, ADMIN)
    r1, r2 = await asyncio.gather(
        client.post(f"/ordenes/{a}/terminar", headers=h), client.post(f"/ordenes/{b}/terminar", headers=h))
    assert sorted([r1.status_code, r2.status_code]) == [200, 409]
    assert await _stock(sembrada, FILTRO) == 0
    assert await _escalar(
        sembrada, "SELECT count(*) FROM movimiento_stock WHERE repuesto_id = :r AND cantidad < 0 "
        "AND orden_id IN (:a, :b)", r=FILTRO, a=a, b=b) == 1
    estados = sorted([await _estado(sembrada, a), await _estado(sembrada, b)])
    assert estados == ["EN_REPARACION", "TERMINADA"]


async def test_dos_terminaciones_simultaneas_con_stock_para_ambas_descuentan_dos_veces(
        sembrada, client, lecturas_simultaneas):
    a, b = await _dos_ordenes_con_filtro(sembrada, 5)
    h = await sesion(client, ADMIN)
    r1, r2 = await asyncio.gather(
        client.post(f"/ordenes/{a}/terminar", headers=h), client.post(f"/ordenes/{b}/terminar", headers=h))
    assert (r1.status_code, r2.status_code) == (200, 200)
    assert await _stock(sembrada, FILTRO) == 3
    assert await _escalar(
        sembrada, "SELECT count(*) FROM movimiento_stock WHERE repuesto_id = :r AND cantidad = -1 "
        "AND orden_id IN (:a, :b)", r=FILTRO, a=a, b=b) == 2
