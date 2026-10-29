"""CH-07: rutas de repuestos de punta a punta (router -> servicio -> UoW -> repositorio -> taller_test).

Sesión en los tests: se reemplaza SÓLO get_usuario_actual, que elige el usuario por el
encabezado X-Usuario-Test (sin encabezado -> 401). requiere_rol queda el real: consulta
asignacion_rol en la base con los roles del seed. Usuarios: 1 admin, 3 recepción,
4 mecánico, 6 Laura (cliente).
Repuestos del seed: 1 FIL-001 ($8500, stock 10), 2 FRE-010 ($32000, stock 4),
3 BUJ-100 ($6500, stock 2, en la orden 2 EN_REPARACION), 4 ACE-530 ($12000, stock 20).
"""
import pytest
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

import main
from app.core.database import get_session
from app.core.dependencies import get_usuario_actual
from app.modules.usuarios.models import Usuario

ADMIN, RECEPCION, MECANICO, LAURA = 1, 3, 4, 6
NUEVO = {"codigo": "FIL-010", "descripcion": "Filtro de aire", "precio": "5500.00", "stock_inicial": 15}
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


# --- GET /repuestos (4.1) ----------------------------------------------------------------

@pytest.mark.parametrize("usuario_id", [ADMIN, RECEPCION, MECANICO])
async def test_listado_sin_filtro_200_con_los_4_del_seed(api, usuario_id):
    r = await api.get("/repuestos?page=1&size=20", headers=como(usuario_id))
    assert r.status_code == 200
    cuerpo = r.json()
    assert (cuerpo["total"], cuerpo["page"], cuerpo["size"], cuerpo["pages"]) == (4, 1, 20, 1)
    assert [i["codigo"] for i in cuerpo["items"]] == ["FIL-001", "FRE-010", "BUJ-100", "ACE-530"]
    assert cuerpo["items"][0] == {
        "id": 1, "codigo": "FIL-001", "descripcion": "Filtro de aceite", "precio": "8500.00", "stock": 10,
    }


@pytest.mark.parametrize("q", ["filtro", "FILTRO"])
async def test_busqueda_por_descripcion_sin_distinguir_mayusculas(api, q):
    r = await api.get("/repuestos", params={"q": q}, headers=como(RECEPCION))
    assert r.status_code == 200
    assert [i["codigo"] for i in r.json()["items"]] == ["FIL-001"]
    assert r.json()["total"] == 1


async def test_c16_busqueda_con_comillas_no_inyecta_y_da_pagina_vacia(api, sembrada):
    r = await api.get("/repuestos", params={"q": "' OR '1'='1"}, headers=como(ADMIN))
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 1}
    assert await _escalar(sembrada, "SELECT count(*) FROM repuesto") == 4


async def test_repuesto_dado_de_baja_no_aparece_en_el_listado(api):
    assert (await api.delete("/repuestos/2", headers=como(ADMIN))).status_code == 204
    r = await api.get("/repuestos", headers=como(ADMIN))
    assert [i["id"] for i in r.json()["items"]] == [1, 3, 4]
    assert r.json()["total"] == 3


@pytest.mark.parametrize("consulta", ["page=0", "size=0", "size=101", "page=2", "page=abc"])
async def test_paginacion_invalida_o_inexistente_422(api, consulta):
    r = await api.get(f"/repuestos?{consulta}", headers=como(ADMIN))
    assert r.status_code == 422


async def test_total_y_paginas_con_size_chico(api):
    r = await api.get("/repuestos?page=2&size=3", headers=como(ADMIN))
    assert r.status_code == 200
    assert [i["codigo"] for i in r.json()["items"]] == ["ACE-530"]
    assert (r.json()["total"], r.json()["pages"]) == (4, 2)


# --- GET /repuestos/{id} (4.1) -----------------------------------------------------------

@pytest.mark.parametrize("usuario_id", [ADMIN, RECEPCION, MECANICO])
async def test_detalle_de_un_repuesto_existente(api, usuario_id):
    r = await api.get("/repuestos/1", headers=como(usuario_id))
    assert r.status_code == 200
    assert r.json()["codigo"] == "FIL-001"


async def test_detalle_de_inexistente_404(api):
    r = await api.get("/repuestos/999", headers=como(ADMIN))
    assert r.status_code == 404
    assert r.json() == {"detail": "Repuesto no encontrado"}


async def test_detalle_de_dado_de_baja_404(api):
    assert (await api.delete("/repuestos/3", headers=como(ADMIN))).status_code == 204
    assert (await api.get("/repuestos/3", headers=como(ADMIN))).status_code == 404


@pytest.mark.parametrize("id_", ["0", "-1", "abc", "2147483648", "1.5"])
async def test_id_invalido_422_en_todas_las_rutas_con_id(api, id_):
    for metodo, sufijo, cuerpo in [
        ("GET", "", None), ("PATCH", "", {"precio": "10.00"}), ("DELETE", "", None),
        ("POST", "/reponer", {"cantidad": 1}), ("GET", "/movimientos", None), ("GET", "/precios", None),
    ]:
        r = await api.request(metodo, f"/repuestos/{id_}{sufijo}", json=cuerpo, headers=como(ADMIN))
        assert r.status_code == 422, (metodo, sufijo)


# --- POST /repuestos (4.2) ---------------------------------------------------------------

async def test_alta_con_stock_inicial_201_y_su_movimiento(api, sembrada):
    r = await api.post("/repuestos", json=NUEVO, headers=como(ADMIN))
    assert r.status_code == 201
    assert r.json() == {
        "id": 5, "codigo": "FIL-010", "descripcion": "Filtro de aire", "precio": "5500.00", "stock": 15,
    }
    r = await api.get("/repuestos/5/movimientos", headers=como(ADMIN))
    assert [(m["cantidad"], m["motivo"], m["orden_id"], m["usuario_id"]) for m in r.json()] == [
        (15, "Stock inicial", None, ADMIN),
    ]


async def test_alta_con_stock_inicial_cero_201_sin_movimiento(api, sembrada):
    r = await api.post("/repuestos", json={**NUEVO, "stock_inicial": 0}, headers=como(ADMIN))
    assert r.status_code == 201 and r.json()["stock"] == 0
    assert await _escalar(sembrada, "SELECT count(*) FROM movimiento_stock WHERE repuesto_id = 5") == 0


async def test_alta_sin_stock_inicial_vale_cero(api):
    sin_stock = {k: v for k, v in NUEVO.items() if k != "stock_inicial"}
    r = await api.post("/repuestos", json=sin_stock, headers=como(ADMIN))
    assert r.status_code == 201 and r.json()["stock"] == 0


@pytest.mark.parametrize("stock_inicial", [0, 5])
async def test_codigo_vigente_repetido_409_sin_filas_nuevas(api, sembrada, stock_inicial):
    r = await api.post("/repuestos", json={**NUEVO, "codigo": "FIL-001", "stock_inicial": stock_inicial},
                       headers=como(ADMIN))
    assert r.status_code == 409
    assert r.json() == {"detail": "Ya existe un repuesto vigente con ese código"}
    _sin_texto_de_la_base(r)
    assert await _escalar(sembrada, "SELECT count(*) FROM repuesto") == 4
    assert await _escalar(sembrada, "SELECT count(*) FROM movimiento_stock") == 4


async def test_codigo_de_un_repuesto_dado_de_baja_se_reusa_201(api):
    assert (await api.delete("/repuestos/1", headers=como(ADMIN))).status_code == 204
    r = await api.post("/repuestos", json={**NUEVO, "codigo": "FIL-001"}, headers=como(ADMIN))
    assert r.status_code == 201 and r.json()["id"] == 5


@pytest.mark.parametrize(
    "cuerpo",
    [
        {**NUEVO, "precio": "0"},
        {**NUEVO, "precio": "-10.00"},
        {**NUEVO, "precio": "10.999"},
        {**NUEVO, "stock_inicial": -1},
        {**NUEVO, "stock": 5},
        {**NUEVO, "borrado_en": "2026-10-28T10:00:00Z"},
        {**NUEVO, "codigo": "   "},
        {**NUEVO, "descripcion": "Filtro\u0000aire"},
        {"descripcion": "Sin código", "precio": "10.00"},
    ],
)
async def test_alta_invalida_422_sin_filas(api, sembrada, cuerpo):
    r = await api.post("/repuestos", json=cuerpo, headers=como(ADMIN))
    assert r.status_code == 422
    assert await _escalar(sembrada, "SELECT count(*) FROM repuesto") == 4


# --- PATCH /repuestos/{id} (4.3, C-18) ---------------------------------------------------

async def test_c18_cambio_de_precio_registra_el_historial(api):
    r = await api.patch("/repuestos/1", json={"precio": "9500.00"}, headers=como(ADMIN))
    assert r.status_code == 200 and r.json()["precio"] == "9500.00"
    r = await api.get("/repuestos/1/precios", headers=como(ADMIN))
    assert r.status_code == 200
    assert [(p["precio_anterior"], p["precio_nuevo"], p["usuario_id"]) for p in r.json()] == [
        ("8000.00", "8500.00", ADMIN),
        ("8500.00", "9500.00", ADMIN),
    ]


async def test_cambio_solo_de_descripcion_no_toca_el_historial(api, sembrada):
    r = await api.patch("/repuestos/1", json={"descripcion": "Filtro de aceite sintético"}, headers=como(ADMIN))
    assert r.status_code == 200 and r.json()["descripcion"] == "Filtro de aceite sintético"
    assert await _escalar(sembrada, "SELECT count(*) FROM historial_precio_repuesto") == 1


@pytest.mark.parametrize("precio", ["8500.00", 8500])
async def test_mismo_precio_200_sin_fila_en_el_historial(api, sembrada, precio):
    r = await api.patch("/repuestos/1", json={"precio": precio}, headers=como(ADMIN))
    assert r.status_code == 200
    assert await _escalar(sembrada, "SELECT count(*) FROM historial_precio_repuesto") == 1


@pytest.mark.parametrize(
    "cuerpo",
    [{"stock": 99}, {"codigo": "OTRO"}, {"precio": "0"}, {"precio": "-5.00"}, {"precio": None}, {"descripcion": None}],
)
async def test_patch_invalido_422_y_no_cambia_nada(api, sembrada, cuerpo):
    r = await api.patch("/repuestos/1", json=cuerpo, headers=como(ADMIN))
    assert r.status_code == 422
    assert await _escalar(sembrada, "SELECT stock FROM repuesto WHERE id = 1") == 10
    assert await _escalar(sembrada, "SELECT precio FROM repuesto WHERE id = 1") == 8500


async def test_patch_de_inexistente_o_dado_de_baja_404(api):
    assert (await api.patch("/repuestos/999", json={"precio": "10.00"}, headers=como(ADMIN))).status_code == 404
    assert (await api.delete("/repuestos/3", headers=como(ADMIN))).status_code == 204
    r = await api.patch("/repuestos/3", json={"precio": "10.00"}, headers=como(ADMIN))
    assert r.status_code == 404
    assert r.json() == {"detail": "Repuesto no encontrado"}


# --- DELETE /repuestos/{id} (4.3, DD-14) -------------------------------------------------

async def test_baja_de_repuesto_en_orden_abierta_204_no_409(api, sembrada):
    r = await api.delete("/repuestos/3", headers=como(ADMIN))  # figura en la orden 2 EN_REPARACION
    assert r.status_code == 204 and r.content == b""
    assert await _escalar(sembrada, "SELECT borrado_en IS NOT NULL FROM repuesto WHERE id = 3") is True
    assert await _escalar(sembrada, "SELECT count(*) FROM item_orden WHERE repuesto_id = 3") == 1
    assert (await api.get("/repuestos/3", headers=como(ADMIN))).status_code == 404


async def test_baja_de_inexistente_o_repetida_404(api):
    assert (await api.delete("/repuestos/999", headers=como(ADMIN))).status_code == 404
    assert (await api.delete("/repuestos/3", headers=como(ADMIN))).status_code == 204
    r = await api.delete("/repuestos/3", headers=como(ADMIN))
    assert r.status_code == 404
    assert r.json() == {"detail": "Repuesto no encontrado"}


# --- POST /repuestos/{id}/reponer (4.3) --------------------------------------------------

async def test_reposicion_valida_200_y_movimiento(api):
    r = await api.post("/repuestos/3/reponer", json={"cantidad": 5, "motivo": "Compra a proveedor"},
                       headers=como(ADMIN))
    assert r.status_code == 200 and r.json()["stock"] == 7
    r = await api.get("/repuestos/3/movimientos", headers=como(ADMIN))
    assert [(m["cantidad"], m["motivo"], m["orden_id"]) for m in r.json()] == [
        (2, "Stock inicial", None), (5, "Compra a proveedor", None),
    ]


async def test_reposicion_sin_motivo_usa_el_de_por_defecto(api):
    r = await api.post("/repuestos/1/reponer", json={"cantidad": 5}, headers=como(ADMIN))
    assert r.status_code == 200 and r.json()["stock"] == 15
    movimientos = (await api.get("/repuestos/1/movimientos", headers=como(ADMIN))).json()
    assert movimientos[-1]["motivo"] == "Reposición"


@pytest.mark.parametrize("cuerpo", [{"cantidad": 0}, {"cantidad": -3}, {}, {"cantidad": 1, "stock": 3}])
async def test_reposicion_invalida_422_sin_cambios(api, sembrada, cuerpo):
    r = await api.post("/repuestos/3/reponer", json=cuerpo, headers=como(ADMIN))
    assert r.status_code == 422
    assert await _escalar(sembrada, "SELECT stock FROM repuesto WHERE id = 3") == 2
    assert await _escalar(sembrada, "SELECT count(*) FROM movimiento_stock") == 4


async def test_reposicion_de_inexistente_o_dado_de_baja_404(api, sembrada):
    assert (await api.post("/repuestos/999/reponer", json={"cantidad": 1}, headers=como(ADMIN))).status_code == 404
    assert (await api.delete("/repuestos/3", headers=como(ADMIN))).status_code == 204
    assert (await api.post("/repuestos/3/reponer", json={"cantidad": 1}, headers=como(ADMIN))).status_code == 404
    assert await _escalar(sembrada, "SELECT count(*) FROM movimiento_stock") == 4


# --- GET movimientos y precios (4.3) -----------------------------------------------------

async def test_movimientos_del_seed(api):
    r = await api.get("/repuestos/1/movimientos", headers=como(ADMIN))
    assert r.status_code == 200
    assert [(m["cantidad"], m["motivo"]) for m in r.json()] == [(10, "Stock inicial")]
    assert set(r.json()[0]) == {"id", "repuesto_id", "orden_id", "usuario_id", "cantidad", "motivo", "cuando"}


async def test_precios_de_un_repuesto_sin_cambios_es_lista_vacia(api):
    r = await api.get("/repuestos/2/precios", headers=como(ADMIN))
    assert r.status_code == 200 and r.json() == []


@pytest.mark.parametrize("sufijo", ["/movimientos", "/precios"])
async def test_historiales_de_inexistente_o_dado_de_baja_404(api, sufijo):
    assert (await api.get(f"/repuestos/999{sufijo}", headers=como(ADMIN))).status_code == 404
    assert (await api.delete("/repuestos/3", headers=como(ADMIN))).status_code == 204
    assert (await api.get(f"/repuestos/3{sufijo}", headers=como(ADMIN))).status_code == 404


# --- Permisos (4.4, C-18) ----------------------------------------------------------------

RUTAS_DE_CATALOGO = [
    ("GET", "/repuestos", None),
    ("GET", "/repuestos/1", None),
]
RUTAS_DE_ADMIN = [
    ("POST", "/repuestos", NUEVO),
    ("PATCH", "/repuestos/1", {"precio": "9500.00"}),
    ("DELETE", "/repuestos/1", None),
    ("POST", "/repuestos/1/reponer", {"cantidad": 5}),
    ("GET", "/repuestos/1/movimientos", None),
    ("GET", "/repuestos/1/precios", None),
]
LAS_OCHO = RUTAS_DE_CATALOGO + RUTAS_DE_ADMIN


@pytest.mark.parametrize("metodo, ruta, cuerpo", LAS_OCHO)
async def test_sin_cookie_401_con_la_dependencia_real(client, metodo, ruta, cuerpo):
    r = await client.request(metodo, ruta, json=cuerpo)
    assert r.status_code == 401


@pytest.mark.parametrize("metodo, ruta, cuerpo", LAS_OCHO)
async def test_cliente_no_accede_al_catalogo_403(api, sembrada, metodo, ruta, cuerpo):
    r = await api.request(metodo, ruta, json=cuerpo, headers=como(LAURA))
    assert r.status_code == 403
    assert await _escalar(sembrada, "SELECT count(*) FROM repuesto WHERE borrado_en IS NULL") == 4


@pytest.mark.parametrize("usuario_id", [RECEPCION, MECANICO])
@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS_DE_CATALOGO)
async def test_recepcion_y_mecanico_consultan_el_catalogo(api, usuario_id, metodo, ruta, cuerpo):
    r = await api.request(metodo, ruta, json=cuerpo, headers=como(usuario_id))
    assert r.status_code == 200


@pytest.mark.parametrize("usuario_id", [RECEPCION, MECANICO])
@pytest.mark.parametrize("metodo, ruta, cuerpo", RUTAS_DE_ADMIN)
async def test_recepcion_y_mecanico_no_administran_ni_ven_historiales_403(api, sembrada, usuario_id, metodo, ruta, cuerpo):
    r = await api.request(metodo, ruta, json=cuerpo, headers=como(usuario_id))
    assert r.status_code == 403
    assert await _escalar(sembrada, "SELECT count(*) FROM repuesto WHERE borrado_en IS NULL") == 4
    assert await _escalar(sembrada, "SELECT precio FROM repuesto WHERE id = 1") == 8500
    assert await _escalar(sembrada, "SELECT stock FROM repuesto WHERE id = 1") == 10


@pytest.mark.parametrize("metodo, ruta, cuerpo", LAS_OCHO)
async def test_admin_pasa_las_ocho(api, metodo, ruta, cuerpo):
    r = await api.request(metodo, ruta, json=cuerpo, headers=como(ADMIN))
    assert r.status_code in (200, 201, 204)


async def test_rol_admin_revocado_pierde_el_permiso_en_la_peticion_siguiente(api, sembrada):
    assert (await api.get("/repuestos/1/precios", headers=como(ADMIN))).status_code == 200
    async with sembrada.begin() as c:
        await c.execute(text("UPDATE asignacion_rol SET revocada_en = now() WHERE usuario_id = 1"))
    assert (await api.get("/repuestos/1/precios", headers=como(ADMIN))).status_code == 403


# --- Montaje en main.py (4.5) ------------------------------------------------------------

def _rutas_del_grupo(grupo) -> set[tuple[str, str]]:
    # Una app con sólo ese grupo: openapi() resuelve los routers incluidos en
    # cualquier versión de FastAPI (en las nuevas, include_router es perezoso).
    app = FastAPI()
    app.include_router(grupo)
    return {(m.upper(), ruta) for ruta, ops in app.openapi()["paths"].items() for m in ops}


def test_las_ocho_rutas_estan_en_el_grupo_protegido():
    protegidas = _rutas_del_grupo(main.rutas_protegidas)
    abiertas = {ruta for _, ruta in _rutas_del_grupo(main.rutas_abiertas)}
    esperadas = {
        ("GET", "/repuestos"), ("POST", "/repuestos"), ("GET", "/repuestos/{id}"),
        ("PATCH", "/repuestos/{id}"), ("DELETE", "/repuestos/{id}"),
        ("POST", "/repuestos/{id}/reponer"), ("GET", "/repuestos/{id}/movimientos"),
        ("GET", "/repuestos/{id}/precios"),
    }
    assert esperadas <= protegidas
    assert not any(ruta.startswith("/repuestos") for ruta in abiertas)
