"""CH-06: rutas de clientes y vehículos de punta a punta (router → servicio → UoW →
repositorio → taller_test sembrada).

Sesión en los tests (design D9): se reemplaza SÓLO get_usuario_actual, que elige
el usuario por el encabezado X-Usuario-Test (sin encabezado → 401). requiere_rol
queda el real: consulta asignacion_rol en la base, con los roles del seed.
Ids del seed: 1 admin, 2 admin2, 3 recepción, 4 mecánico, 5 mecánico2,
6 Laura (cliente 1, vehículos 1 AB123CD y 2 AC456EF), 7 nuevo. Cliente 2 = Jorge
(sin usuario, vehículo 3 AD789GH). Orden 1 PENDIENTE del vehículo 1; orden 2
EN_REPARACION del vehículo 3.
"""
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

import main
from app.core.database import get_session
from app.core.dependencies import get_usuario_actual
from app.modules.clientes import service
from app.modules.usuarios.models import Usuario
from tests.helpers import insertar

ADMIN, RECEPCION, MECANICO, LAURA = 1, 3, 4, 6
NUEVO_CLIENTE = {"nombre": "Ana Pérez", "documento": "40111222", "telefono": "261 555-1234"}
NUEVO_VEHICULO = {"patente": "AE123BC", "marca": "Fiat", "modelo": "Cronos", "anio": 2022}
TEXTO_DE_LA_BASE = ("uq_", "duplicate", "duplicad", "llave", "key", "violates", "viola", "asyncpg")


def como(usuario_id: int) -> dict[str, str]:
    return {"X-Usuario-Test": str(usuario_id)}


@pytest.fixture
async def api(sembrada, client):
    async def _usuario_de_prueba(
        request: Request, session: AsyncSession = Depends(get_session)
    ) -> Usuario:
        usuario_id = request.headers.get("X-Usuario-Test")
        if usuario_id is None:
            raise HTTPException(401, "No autenticado")
        return await session.get(Usuario, int(usuario_id))

    main.app.dependency_overrides[get_usuario_actual] = _usuario_de_prueba
    try:
        yield client
    finally:
        main.app.dependency_overrides.pop(get_usuario_actual, None)


async def _escalar(motor, sql: str, **params):
    async with motor.connect() as c:
        return (await c.execute(text(sql), params)).scalar()


def _sin_texto_de_la_base(respuesta):
    cuerpo = respuesta.text.lower()
    for palabra in TEXTO_DE_LA_BASE:
        assert palabra not in cuerpo, palabra


# --- POST /clientes ------------------------------------------------------------------

async def test_alta_de_cliente_201(api, sembrada):
    r = await api.post("/clientes", json=NUEVO_CLIENTE, headers=como(RECEPCION))
    assert r.status_code == 201
    assert r.json() == {"id": 3, "usuario_id": None, **NUEVO_CLIENTE}
    assert await _escalar(sembrada, "SELECT count(*) FROM cliente") == 3


async def test_alta_de_cliente_por_admin_201(api):
    r = await api.post("/clientes", json={**NUEVO_CLIENTE, "documento": "40111333"}, headers=como(ADMIN))
    assert r.status_code == 201


@pytest.mark.parametrize("documento", ["30111222", "  30111222 "])
async def test_documento_repetido_409_sin_fila_nueva(api, sembrada, documento):
    r = await api.post("/clientes", json={**NUEVO_CLIENTE, "documento": documento}, headers=como(RECEPCION))
    assert r.status_code == 409
    assert r.json() == {"detail": "Ya existe un cliente con ese documento"}
    _sin_texto_de_la_base(r)
    assert await _escalar(sembrada, "SELECT count(*) FROM cliente") == 2


@pytest.mark.parametrize(
    "cuerpo",
    [
        {**NUEVO_CLIENTE, "usuario_id": 6},  # nadie se vincula a un usuario por acá
        {**NUEVO_CLIENTE, "documento": "   "},
        {"nombre": "Sin documento", "telefono": "1"},
        {**NUEVO_CLIENTE, "nombre": "Ana\u0000Pérez"},
    ],
)
async def test_alta_de_cliente_invalida_422_sin_fila(api, sembrada, cuerpo):
    r = await api.post("/clientes", json=cuerpo, headers=como(RECEPCION))
    assert r.status_code == 422
    assert await _escalar(sembrada, "SELECT count(*) FROM cliente") == 2


# --- GET /clientes/{id} ---------------------------------------------------------------

async def test_cliente_con_sus_vehiculos_vigentes(api):
    r = await api.get("/clientes/1", headers=como(RECEPCION))
    assert r.status_code == 200
    cuerpo = r.json()
    assert (cuerpo["id"], cuerpo["nombre"], cuerpo["documento"], cuerpo["usuario_id"]) == (
        1, "Laura Cliente", "30111222", LAURA,
    )
    assert [v["patente"] for v in cuerpo["vehiculos"]] == ["AB123CD", "AC456EF"]
    assert cuerpo["vehiculos"][1] == {
        "id": 2, "cliente_id": 1, "patente": "AC456EF", "marca": "Toyota", "modelo": "Etios", "anio": 2019,
    }


async def test_cliente_sin_usuario(api):
    r = await api.get("/clientes/2", headers=como(ADMIN))
    assert r.status_code == 200
    assert r.json()["usuario_id"] is None
    assert [v["patente"] for v in r.json()["vehiculos"]] == ["AD789GH"]


async def test_cliente_inexistente_404(api):
    r = await api.get("/clientes/999", headers=como(RECEPCION))
    assert r.status_code == 404
    assert r.json() == {"detail": "Cliente no encontrado"}


async def test_el_vehiculo_dado_de_baja_no_aparece_en_el_cliente(api):
    assert (await api.delete("/vehiculos/2", headers=como(RECEPCION))).status_code == 204
    r = await api.get("/clientes/1", headers=como(RECEPCION))
    assert [v["patente"] for v in r.json()["vehiculos"]] == ["AB123CD"]


# --- POST /clientes/{id}/vehiculos -------------------------------------------------------

async def test_alta_de_vehiculo_201(api):
    r = await api.post("/clientes/2/vehiculos", json=NUEVO_VEHICULO, headers=como(RECEPCION))
    assert r.status_code == 201
    assert r.json() == {"id": 4, "cliente_id": 2, **NUEVO_VEHICULO}


async def test_patente_normalizada_al_guardar(api, sembrada):
    r = await api.post(
        "/clientes/2/vehiculos", json={**NUEVO_VEHICULO, "patente": " ab 123 zz "}, headers=como(ADMIN)
    )
    assert r.status_code == 201 and r.json()["patente"] == "AB123ZZ"
    assert await _escalar(sembrada, "SELECT patente FROM vehiculo WHERE id = 4") == "AB123ZZ"


@pytest.mark.parametrize("patente", ["AD789GH", "ad789gh"])  # vigente de Jorge
async def test_patente_vigente_repetida_409_sin_fila(api, sembrada, patente):
    r = await api.post("/clientes/1/vehiculos", json={**NUEVO_VEHICULO, "patente": patente}, headers=como(RECEPCION))
    assert r.status_code == 409
    assert r.json() == {"detail": "Ya hay un vehículo vigente con esa patente"}
    _sin_texto_de_la_base(r)
    assert await _escalar(sembrada, "SELECT count(*) FROM vehiculo") == 3


@pytest.mark.parametrize("patente", ["AE123BC", "AD789GH"])
async def test_cliente_inexistente_404_aunque_la_patente_este_repetida(api, sembrada, patente):
    r = await api.post("/clientes/999/vehiculos", json={**NUEVO_VEHICULO, "patente": patente}, headers=como(RECEPCION))
    assert r.status_code == 404
    assert r.json() == {"detail": "Cliente no encontrado"}
    assert await _escalar(sembrada, "SELECT count(*) FROM vehiculo") == 3


@pytest.mark.parametrize("anio, codigo", [(1949, 422), (2101, 422), (1950, 201), (2100, 201)])
async def test_anio_en_el_contrato(api, anio, codigo):
    patente = f"AE{anio}B"
    r = await api.post("/clientes/1/vehiculos", json={**NUEVO_VEHICULO, "patente": patente, "anio": anio}, headers=como(RECEPCION))
    assert r.status_code == codigo


async def test_alta_de_vehiculo_con_campo_extra_422(api):
    r = await api.post("/clientes/1/vehiculos", json={**NUEVO_VEHICULO, "cliente_id": 2}, headers=como(RECEPCION))
    assert r.status_code == 422


# --- DELETE /vehiculos/{id} -----------------------------------------------------------

async def test_baja_logica_204_conserva_la_fila(api, sembrada):
    r = await api.delete("/vehiculos/2", headers=como(RECEPCION))
    assert r.status_code == 204 and r.content == b""
    assert await _escalar(sembrada, "SELECT borrado_en IS NOT NULL FROM vehiculo WHERE id = 2") is True


async def test_baja_de_inexistente_o_ya_dado_de_baja_404(api):
    assert (await api.delete("/vehiculos/999", headers=como(RECEPCION))).status_code == 404
    assert (await api.delete("/vehiculos/2", headers=como(RECEPCION))).status_code == 204
    r = await api.delete("/vehiculos/2", headers=como(RECEPCION))
    assert r.status_code == 404
    assert r.json() == {"detail": "Vehículo no encontrado"}


@pytest.mark.parametrize("vehiculo_id", [1, 3])  # orden 1 PENDIENTE, orden 2 EN_REPARACION
async def test_baja_con_orden_abierta_409(api, sembrada, vehiculo_id):
    r = await api.delete(f"/vehiculos/{vehiculo_id}", headers=como(ADMIN))
    assert r.status_code == 409
    assert r.json() == {"detail": "El vehículo tiene órdenes abiertas: no se puede dar de baja"}
    assert await _escalar(sembrada, "SELECT borrado_en FROM vehiculo WHERE id = :id", id=vehiculo_id) is None


async def test_baja_con_ordenes_solo_finales_204(api, sembrada):
    async with sembrada.begin() as c:
        await insertar(c, "orden_trabajo", vehiculo_id=2, estado="TERMINADA")
        await insertar(c, "orden_trabajo", vehiculo_id=2, estado="CANCELADA")
    assert (await api.delete("/vehiculos/2", headers=como(RECEPCION))).status_code == 204
    # Las órdenes viejas se conservan.
    assert await _escalar(sembrada, "SELECT count(*) FROM orden_trabajo WHERE vehiculo_id = 2") == 2


# --- C-19 ------------------------------------------------------------------------------

async def test_c19_baja_y_reuso_de_la_patente(api, sembrada):
    assert (await api.delete("/vehiculos/2", headers=como(RECEPCION))).status_code == 204
    otro = {"patente": "AC456EF", "marca": "Toyota", "modelo": "Etios", "anio": 2019}
    r = await api.post("/clientes/2/vehiculos", json=otro, headers=como(RECEPCION))
    assert r.status_code == 201 and r.json()["cliente_id"] == 2
    r = await api.post("/clientes/1/vehiculos", json=otro, headers=como(RECEPCION))
    assert r.status_code == 409
    # Dos filas con la misma patente: una dada de baja y una vigente.
    assert await _escalar(
        sembrada, "SELECT count(*) FROM vehiculo WHERE patente = 'AC456EF' AND borrado_en IS NULL"
    ) == 1
    assert await _escalar(sembrada, "SELECT count(*) FROM vehiculo WHERE patente = 'AC456EF'") == 2


# --- GET /mis-vehiculos ------------------------------------------------------------------

async def test_mis_vehiculos_solo_los_propios(api):
    r = await api.get("/mis-vehiculos", headers=como(LAURA))
    assert r.status_code == 200
    assert [v["patente"] for v in r.json()] == ["AB123CD", "AC456EF"]
    assert all(v["cliente_id"] == 1 for v in r.json())


@pytest.mark.parametrize("usuario_id", [ADMIN, MECANICO])
async def test_mis_vehiculos_sin_ficha_de_cliente_lista_vacia(api, usuario_id):
    r = await api.get("/mis-vehiculos", headers=como(usuario_id))
    assert r.status_code == 200 and r.json() == []


async def test_mis_vehiculos_sin_el_dado_de_baja(api):
    assert (await api.delete("/vehiculos/2", headers=como(RECEPCION))).status_code == 204
    r = await api.get("/mis-vehiculos", headers=como(LAURA))
    assert [v["patente"] for v in r.json()] == ["AB123CD"]


# --- Permisos -----------------------------------------------------------------------------

RUTAS_DE_PERSONAL = [
    ("POST", "/clientes", NUEVO_CLIENTE),
    ("GET", "/clientes/1", None),
    ("POST", "/clientes/1/vehiculos", NUEVO_VEHICULO),
    ("DELETE", "/vehiculos/2", None),
]
TODAS_LAS_RUTAS = RUTAS_DE_PERSONAL + [("GET", "/mis-vehiculos", None)]


@pytest.mark.parametrize("metodo, ruta, cuerpo", TODAS_LAS_RUTAS)
async def test_sin_cookie_401_con_la_dependencia_real(client, metodo, ruta, cuerpo):
    r = await client.request(metodo, ruta, json=cuerpo)
    assert r.status_code == 401


@pytest.mark.parametrize("usuario_id", [MECANICO, LAURA])
@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS_DE_PERSONAL)
async def test_sin_rol_de_personal_403(api, sembrada, usuario_id, metodo, ruta, cuerpo):
    r = await api.request(metodo, ruta, json=cuerpo, headers=como(usuario_id))
    assert r.status_code == 403
    assert await _escalar(sembrada, "SELECT count(*) FROM cliente") == 2
    assert await _escalar(sembrada, "SELECT count(*) FROM vehiculo WHERE borrado_en IS NULL") == 3


@pytest.mark.parametrize("usuario_id", [ADMIN, RECEPCION])
@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS_DE_PERSONAL)
async def test_admin_y_recepcion_pasan(api, usuario_id, metodo, ruta, cuerpo):
    r = await api.request(metodo, ruta, json=cuerpo, headers=como(usuario_id))
    assert r.status_code in (200, 201, 204)


async def test_rol_revocado_pierde_el_permiso_en_la_peticion_siguiente(api, sembrada):
    assert (await api.get("/clientes/1", headers=como(RECEPCION))).status_code == 200
    async with sembrada.begin() as c:
        await c.execute(text("UPDATE asignacion_rol SET revocada_en = now() WHERE usuario_id = 3"))
    assert (await api.get("/clientes/1", headers=como(RECEPCION))).status_code == 403


def _rutas_del_grupo(grupo) -> set[tuple[str, str]]:
    # Una app con sólo ese grupo: openapi() resuelve los routers incluidos en
    # cualquier versión de FastAPI (en las nuevas, include_router es perezoso).
    app = FastAPI()
    app.include_router(grupo)
    return {(m.upper(), ruta) for ruta, ops in app.openapi()["paths"].items() for m in ops}


def test_las_cinco_rutas_estan_en_el_grupo_protegido():
    protegidas = _rutas_del_grupo(main.rutas_protegidas)
    abiertas = {ruta for _, ruta in _rutas_del_grupo(main.rutas_abiertas)}
    for metodo, ruta in [
        ("POST", "/clientes"), ("GET", "/clientes/{id}"), ("POST", "/clientes/{id}/vehiculos"),
        ("DELETE", "/vehiculos/{id}"), ("GET", "/mis-vehiculos"),
    ]:
        assert (metodo, ruta) in protegidas
        assert ruta not in abiertas


# --- C-01 y RN-18: parámetros de ruta inválidos ------------------------------------------

@pytest.fixture
def servicio_espiado(monkeypatch):
    llamadas = []
    for nombre in ("obtener_cliente", "crear_vehiculo", "dar_de_baja_vehiculo"):
        async def _espia(*args, _nombre=nombre, **kwargs):
            llamadas.append(_nombre)
            raise AssertionError("no debía ejecutarse")
        monkeypatch.setattr(service, nombre, _espia)
    return llamadas


@pytest.mark.parametrize(
    "metodo, ruta, cuerpo",
    [
        ("GET", "/clientes/abc", None),
        ("GET", "/clientes/1.5", None),
        ("POST", "/clientes/abc/vehiculos", NUEVO_VEHICULO),
        ("DELETE", "/vehiculos/1.5", None),
        ("DELETE", "/vehiculos/abc", None),
        # Fuera del rango de la columna INTEGER: sin el tope serían 500 (RN-18).
        ("GET", "/clientes/3000000000", None),
        ("DELETE", "/vehiculos/3000000000", None),
        ("GET", "/clientes/0", None),
        ("DELETE", "/vehiculos/-1", None),
    ],
)
async def test_id_invalido_422_sin_ejecutar_el_servicio(api, servicio_espiado, metodo, ruta, cuerpo):
    r = await api.request(metodo, ruta, json=cuerpo, headers=como(RECEPCION))
    assert r.status_code == 422
    assert servicio_espiado == []
