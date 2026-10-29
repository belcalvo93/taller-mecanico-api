"""CH-08 grupos 6, 7 y 8: iniciar, cancelar (C-13) y terminar (sólo permiso y estado).

Sesión real (login). Orden 1 PENDIENTE (vehículo 1, de Laura); orden 2 EN_REPARACION
(vehículo 3, de Jorge, mecánico 4). El descuento de stock de terminar es del grupo 9
(bloqueado por CH-07): acá ninguna prueba llega a ese paso.
"""
import pytest
from sqlalchemy import text

from app.modules.ordenes import service
from tests.ordenes_comun import (
    ADMIN, ADMIN2, LAURA, MECANICO, MECANICO2, RECEPCION, crear_orden, sesion, sin_texto_de_la_base,
)


async def _escalar(motor, sql: str, **params):
    async with motor.connect() as c:
        return (await c.execute(text(sql), params)).scalar()


async def _estado(motor, orden_id: int) -> str:
    return await _escalar(motor, "SELECT estado FROM orden_trabajo WHERE id = :i", i=orden_id)


async def _mecanico(motor, orden_id: int):
    return await _escalar(motor, "SELECT mecanico_id FROM orden_trabajo WHERE id = :i", i=orden_id)


async def _lineas(motor, orden_id: int) -> int:
    return await _escalar(motor, "SELECT count(*) FROM historial_estado_orden WHERE orden_id = :i", i=orden_id)


async def _ultima_linea(motor, orden_id: int):
    async with motor.connect() as c:
        fila = (await c.execute(text(
            "SELECT desde_estado, hasta_estado, usuario_id FROM historial_estado_orden "
            "WHERE orden_id = :i ORDER BY id DESC LIMIT 1"), {"i": orden_id})).one()
    return tuple(fila)


# --- 6. iniciar (RN-11, SU-03) ----------------------------------------------------------------

async def test_el_mecanico_inicia_una_pendiente(sembrada, client):
    r = await client.post("/ordenes/1/iniciar", headers=await sesion(client, MECANICO2))
    assert r.status_code == 200
    c = r.json()
    assert (c["estado"], c["mecanico_id"]) == ("EN_REPARACION", MECANICO2)
    assert [(h["desde_estado"], h["hasta_estado"], h["usuario_id"]) for h in c["historial"]] == [
        (None, "PENDIENTE", RECEPCION), ("PENDIENTE", "EN_REPARACION", MECANICO2)]
    assert await _estado(sembrada, 1) == "EN_REPARACION" and await _mecanico(sembrada, 1) == MECANICO2
    assert await _ultima_linea(sembrada, 1) == ("PENDIENTE", "EN_REPARACION", MECANICO2)


async def test_otro_mecanico_inicia_otra_pendiente(sembrada, client):
    nueva = await crear_orden(sembrada, 3, [1])
    r = await client.post(f"/ordenes/{nueva}/iniciar", headers=await sesion(client, MECANICO))
    assert r.status_code == 200 and r.json()["mecanico_id"] == MECANICO
    assert await _lineas(sembrada, nueva) == 2


async def test_iniciar_una_en_reparacion_409_sin_linea_nueva(sembrada, client):
    antes = await _lineas(sembrada, 2)
    r = await client.post("/ordenes/2/iniciar", headers=await sesion(client, MECANICO2))
    assert r.status_code == 409
    assert "EN_REPARACION" in r.json()["detail"]
    sin_texto_de_la_base(r)
    assert await _lineas(sembrada, 2) == antes
    assert await _mecanico(sembrada, 2) == MECANICO


async def test_iniciar_inexistente_404(sembrada, client):
    assert (await client.post("/ordenes/999/iniciar", headers=await sesion(client, MECANICO))).status_code == 404


@pytest.mark.parametrize("usuario", [ADMIN, RECEPCION, LAURA])
async def test_solo_un_mecanico_inicia_403(sembrada, client, usuario):
    r = await client.post("/ordenes/1/iniciar", headers=await sesion(client, usuario))
    assert r.status_code == 403
    assert await _estado(sembrada, 1) == "PENDIENTE" and await _mecanico(sembrada, 1) is None
    assert await _lineas(sembrada, 1) == 1


# --- 7. cancelar (RN-12, RN-17, C-13) ---------------------------------------------------------

async def test_laura_cancela_su_orden_pendiente(sembrada, client):
    r = await client.post("/ordenes/1/cancelar", headers=await sesion(client, LAURA))
    assert r.status_code == 200
    assert r.json()["estado"] == "CANCELADA"
    assert r.json()["historial"][-1]["usuario_id"] == LAURA
    assert await _estado(sembrada, 1) == "CANCELADA"
    assert await _ultima_linea(sembrada, 1) == ("PENDIENTE", "CANCELADA", LAURA)
    assert await _lineas(sembrada, 1) == 2


@pytest.mark.parametrize("usuario", [RECEPCION, ADMIN, ADMIN2])
async def test_recepcion_y_admin_cancelan_una_pendiente_de_jorge(sembrada, client, usuario):
    nueva = await crear_orden(sembrada, 3, [1])
    r = await client.post(f"/ordenes/{nueva}/cancelar", headers=await sesion(client, usuario))
    assert r.status_code == 200 and r.json()["estado"] == "CANCELADA"
    assert await _ultima_linea(sembrada, nueva) == ("PENDIENTE", "CANCELADA", usuario)


async def test_403_antes_que_409_la_orden_ajena_en_reparacion(sembrada, client):
    r = await client.post("/ordenes/2/cancelar", headers=await sesion(client, LAURA))
    assert r.status_code == 403
    assert await _estado(sembrada, 2) == "EN_REPARACION"


async def test_ajena_pendiente_tambien_403(sembrada, client):
    nueva = await crear_orden(sembrada, 3, [1])
    r = await client.post(f"/ordenes/{nueva}/cancelar", headers=await sesion(client, LAURA))
    assert r.status_code == 403
    assert await _estado(sembrada, nueva) == "PENDIENTE"


@pytest.mark.parametrize("usuario", [MECANICO, MECANICO2])
async def test_un_mecanico_sin_relacion_no_cancela_403(sembrada, client, usuario):
    r = await client.post("/ordenes/1/cancelar", headers=await sesion(client, usuario))
    assert r.status_code == 403
    assert await _estado(sembrada, 1) == "PENDIENTE"


async def test_cancelar_una_terminada_409_sin_linea_nueva(sembrada, client):
    terminada = await crear_orden(sembrada, 3, [1], estado="TERMINADA")
    antes = await _lineas(sembrada, terminada)
    r = await client.post(f"/ordenes/{terminada}/cancelar", headers=await sesion(client, RECEPCION))
    assert r.status_code == 409
    assert "TERMINADA" in r.json()["detail"]
    assert await _estado(sembrada, terminada) == "TERMINADA"
    assert await _lineas(sembrada, terminada) == antes


async def test_cancelar_en_reparacion_409_para_la_recepcion(sembrada, client):
    antes = await _lineas(sembrada, 2)
    r = await client.post("/ordenes/2/cancelar", headers=await sesion(client, RECEPCION))
    assert r.status_code == 409
    assert await _lineas(sembrada, 2) == antes


async def test_cancelar_inexistente_404(sembrada, client):
    assert (await client.post("/ordenes/999/cancelar", headers=await sesion(client, ADMIN))).status_code == 404


async def test_el_dueno_cancela_aunque_el_vehiculo_este_dado_de_baja(sembrada, client):
    async with sembrada.begin() as c:
        await c.execute(text("UPDATE vehiculo SET borrado_en = now() WHERE id = 1"))
    r = await client.post("/ordenes/1/cancelar", headers=await sesion(client, LAURA))
    assert r.status_code == 200


# --- 8. terminar: permiso, estado y 404 (sin tocar stock) --------------------------------------

async def test_mecanico_no_asignado_403_y_nada_cambia(sembrada, client):
    antes = await _lineas(sembrada, 2)
    r = await client.post("/ordenes/2/terminar", headers=await sesion(client, MECANICO2))
    assert r.status_code == 403
    sin_texto_de_la_base(r)
    assert await _estado(sembrada, 2) == "EN_REPARACION"
    assert await _lineas(sembrada, 2) == antes


@pytest.mark.parametrize("usuario", [RECEPCION, LAURA])
async def test_recepcion_y_cliente_no_terminan_403(sembrada, client, usuario):
    r = await client.post("/ordenes/2/terminar", headers=await sesion(client, usuario))
    assert r.status_code == 403
    assert await _estado(sembrada, 2) == "EN_REPARACION"


async def test_403_antes_que_409_mecanico_no_asignado_sobre_una_pendiente(sembrada, client):
    r = await client.post("/ordenes/1/terminar", headers=await sesion(client, MECANICO2))
    assert r.status_code == 403
    assert await _estado(sembrada, 1) == "PENDIENTE"


async def test_el_mecanico_asignado_sobre_una_terminada_es_409(sembrada, client):
    terminada = await crear_orden(sembrada, 3, [1], estado="TERMINADA", mecanico_id=MECANICO)
    r = await client.post(f"/ordenes/{terminada}/terminar", headers=await sesion(client, MECANICO))
    assert r.status_code == 409
    assert "TERMINADA" in r.json()["detail"]


async def test_admin_sobre_una_pendiente_409_sin_cambios(sembrada, client):
    antes = await _lineas(sembrada, 1)
    r = await client.post("/ordenes/1/terminar", headers=await sesion(client, ADMIN))
    assert r.status_code == 409
    assert "PENDIENTE" in r.json()["detail"]
    assert await _estado(sembrada, 1) == "PENDIENTE"
    assert await _lineas(sembrada, 1) == antes


async def test_terminar_inexistente_404(sembrada, client):
    assert (await client.post("/ordenes/999/terminar", headers=await sesion(client, ADMIN))).status_code == 404


# --- C-01 en las tres acciones ---------------------------------------------------------------

@pytest.fixture
def servicio_espiado(monkeypatch):
    llamadas = []
    for nombre in ("iniciar_orden", "terminar_orden", "cancelar_orden"):
        async def _espia(*args, _n=nombre, **kwargs):
            llamadas.append(_n)
            raise AssertionError("el servicio no debía ejecutarse")
        monkeypatch.setattr(service, nombre, _espia)
    return llamadas


@pytest.mark.parametrize("accion", ["iniciar", "terminar", "cancelar"])
@pytest.mark.parametrize("id_", ["abc", "3000000000", "0"])
async def test_c01_id_invalido_422_sin_ejecutar_el_servicio(sembrada, client, servicio_espiado, accion, id_):
    r = await client.post(f"/ordenes/{id_}/{accion}", headers=await sesion(client, MECANICO))
    assert r.status_code == 422
    assert servicio_espiado == []
