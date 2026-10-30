"""CH-08 grupo 5: detalle, listados y órdenes propias (C-06, C-15, C-17, C-01).

Sesión real (login). Orden 1 PENDIENTE del vehículo 1 (de Laura); orden 2
EN_REPARACION del vehículo 3 (de Jorge, mecánico 4) con BUJ-100x4.
"""
import pytest
from sqlalchemy import text

from app.modules.ordenes import service
from tests.ordenes_comun import (
    ADMIN, LAURA, MECANICO, MECANICO2, NUEVO, RECEPCION, sesion, sin_texto_de_la_base,
)

CLAVES_RESUMEN = {"id", "estado", "patente", "cliente", "total", "creada_en", "mecanico_id", "falla"}


# --- 5.1 / 5.2 GET /ordenes/{id} ---------------------------------------------------------

@pytest.mark.parametrize("usuario", [RECEPCION, MECANICO, ADMIN])
async def test_el_personal_ve_la_orden_2(sembrada, client, usuario):
    r = await client.get("/ordenes/2", headers=await sesion(client, usuario))
    assert r.status_code == 200
    c = r.json()
    assert (c["id"], c["estado"], c["patente"], c["cliente"], c["mecanico_id"]) == (
        2, "EN_REPARACION", "AD789GH", "Jorge Gómez", MECANICO)
    assert [(i["codigo"], i["cantidad"], i["precio_unitario"], i["subtotal"]) for i in c["items"]] == [
        ("BUJ-100", 4, "6500.00", "26000.00")]
    assert c["total"] == "26000.00"
    assert [(h["desde_estado"], h["hasta_estado"], h["usuario_id"]) for h in c["historial"]] == [
        (None, "PENDIENTE", RECEPCION), ("PENDIENTE", "EN_REPARACION", MECANICO)]
    assert set(c) == CLAVES_RESUMEN | {"items", "historial"}


async def test_detalle_de_la_orden_1_con_importes_en_texto(sembrada, client):
    r = await client.get("/ordenes/1", headers=await sesion(client, RECEPCION))
    c = r.json()
    assert c["total"] == "56500.00"
    assert [i["subtotal"] for i in c["items"]] == ["8500.00", "48000.00"]


async def test_detalle_inexistente_404(sembrada, client):
    r = await client.get("/ordenes/999", headers=await sesion(client, ADMIN))
    assert r.status_code == 404
    sin_texto_de_la_base(r)


async def test_item_con_repuesto_dado_de_baja_sigue_mostrando_codigo_y_descripcion(sembrada, client):
    async with sembrada.begin() as c:
        await c.execute(text("UPDATE repuesto SET borrado_en = now() WHERE id = 3"))
    r = await client.get("/ordenes/2", headers=await sesion(client, MECANICO))
    assert r.status_code == 200
    item = r.json()["items"][0]
    assert (item["codigo"], item["descripcion"]) == ("BUJ-100", "Bujía de encendido")


async def test_el_dueno_ve_su_orden_y_no_la_ajena(sembrada, client):
    h = await sesion(client, LAURA)
    assert (await client.get("/ordenes/1", headers=h)).status_code == 200
    ajena = await client.get("/ordenes/2", headers=h)
    assert ajena.status_code == 403
    sin_texto_de_la_base(ajena)


async def test_sin_rol_vigente_ni_ficha_no_ve_la_orden(sembrada, client):
    # Mecánico2 con su rol revocado: ni personal vigente ni dueño de la orden.
    async with sembrada.begin() as c:
        await c.execute(text("UPDATE asignacion_rol SET revocada_en = now() WHERE usuario_id = 5"))
    h = await sesion(client, MECANICO2)
    assert (await client.get("/ordenes/1", headers=h)).status_code == 403


# --- 5.3 C-15 sin N+1 por la ruta ------------------------------------------------------------

async def test_c15_misma_cantidad_de_sentencias_con_2_y_con_4_items(sembrada, client, sentencias):
    h = await sesion(client, RECEPCION)
    dos = (await client.post("/ordenes", headers=h, json={
        "vehiculo_id": 1, "falla": "Dos", "items": [{"repuesto_id": 1, "cantidad": 1}, {"repuesto_id": 2, "cantidad": 1}]})).json()
    cuatro = (await client.post("/ordenes", headers=h, json={
        "vehiculo_id": 1, "falla": "Cuatro",
        "items": [{"repuesto_id": n, "cantidad": 1} for n in (1, 2, 3, 4)]})).json()
    assert (len(dos["items"]), len(cuatro["items"])) == (2, 4)

    sentencias.clear()
    assert (await client.get(f"/ordenes/{dos['id']}", headers=h)).status_code == 200
    n_dos = len(sentencias)
    sentencias.clear()
    assert (await client.get(f"/ordenes/{cuatro['id']}", headers=h)).status_code == 200
    n_cuatro = len(sentencias)
    assert n_dos == n_cuatro


# --- 5.4 GET /ordenes ------------------------------------------------------------------------------

async def test_listado_filtrado_por_estado(sembrada, client):
    h = await sesion(client, RECEPCION)
    r = await client.get("/ordenes", params={"estado": "PENDIENTE"}, headers=h)
    assert r.status_code == 200
    cuerpo = r.json()
    assert [o["id"] for o in cuerpo["items"]] == [1]
    assert (cuerpo["total"], cuerpo["page"], cuerpo["size"], cuerpo["pages"]) == (1, 1, 20, 1)
    assert set(cuerpo["items"][0]) == CLAVES_RESUMEN
    assert cuerpo["items"][0]["patente"] == "AB123CD" and cuerpo["items"][0]["cliente"] == "Laura Cliente"
    assert cuerpo["items"][0]["total"] == "56500.00"
    en_rep = (await client.get("/ordenes", params={"estado": "EN_REPARACION"}, headers=h)).json()
    assert [o["id"] for o in en_rep["items"]] == [2]


async def test_listado_con_size_1(sembrada, client):
    r = await client.get("/ordenes", params={"size": 1}, headers=await sesion(client, MECANICO))
    cuerpo = r.json()
    assert (len(cuerpo["items"]), cuerpo["total"], cuerpo["pages"]) == (1, 2, 2)
    assert cuerpo["items"][0]["id"] == 1


async def test_listado_de_un_estado_sin_ordenes_es_una_pagina_vacia(sembrada, client):
    r = await client.get("/ordenes", params={"estado": "TERMINADA"}, headers=await sesion(client, ADMIN))
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 1}


async def test_estado_no_declarado_422(sembrada, client):
    r = await client.get("/ordenes", params={"estado": "ENTREGADA"}, headers=await sesion(client, ADMIN))
    assert r.status_code == 422


async def test_pagina_inexistente_o_tamano_invalido_422(sembrada, client):
    h = await sesion(client, ADMIN)
    inexistente = await client.get("/ordenes", params={"page": 3, "size": 1}, headers=h)
    assert inexistente.status_code == 422
    assert inexistente.json() == {"detail": "La página 3 no existe: hay 2"}
    assert (await client.get("/ordenes", params={"size": 500}, headers=h)).status_code == 422
    assert (await client.get("/ordenes", params={"page": 0}, headers=h)).status_code == 422


async def test_un_cliente_no_lista_403(sembrada, client):
    assert (await client.get("/ordenes", headers=await sesion(client, LAURA))).status_code == 403


# --- 5.5 GET /mis-ordenes --------------------------------------------------------------------------

async def test_laura_ve_solo_sus_ordenes(sembrada, client):
    r = await client.get("/mis-ordenes", headers=await sesion(client, LAURA))
    assert r.status_code == 200
    cuerpo = r.json()
    assert [o["id"] for o in cuerpo["items"]] == [1]
    assert (cuerpo["total"], cuerpo["pages"]) == (1, 1)
    assert set(cuerpo["items"][0]) == CLAVES_RESUMEN


async def test_laura_ve_tambien_la_orden_nueva_de_su_otro_vehiculo(sembrada, client):
    h = await sesion(client, RECEPCION)
    await client.post("/ordenes", headers=h, json={
        "vehiculo_id": 2, "falla": "Frenos", "items": [{"repuesto_id": 2, "cantidad": 1}]})
    r = await client.get("/mis-ordenes", headers=await sesion(client, LAURA))
    assert [o["id"] for o in r.json()["items"]] == [1, 3]


async def test_personal_sin_ficha_de_cliente_pagina_vacia(sembrada, client):
    r = await client.get("/mis-ordenes", headers=await sesion(client, RECEPCION))
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 1}


async def test_mis_ordenes_pagina_inexistente_422(sembrada, client):
    h = await sesion(client, LAURA)
    assert (await client.get("/mis-ordenes", params={"page": 2}, headers=h)).status_code == 422
    assert (await client.get("/mis-ordenes", params={"size": 101}, headers=h)).status_code == 422


# --- 5.6 C-06 completo ----------------------------------------------------------------------------

RUTAS = [
    ("GET", "/estados-orden"), ("POST", "/ordenes"), ("GET", "/ordenes"), ("GET", "/ordenes/1"),
    ("POST", "/ordenes/1/iniciar"), ("POST", "/ordenes/1/terminar"), ("POST", "/ordenes/1/cancelar"),
    ("GET", "/mis-ordenes"),
]


@pytest.mark.parametrize("metodo, ruta", RUTAS)
async def test_c06_sin_cookie_las_ocho_rutas_son_401(sembrada, client, metodo, ruta):
    r = await client.request(metodo, ruta, json={} if metodo == "POST" else None)
    assert r.status_code == 401


async def test_c06_laura_es_403_en_listar_y_crear_y_200_en_lo_propio(sembrada, client):
    h = await sesion(client, LAURA)
    assert (await client.get("/ordenes", headers=h)).status_code == 403
    cuerpo = {"vehiculo_id": 1, "falla": "x", "items": [{"repuesto_id": 1, "cantidad": 1}]}
    assert (await client.post("/ordenes", json=cuerpo, headers=h)).status_code == 403
    assert (await client.get("/mis-ordenes", headers=h)).status_code == 200
    assert (await client.get("/auth/yo", headers=h)).status_code == 200


@pytest.mark.parametrize("metodo, ruta", [("GET", "/ordenes"), ("GET", "/mis-ordenes"), ("GET", "/estados-orden")])
async def test_c06_cambio_de_password_pendiente_es_403(sembrada, client, metodo, ruta):
    r = await client.request(metodo, ruta, headers=await sesion(client, NUEVO))
    assert r.status_code == 403
    assert "contraseña" in r.json()["detail"].lower()


# --- 5.7 C-01 -------------------------------------------------------------------------------------------

@pytest.fixture
def servicio_espiado(monkeypatch):
    llamadas = []

    async def _espia(*args, **kwargs):
        llamadas.append(args)
        raise AssertionError("el servicio no debía ejecutarse")

    monkeypatch.setattr(service, "obtener_detalle", _espia)
    return llamadas


@pytest.mark.parametrize("id_", ["abc", "3000000000", "0", "-1"])
async def test_c01_id_invalido_422_sin_ejecutar_el_servicio(sembrada, client, servicio_espiado, id_):
    r = await client.get(f"/ordenes/{id_}", headers=await sesion(client, ADMIN))
    assert r.status_code == 422
    assert servicio_espiado == []
