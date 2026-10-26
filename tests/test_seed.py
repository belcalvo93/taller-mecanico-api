"""seed.py (CH-02): deja `taller_test` en el estado inicial conocido.
Los tests corren con BCRYPT_COST=4 (velocidad) y dejan las tablas VACÍAS al
terminar, para no alterar a los tests que esperan una base sin datos."""
import pytest
from sqlalchemy import text

import seed
from app.core.config import get_settings

def _settings(monkeypatch, costo="4"):
    monkeypatch.setenv("BCRYPT_COST", costo)
    get_settings.cache_clear()
    return get_settings()


async def leer(motor, sql, **params):
    async with motor.connect() as c:
        return (await c.execute(text(sql), params)).all()


# --- 6.1 catálogo -------------------------------------------------------------


async def test_el_catalogo_de_estados(sembrada):
    filas = await leer(sembrada, "SELECT codigo, posicion, es_final, descripcion FROM estado_orden ORDER BY posicion")
    assert [(c, p, f) for c, p, f, _ in filas] == [
        ("PENDIENTE", 1, False),
        ("EN_REPARACION", 2, False),
        ("TERMINADA", 3, True),
        ("CANCELADA", 4, True),
    ]
    assert all(d.strip() for *_, d in filas)


# --- 6.3 orden de carga ---------------------------------------------------------


@pytest.fixture
def sentencias(motor):
    from sqlalchemy import event

    ejecutadas = []

    def _registrar(conn, cursor, statement, *args):
        ejecutadas.append(statement)

    event.listen(motor.sync_engine, "before_cursor_execute", _registrar)
    yield ejecutadas
    event.remove(motor.sync_engine, "before_cursor_execute", _registrar)


async def test_primero_se_vacia_y_la_primera_insercion_es_el_catalogo(
    motor, monkeypatch, vaciar_al_terminar, sentencias
):
    await seed.sembrar(motor, _settings(monkeypatch))
    assert sentencias[0].lstrip().upper().startswith("TRUNCATE")
    primera = next(s for s in sentencias if s.lstrip().upper().startswith("INSERT"))
    assert primera.lstrip().upper().startswith("INSERT INTO ESTADO_ORDEN")


# --- 6.4 usuarios y roles (+ ids de la consigna) --------------------------------

CORREOS = [
    "admin@example.com",
    "admin2@example.com",
    "recepcion@example.com",
    "mecanico@example.com",
    "mecanico2@example.com",
    "cliente@example.com",
    "nuevo@example.com",
]
ROLES = ["ADMIN", "ADMIN", "RECEPCION", "MECANICO", "MECANICO", "CLIENTE", "MECANICO"]


async def test_usuarios_con_ids_de_la_consigna_y_su_rol_vigente(sembrada):
    filas = await leer(
        sembrada,
        "SELECT u.id, u.email, u.activo, u.debe_cambiar_password, u.password_cambiada_en, "
        "a.rol, a.vence_en, a.revocada_en FROM usuario u JOIN asignacion_rol a ON a.usuario_id = u.id "
        "ORDER BY u.id",
    )
    assert [(f.id, f.email, f.rol) for f in filas] == list(zip(range(1, 8), CORREOS, ROLES))
    assert all(f.activo and f.password_cambiada_en is None for f in filas)
    assert all(f.vence_en is None and f.revocada_en is None for f in filas)
    assert [f.email for f in filas if f.debe_cambiar_password] == ["nuevo@example.com"]


async def test_cada_usuario_tiene_exactamente_un_rol(sembrada):
    (cantidad,) = (await leer(sembrada, "SELECT count(*) FROM asignacion_rol"))[0]
    assert cantidad == 7


async def test_los_ids_coinciden_con_los_de_la_consigna(sembrada):
    # Usuarios 1..7 en el orden del apartado "Datos iniciales"; repuestos en el orden
    # en que los lista la consigna (los ejemplos fijan 1 FIL-001, 2 FRE-010 y 4 ACE-530);
    # el vehículo 2 es AC456EF de Laura (respuesta de ejemplo de POST /ordenes).
    usuarios = await leer(sembrada, "SELECT id, email FROM usuario ORDER BY id")
    assert [(f.id, f.email) for f in usuarios] == list(zip(range(1, 8), CORREOS))
    repuestos = await leer(sembrada, "SELECT id, codigo FROM repuesto ORDER BY id")
    assert [(f.id, f.codigo) for f in repuestos] == [
        (1, "FIL-001"), (2, "FRE-010"), (3, "BUJ-100"), (4, "ACE-530"),
    ]
    (vehiculo,) = await leer(
        sembrada,
        "SELECT v.patente, c.nombre FROM vehiculo v JOIN cliente c ON c.id = v.cliente_id WHERE v.id = 2",
    )
    assert vehiculo.patente == "AC456EF" and vehiculo.nombre.startswith("Laura")


# --- 6.5 contraseñas -------------------------------------------------------------


async def test_las_contrasenas_de_prueba_verifican_y_otra_no(sembrada):
    import bcrypt

    hashes = dict(await leer(sembrada, "SELECT email, password_hash FROM usuario"))
    assert set(hashes) == set(CORREOS) == set(seed.CONTRASENAS)
    for correo, clave in seed.CONTRASENAS.items():
        assert hashes[correo].startswith("$2b$04$")
        assert hashes[correo] != clave
        assert bcrypt.checkpw(clave.encode(), hashes[correo].encode())
        assert not bcrypt.checkpw(b"otra-clave-cualquiera", hashes[correo].encode())
        assert len(clave.encode()) <= 72


async def test_el_costo_sale_de_la_configuracion(motor, monkeypatch, vaciar_al_terminar):
    await seed.sembrar(motor, _settings(monkeypatch, "5"))
    hashes = [h for (h,) in await leer(motor, "SELECT password_hash FROM usuario")]
    assert len(hashes) == 7 and all(h.startswith("$2b$05$") for h in hashes)


async def test_los_hashes_se_calculan_en_hilos_y_antes_de_abrir_la_transaccion(
    motor, monkeypatch, vaciar_al_terminar, sentencias
):
    import threading

    import bcrypt

    real = bcrypt.hashpw
    llamadas = []

    def espia(clave, sal):
        llamadas.append((threading.current_thread() is threading.main_thread(), len(sentencias)))
        return real(clave, sal)

    monkeypatch.setattr(bcrypt, "hashpw", espia)
    await seed.sembrar(motor, _settings(monkeypatch))
    assert len(llamadas) == 7
    assert all(not principal for principal, _ in llamadas)  # asyncio.to_thread
    assert all(antes == 0 for _, antes in llamadas)  # ninguna sentencia SQL todavía


def test_seed_no_usa_el_modulo_de_seguridad_de_la_app():
    codigo = open(seed.__file__, encoding="utf-8").read()
    assert "app.core.security" not in codigo


# --- 6.6 clientes y vehículos -------------------------------------------------


async def test_laura_y_jorge_con_sus_vehiculos(sembrada):
    clientes = await leer(sembrada, "SELECT id, usuario_id, nombre, documento, telefono FROM cliente ORDER BY id")
    assert [tuple(c) for c in clientes] == [
        (1, 6, "Laura Cliente", "30111222", "11 4000-1111"),
        (2, None, "Jorge Gómez", "25333444", "11 4000-2222"),
    ]
    vehiculos = await leer(
        sembrada, "SELECT id, cliente_id, patente, marca, modelo, anio, borrado_en FROM vehiculo ORDER BY id"
    )
    assert [tuple(v) for v in vehiculos] == [
        (1, 1, "AB123CD", "Volkswagen", "Gol Trend", 2015, None),
        (2, 1, "AC456EF", "Toyota", "Etios", 2019, None),
        (3, 2, "AD789GH", "Ford", "Fiesta", 2012, None),
    ]


# --- 6.7 repuestos y stock --------------------------------------------------------


async def test_repuestos_aprobados(sembrada):
    from decimal import Decimal

    filas = await leer(sembrada, "SELECT id, codigo, descripcion, precio, stock, borrado_en FROM repuesto ORDER BY id")
    assert [tuple(f) for f in filas] == [
        (1, "FIL-001", "Filtro de aceite", Decimal("8500.00"), 10, None),
        (2, "FRE-010", "Pastillas de freno delanteras", Decimal("32000.00"), 4, None),
        (3, "BUJ-100", "Bujía de encendido", Decimal("6500.00"), 2, None),
        (4, "ACE-530", "Aceite 5W30 por litro", Decimal("12000.00"), 20, None),
    ]
    assert "freno" not in filas[2].descripcion.lower()


async def test_un_movimiento_stock_inicial_por_repuesto_y_un_cambio_de_precio(sembrada):
    from decimal import Decimal

    movs = await leer(
        sembrada,
        "SELECT m.repuesto_id, m.cantidad, m.motivo, m.orden_id, m.usuario_id, r.stock "
        "FROM movimiento_stock m JOIN repuesto r ON r.id = m.repuesto_id ORDER BY m.repuesto_id",
    )
    assert len(movs) == 4
    assert [(f.repuesto_id, f.motivo, f.orden_id, f.usuario_id) for f in movs] == [
        (i, "Stock inicial", None, 1) for i in (1, 2, 3, 4)
    ]
    assert all(f.cantidad == f.stock for f in movs)
    precios = await leer(sembrada, "SELECT repuesto_id, usuario_id, precio_anterior, precio_nuevo FROM historial_precio_repuesto")
    assert [tuple(p) for p in precios] == [(1, 1, Decimal("8000.00"), Decimal("8500.00"))]


# --- 6.8 órdenes ------------------------------------------------------------------


async def test_orden_1_pendiente_de_laura(sembrada):
    from decimal import Decimal

    (o,) = await leer(sembrada, "SELECT vehiculo_id, mecanico_id, estado, falla, total FROM orden_trabajo WHERE id = 1")
    assert (o.vehiculo_id, o.mecanico_id, o.estado, o.total) == (1, None, "PENDIENTE", Decimal("56500.00"))
    assert o.falla == "Service de 60.000 km: cambio de aceite y filtro"
    items = await leer(sembrada, "SELECT repuesto_id, cantidad, precio_unitario FROM item_orden WHERE orden_id = 1 ORDER BY repuesto_id")
    assert [tuple(i) for i in items] == [(1, 1, Decimal("8500.00")), (4, 4, Decimal("12000.00"))]
    hist = await leer(sembrada, "SELECT desde_estado, hasta_estado, usuario_id FROM historial_estado_orden WHERE orden_id = 1 ORDER BY id")
    assert [tuple(h) for h in hist] == [(None, "PENDIENTE", 3)]


async def test_orden_2_en_reparacion_pide_4_bujias_con_2_en_stock(sembrada):
    from decimal import Decimal

    (o,) = await leer(sembrada, "SELECT vehiculo_id, mecanico_id, estado, falla, total FROM orden_trabajo WHERE id = 2")
    assert (o.vehiculo_id, o.mecanico_id, o.estado, o.total) == (3, 4, "EN_REPARACION", Decimal("26000.00"))
    assert o.falla == "Falla de encendido: el motor ratea en frío"
    items = await leer(sembrada, "SELECT repuesto_id, cantidad, precio_unitario FROM item_orden WHERE orden_id = 2")
    assert [tuple(i) for i in items] == [(3, 4, Decimal("6500.00"))]
    (stock,) = (await leer(sembrada, "SELECT stock FROM repuesto WHERE id = 3"))[0]
    assert stock == 2
    hist = await leer(sembrada, "SELECT desde_estado, hasta_estado, usuario_id FROM historial_estado_orden WHERE orden_id = 2 ORDER BY id")
    assert [tuple(h) for h in hist] == [(None, "PENDIENTE", 3), ("PENDIENTE", "EN_REPARACION", 4)]


async def test_totales_y_precios_unitarios_son_coherentes(sembrada):
    incoherentes = await leer(
        sembrada,
        "SELECT o.id FROM orden_trabajo o WHERE o.total <> "
        "(SELECT sum(cantidad * precio_unitario) FROM item_orden WHERE orden_id = o.id)",
    )
    assert incoherentes == []
    distintos = await leer(
        sembrada, "SELECT i.id FROM item_orden i JOIN repuesto r ON r.id = i.repuesto_id WHERE i.precio_unitario <> r.precio"
    )
    assert distintos == []


async def test_la_proxima_orden_es_la_3(sembrada, conexion):
    from tests.helpers import insertar

    assert await insertar(conexion, "orden_trabajo", vehiculo_id=2) == 3


# --- 6.9 evento de seguridad -----------------------------------------------------


async def test_un_evento_de_seguridad(sembrada):
    filas = await leer(sembrada, "SELECT actor, accion FROM evento_seguridad")
    assert [tuple(f) for f in filas] == [("SISTEMA", "Carga de los datos iniciales")]


# --- 6.10 reproducibilidad --------------------------------------------------------

TABLAS = [
    "usuario", "asignacion_rol", "intento_acceso", "evento_seguridad", "cliente", "vehiculo",
    "repuesto", "movimiento_stock", "historial_precio_repuesto", "estado_orden", "orden_trabajo",
    "item_orden", "historial_estado_orden",
]


async def foto(motor):
    """Todas las filas de las 13 tablas sin lo que cambia en cada corrida (hashes con sal y horas)."""
    resultado = {}
    for tabla in TABLAS:
        columnas = [
            c
            for (c, tipo) in await leer(
                motor,
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = :t ORDER BY ordinal_position",
                t=tabla,
            )
            if not tipo.startswith("timestamp") and c != "password_hash"
        ]
        # tabla y columnas salen del catálogo de la base y de la lista fija de arriba
        filas = await leer(motor, "SELECT " + ", ".join(columnas) + " FROM " + tabla + " ORDER BY 1")
        resultado[tabla] = [tuple(f) for f in filas]
    return resultado


async def test_el_seed_elimina_las_filas_ajenas(sembrada):
    async with sembrada.begin() as c:
        await c.execute(
            text("INSERT INTO repuesto (codigo, descripcion, precio, stock) VALUES ('EXTRA-1', 'Ajeno', 1, 3)")
        )
        await c.execute(
            text(
                "INSERT INTO movimiento_stock (repuesto_id, usuario_id, cantidad, motivo, cuando) "
                "VALUES (5, 1, 3, 'Ajeno', now())"
            )
        )
    assert len(await leer(sembrada, "SELECT 1 FROM repuesto")) == 5

    await seed.sembrar(sembrada, get_settings())

    assert [r.codigo for r in await leer(sembrada, "SELECT codigo FROM repuesto ORDER BY id")] == [
        "FIL-001", "FRE-010", "BUJ-100", "ACE-530",
    ]
    assert len(await leer(sembrada, "SELECT 1 FROM movimiento_stock")) == 4


async def test_dos_corridas_dejan_las_mismas_filas_con_los_mismos_ids(sembrada, monkeypatch):
    primera = await foto(sembrada)
    await seed.sembrar(sembrada, _settings(monkeypatch))
    segunda = await foto(sembrada)
    assert primera == segunda
    assert len(primera["usuario"]) == 7 and len(primera["item_orden"]) == 3


async def test_si_la_carga_falla_a_mitad_la_base_queda_como_estaba(sembrada, monkeypatch):
    from sqlalchemy.exc import DBAPIError

    antes = await foto(sembrada)
    invalidos = [dict(r) for r in seed.REPUESTOS]
    invalidos[0]["stock"] = -1  # viola ck_repuesto_stock_no_negativo después del TRUNCATE
    monkeypatch.setattr(seed, "REPUESTOS", invalidos)

    with pytest.raises(DBAPIError):
        await seed.sembrar(sembrada, get_settings())

    assert await foto(sembrada) == antes


# --- 6.11 `python seed.py` ----------------------------------------------------------


def test_python_seed_py_carga_taller_test_y_no_tiene_secretos(motor, vaciar_al_terminar):
    import os
    import subprocess
    import sys

    entorno = {**os.environ, "POSTGRES_DB": "taller_test", "BCRYPT_COST": "4"}
    res = subprocess.run(
        [sys.executable, seed.__file__], cwd=os.path.dirname(seed.__file__), env=entorno,
        capture_output=True, text=True, timeout=120,
    )
    assert res.returncode == 0, res.stderr[-500:]

    codigo = open(seed.__file__, encoding="utf-8").read()
    for prohibido in ("postgresql://", "postgresql+asyncpg", "POSTGRES_PASSWORD", "JWT_SECRET_KEY"):
        assert prohibido not in codigo


async def test_python_seed_py_dejo_los_datos(motor, vaciar_al_terminar):
    # Depende del test anterior solo en que corre a continuación: lo repite para no acoplarse.
    import os
    import subprocess
    import sys

    entorno = {**os.environ, "POSTGRES_DB": "taller_test", "BCRYPT_COST": "4"}
    subprocess.run(
        [sys.executable, seed.__file__], cwd=os.path.dirname(seed.__file__), env=entorno,
        capture_output=True, text=True, timeout=120, check=True,
    )
    assert (await leer(motor, "SELECT count(*) FROM usuario"))[0][0] == 7
    assert (await leer(motor, "SELECT count(*) FROM orden_trabajo"))[0][0] == 2
