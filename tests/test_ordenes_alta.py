"""CH-08 grupo 4: alta de una orden en un solo bloque (RN-10, RN-16, RN-19, C-10).

Sesión real (login). Base sembrada: vehículos 1 y 2 de Laura, 3 de Jorge; repuestos
1 FIL-001 (8500.00), 2 FRE-010 (32000.00), 3 BUJ-100 (6500.00), 4 ACE-530 (12000.00).
"""
import pytest
from sqlalchemy import text

from app.modules.ordenes import service
from app.modules.ordenes.schemas import ItemOrdenCrear, OrdenCrear
from app.modules.ordenes.unit_of_work import OrdenesUnitOfWork
from tests.helpers import escenario
from tests.ordenes_comun import ADMIN, LAURA, MECANICO, RECEPCION, sesion, sin_texto_de_la_base

CONSIGNA = {
    "vehiculo_id": 2,
    "falla": "Frenos que rechinan",
    "items": [{"repuesto_id": 2, "cantidad": 1}, {"repuesto_id": 4, "cantidad": 3}],
}


async def _escalar(motor, sql: str, **params):
    async with motor.connect() as c:
        return (await c.execute(text(sql), params)).scalar()


async def _conteos(motor) -> tuple[int, int, int]:
    return tuple([
        await _escalar(motor, f"SELECT count(*) FROM {t}")
        for t in ("orden_trabajo", "item_orden", "historial_estado_orden")
    ])


async def test_alta_como_recepcion_con_el_cuerpo_de_la_consigna(sembrada, client):
    r = await client.post("/ordenes", json=CONSIGNA, headers=await sesion(client, RECEPCION))
    assert r.status_code == 201
    cuerpo = r.json()
    assert cuerpo["id"] == 3
    assert cuerpo["estado"] == "PENDIENTE"
    assert cuerpo["patente"] == "AC456EF"
    assert cuerpo["cliente"] == "Laura Cliente"
    assert cuerpo["mecanico_id"] is None
    assert cuerpo["falla"] == "Frenos que rechinan"
    assert cuerpo["total"] == "68000.00"
    assert [(i["repuesto_id"], i["codigo"], i["cantidad"], i["precio_unitario"], i["subtotal"])
            for i in cuerpo["items"]] == [
        (2, "FRE-010", 1, "32000.00", "32000.00"), (4, "ACE-530", 3, "12000.00", "36000.00")]
    assert [(h["desde_estado"], h["hasta_estado"], h["usuario_id"]) for h in cuerpo["historial"]] == [
        (None, "PENDIENTE", RECEPCION)]
    assert cuerpo["creada_en"].endswith("Z") or "+" in cuerpo["creada_en"]


async def test_alta_como_admin_con_otros_items_lleva_el_id_del_admin(sembrada, client):
    cuerpo = {"vehiculo_id": 3, "falla": "No arranca",
              "items": [{"repuesto_id": 1, "cantidad": 2}, {"repuesto_id": 3, "cantidad": 1}]}
    r = await client.post("/ordenes", json=cuerpo, headers=await sesion(client, ADMIN))
    assert r.status_code == 201
    salida = r.json()
    assert salida["total"] == "23500.00" and salida["patente"] == "AD789GH"
    assert salida["cliente"] == "Jorge Gómez"
    assert salida["historial"][0]["usuario_id"] == ADMIN
    assert await _conteos(sembrada) == (3, 5, 4)


async def test_el_precio_queda_fijo_en_la_orden(sembrada, client):
    h = await sesion(client, RECEPCION)
    creada = (await client.post("/ordenes", json=CONSIGNA, headers=h)).json()
    async with sembrada.begin() as c:
        await c.execute(text("UPDATE repuesto SET precio = 99999.00 WHERE id IN (2, 4)"))
    r = await client.get(f"/ordenes/{creada['id']}", headers=h)
    assert r.status_code == 200
    assert r.json()["total"] == "68000.00"
    assert [i["precio_unitario"] for i in r.json()["items"]] == ["32000.00", "12000.00"]


@pytest.mark.parametrize(
    "cuerpo, preparar",
    [
        pytest.param({**CONSIGNA, "items": [{"repuesto_id": 999, "cantidad": 1}]}, None, id="repuesto inexistente"),
        pytest.param(CONSIGNA, "UPDATE repuesto SET borrado_en = now() WHERE id = 4", id="repuesto dado de baja"),
        pytest.param({**CONSIGNA, "vehiculo_id": 999}, None, id="vehiculo inexistente"),
        pytest.param(CONSIGNA, "UPDATE vehiculo SET borrado_en = now() WHERE id = 2", id="vehiculo dado de baja"),
    ],
)
async def test_409_sin_filas(sembrada, client, cuerpo, preparar):
    h = await sesion(client, RECEPCION)
    if preparar:
        async with sembrada.begin() as c:
            await c.execute(text(preparar))
    antes = await _conteos(sembrada)
    r = await client.post("/ordenes", json=cuerpo, headers=h)
    assert r.status_code == 409
    assert isinstance(r.json()["detail"], str) and r.json()["detail"]
    sin_texto_de_la_base(r)
    assert await _conteos(sembrada) == antes


async def test_un_repuesto_valido_y_otro_inexistente_no_deja_nada(sembrada, client):
    cuerpo = {**CONSIGNA, "items": [{"repuesto_id": 2, "cantidad": 1}, {"repuesto_id": 999, "cantidad": 1}]}
    antes = await _conteos(sembrada)
    r = await client.post("/ordenes", json=cuerpo, headers=await sesion(client, RECEPCION))
    assert r.status_code == 409
    assert await _conteos(sembrada) == antes


async def test_total_que_no_entra_en_numeric_es_409_no_500(sembrada, client):
    h = await sesion(client, RECEPCION)
    async with sembrada.begin() as c:
        await c.execute(text("UPDATE repuesto SET precio = 99999999.99 WHERE id = 2"))
    antes = await _conteos(sembrada)
    cuerpo = {**CONSIGNA, "items": [{"repuesto_id": 2, "cantidad": 10000}]}
    r = await client.post("/ordenes", json=cuerpo, headers=h)
    assert r.status_code == 409
    sin_texto_de_la_base(r)
    assert await _conteos(sembrada) == antes
    # en el límite exacto (9_999_999_999.99 = 99_999_999.99 x 100 y un poco menos) sí entra
    ok = await client.post("/ordenes", json={**CONSIGNA, "items": [{"repuesto_id": 2, "cantidad": 100}]}, headers=h)
    assert ok.status_code == 201 and ok.json()["total"] == "9999999999.00"


async def test_catalogo_vacio_en_el_servicio(conexion):
    from sqlmodel.ext.asyncio.session import AsyncSession

    datos = await escenario(conexion, catalogo=False)
    async with AsyncSession(bind=conexion, expire_on_commit=False, join_transaction_mode="create_savepoint") as s:
        uow = OrdenesUnitOfWork(s)
        orden = OrdenCrear(vehiculo_id=datos["vehiculo"], falla="Ruido",
                           items=[ItemOrdenCrear(repuesto_id=datos["repuesto"], cantidad=1)])
        with pytest.raises(service.CatalogoVacio):
            await service.crear_orden(uow, datos["usuario"], orden)
    assert (await conexion.execute(text("SELECT count(*) FROM orden_trabajo"))).scalar() == 0


async def test_catalogo_vacio_por_la_ruta_es_409_con_mensaje_propio(sembrada, client):
    h = await sesion(client, RECEPCION)
    async with sembrada.begin() as c:
        await c.execute(text("TRUNCATE estado_orden CASCADE"))
    r = await client.post("/ordenes", json=CONSIGNA, headers=h)
    assert r.status_code == 409
    assert "catálogo" in r.json()["detail"].lower()
    sin_texto_de_la_base(r)
    assert await _escalar(sembrada, "SELECT count(*) FROM orden_trabajo") == 0


@pytest.mark.parametrize("usuario", [MECANICO, LAURA])
async def test_mecanico_y_cliente_no_crean_403(sembrada, client, usuario):
    antes = await _conteos(sembrada)
    r = await client.post("/ordenes", json=CONSIGNA, headers=await sesion(client, usuario))
    assert r.status_code == 403
    assert await _conteos(sembrada) == antes


async def test_sin_cookie_401(sembrada, client):
    assert (await client.post("/ordenes", json=CONSIGNA)).status_code == 401


@pytest.mark.parametrize(
    "cuerpo",
    [
        {**CONSIGNA, "total": "1.00"},
        {**CONSIGNA, "estado": "TERMINADA"},
        {**CONSIGNA, "items": [{"repuesto_id": 2, "cantidad": 1, "precio_unitario": "1.00"}]},
        {**CONSIGNA, "items": []},
        {**CONSIGNA, "items": [{"repuesto_id": 2, "cantidad": 1}, {"repuesto_id": 2, "cantidad": 2}]},
        {**CONSIGNA, "items": [{"repuesto_id": 2, "cantidad": 0}]},
        {**CONSIGNA, "items": [{"repuesto_id": 3_000_000_000, "cantidad": 1}]},
        {**CONSIGNA, "falla": "  "},
    ],
)
async def test_contrato_invalido_422_sin_filas(sembrada, client, cuerpo):
    antes = await _conteos(sembrada)
    r = await client.post("/ordenes", json=cuerpo, headers=await sesion(client, RECEPCION))
    assert r.status_code == 422
    assert await _conteos(sembrada) == antes
