"""Esquema real contra la base `taller_test` migrada con Alembic (CH-02).
Lo que no necesita base (metadata, relaciones) vive en test_modelos.py.
Las fixtures `motor` y `conexion` están en conftest.py."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import column, event, table, text
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

import app.modules.modelos as m
from tests.helpers import ahora, constraint_name, escenario, insertar, rechaza

TABLAS = [
    "usuario",
    "asignacion_rol",
    "intento_acceso",
    "evento_seguridad",
    "cliente",
    "vehiculo",
    "repuesto",
    "movimiento_stock",
    "historial_precio_repuesto",
    "estado_orden",
    "orden_trabajo",
    "item_orden",
    "historial_estado_orden",
]


async def test_las_13_tablas_existen_y_estan_vacias(motor):
    async with motor.connect() as conexion:
        existentes = (
            await conexion.execute(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
                )
            )
        ).scalars().all()
        assert sorted(existentes) == sorted(TABLAS)
        for tabla in TABLAS:
            # el nombre sale de la lista fija de arriba, no de una entrada externa
            filas = (await conexion.execute(text(f"SELECT count(*) FROM {tabla}"))).scalar_one()
            assert filas == 0, f"{tabla} debería estar vacía"


# --- 4.6 tipos y nulos -------------------------------------------------------

FECHAS = {
    ("usuario", "password_cambiada_en"),
    ("asignacion_rol", "desde"),
    ("asignacion_rol", "vence_en"),
    ("asignacion_rol", "revocada_en"),
    ("intento_acceso", "cuando"),
    ("evento_seguridad", "cuando"),
    ("vehiculo", "borrado_en"),
    ("repuesto", "borrado_en"),
    ("movimiento_stock", "cuando"),
    ("historial_precio_repuesto", "cuando"),
    ("orden_trabajo", "creada_en"),
    ("historial_estado_orden", "cuando"),
}
DINERO = {
    ("repuesto", "precio"): (10, 2),
    ("item_orden", "precio_unitario"): (10, 2),
    ("historial_precio_repuesto", "precio_anterior"): (10, 2),
    ("historial_precio_repuesto", "precio_nuevo"): (10, 2),
    ("orden_trabajo", "total"): (12, 2),
}
NULOS = {
    ("usuario", "password_cambiada_en"),
    ("asignacion_rol", "vence_en"),
    ("asignacion_rol", "revocada_en"),
    ("asignacion_rol", "otorgada_por"),
    ("cliente", "usuario_id"),
    ("vehiculo", "borrado_en"),
    ("repuesto", "borrado_en"),
    ("orden_trabajo", "mecanico_id"),
    ("movimiento_stock", "orden_id"),
    ("historial_estado_orden", "desde_estado"),
}


async def _columnas(conexion):
    res = await conexion.execute(
        text(
            "SELECT table_name, column_name, data_type, is_nullable, "
            "numeric_precision, numeric_scale FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name <> 'alembic_version'"
        )
    )
    return res.all()


async def test_todas_las_fechas_son_timestamptz(conexion):
    columnas = await _columnas(conexion)
    con_fecha = {(t, c, tipo) for t, c, tipo, *_ in columnas if tipo.startswith("timestamp")}
    assert {(t, c) for t, c, _ in con_fecha} == FECHAS
    assert {tipo for *_, tipo in con_fecha} == {"timestamp with time zone"}


async def test_el_dinero_es_numeric_con_precision_y_escala(conexion):
    columnas = await _columnas(conexion)
    numericas = {(t, c): (p, e) for t, c, tipo, _, p, e in columnas if tipo == "numeric"}
    assert numericas == DINERO


async def test_solo_son_nulas_las_columnas_de_la_spec(conexion):
    columnas = await _columnas(conexion)
    nulas = {(t, c) for t, c, _, nulo, *_ in columnas if nulo == "YES"}
    assert nulas == NULOS


async def test_un_instante_con_microsegundos_se_guarda_y_se_lee_con_zona(conexion):
    instante = datetime(2026, 10, 25, 12, 30, 45, 123456, tzinfo=timezone.utc)
    id_ = await insertar(conexion, "evento_seguridad", cuando=instante)
    leido = (
        await conexion.execute(text("SELECT cuando FROM evento_seguridad WHERE id = :i"), {"i": id_})
    ).scalar_one()
    assert leido.tzinfo is not None
    assert leido == instante and leido.microsecond == 123456


async def test_un_instante_con_otra_zona_se_guarda_como_el_mismo_instante(conexion):
    instante = datetime(2026, 1, 2, 3, 4, 5, 654321, tzinfo=timezone(timedelta(hours=-3)))
    id_ = await insertar(conexion, "evento_seguridad", cuando=instante)
    leido = (
        await conexion.execute(text("SELECT cuando FROM evento_seguridad WHERE id = :i"), {"i": id_})
    ).scalar_one()
    assert leido == instante and leido.utcoffset() is not None


async def test_un_precio_se_lee_como_decimal_exacto(conexion):
    id_ = await insertar(conexion, "repuesto", precio=Decimal("8500.00"))
    leido = (await conexion.execute(text("SELECT precio FROM repuesto WHERE id = :i"), {"i": id_})).scalar_one()
    assert leido == Decimal("8500.00") and isinstance(leido, Decimal)
    otro = await insertar(conexion, "repuesto", precio=Decimal("0.05"))
    leido = (await conexion.execute(text("SELECT precio FROM repuesto WHERE id = :i"), {"i": otro})).scalar_one()
    assert leido == Decimal("0.05")


# --- 4.7 restricciones contra la base ----------------------------------------


async def _dup_email(c):
    await insertar(c, "usuario", email="dup@example.com")
    await insertar(c, "usuario", email="dup@example.com")


async def _dup_documento(c):
    await insertar(c, "cliente", documento="123")
    await insertar(c, "cliente", documento="123")


async def _dup_cliente_usuario(c):
    u = await insertar(c, "usuario")
    await insertar(c, "cliente", usuario_id=u)
    await insertar(c, "cliente", usuario_id=u)


async def _dup_item(c):
    e = await escenario(c)
    await insertar(c, "item_orden", orden_id=e["orden"], repuesto_id=e["repuesto"])
    await insertar(c, "item_orden", orden_id=e["orden"], repuesto_id=e["repuesto"], cantidad=2)


async def _dup_posicion(c):
    await insertar(c, "estado_orden", posicion=900)
    await insertar(c, "estado_orden", posicion=900)


async def _rol(c, rol):
    u = await insertar(c, "usuario")
    await insertar(c, "asignacion_rol", usuario_id=u, rol=rol)


async def _anio(c, anio):
    e = await escenario(c, catalogo=False)
    await insertar(c, "vehiculo", cliente_id=e["cliente"], anio=anio)


async def _repuesto(c, **v):
    await insertar(c, "repuesto", **v)


async def _total(c, total):
    e = await escenario(c)
    await insertar(c, "orden_trabajo", vehiculo_id=e["vehiculo"], total=total)


async def _item(c, **v):
    e = await escenario(c)
    await insertar(c, "item_orden", orden_id=e["orden"], repuesto_id=e["repuesto"], **v)


async def _mov(c, cantidad):
    e = await escenario(c, catalogo=False)
    await insertar(c, "movimiento_stock", repuesto_id=e["repuesto"], usuario_id=e["usuario"], cantidad=cantidad)


async def _hp(c, anterior, nuevo):
    e = await escenario(c, catalogo=False)
    await insertar(
        c, "historial_precio_repuesto", repuesto_id=e["repuesto"], usuario_id=e["usuario"],
        precio_anterior=anterior, precio_nuevo=nuevo,
    )


PROHIBIDOS = [
    (_dup_email, "uq_usuario_email"),
    (_dup_documento, "uq_cliente_documento"),
    (_dup_cliente_usuario, "uq_cliente_usuario_id"),
    (_dup_item, "uq_item_orden_orden_id_repuesto_id"),
    (_dup_posicion, "uq_estado_orden_posicion"),
    (lambda c: _rol(c, "JEFE"), "ck_asignacion_rol_rol_valido"),
    (lambda c: _anio(c, 1949), "ck_vehiculo_anio_rango"),
    (lambda c: _anio(c, 2101), "ck_vehiculo_anio_rango"),
    (lambda c: _repuesto(c, precio=0), "ck_repuesto_precio_positivo"),
    (lambda c: _repuesto(c, stock=-1), "ck_repuesto_stock_no_negativo"),
    (lambda c: _total(c, Decimal("-0.01")), "ck_orden_trabajo_total_no_negativo"),
    (lambda c: _item(c, cantidad=0), "ck_item_orden_cantidad_positiva"),
    (lambda c: _item(c, precio_unitario=0), "ck_item_orden_precio_unitario_positivo"),
    (lambda c: _mov(c, 0), "ck_movimiento_stock_cantidad_no_cero"),
    (lambda c: _hp(c, 10, 0), "ck_historial_precio_repuesto_precio_nuevo_positivo"),
    (lambda c: _hp(c, 10, 10), "ck_historial_precio_repuesto_precio_distinto"),
]


@pytest.mark.parametrize(
    "operacion,esperado", PROHIBIDOS, ids=[f"{p[1]}-{i}" for i, p in enumerate(PROHIBIDOS)]
)
async def test_la_base_rechaza_lo_prohibido_con_el_nombre_de_la_spec(conexion, operacion, esperado):
    error = await rechaza(conexion, lambda: operacion(conexion))
    assert constraint_name(error) == esperado


async def test_valores_borde_aceptados(conexion):
    await _anio(conexion, 1950)
    await _anio(conexion, 2100)
    await _repuesto(conexion, stock=0)
    await _total(conexion, 0)
    await _mov(conexion, 5)
    await _mov(conexion, -3)


async def test_dos_clientes_sin_usuario_conviven(conexion):
    await insertar(conexion, "cliente", usuario_id=None)
    await insertar(conexion, "cliente", usuario_id=None)


# --- 4.8 índices únicos parciales --------------------------------------------


async def test_patente_vigente_repetida_falla_y_tras_la_baja_se_acepta(conexion):
    e = await escenario(conexion, catalogo=False)
    primero = await insertar(conexion, "vehiculo", cliente_id=e["cliente"], patente="AA111AA")
    error = await rechaza(
        conexion, lambda: insertar(conexion, "vehiculo", cliente_id=e["cliente"], patente="AA111AA")
    )
    assert constraint_name(error) == "uq_vehiculo_patente_vigente"
    vehiculos = table("vehiculo", column("id"), column("borrado_en"))
    await conexion.execute(vehiculos.update().where(vehiculos.c.id == primero).values(borrado_en=ahora()))
    await insertar(conexion, "vehiculo", cliente_id=e["cliente"], patente="AA111AA")


async def test_codigo_de_repuesto_vigente_repetido_falla_y_tras_la_baja_se_acepta(conexion):
    primero = await insertar(conexion, "repuesto", codigo="FIL-001")
    error = await rechaza(conexion, lambda: insertar(conexion, "repuesto", codigo="FIL-001"))
    assert constraint_name(error) == "uq_repuesto_codigo_vigente"
    repuestos = table("repuesto", column("id"), column("borrado_en"))
    await conexion.execute(repuestos.update().where(repuestos.c.id == primero).values(borrado_en=ahora()))
    await insertar(conexion, "repuesto", codigo="FIL-001")


async def test_asignacion_abierta_repetida_falla_y_tras_revocar_se_acepta(conexion):
    u = await insertar(conexion, "usuario")
    primera = await insertar(conexion, "asignacion_rol", usuario_id=u, rol="ADMIN")
    error = await rechaza(conexion, lambda: insertar(conexion, "asignacion_rol", usuario_id=u, rol="ADMIN"))
    assert constraint_name(error) == "uq_asignacion_rol_abierta"
    asignaciones = table("asignacion_rol", column("id"), column("revocada_en"))
    await conexion.execute(asignaciones.update().where(asignaciones.c.id == primera).values(revocada_en=ahora()))
    await insertar(conexion, "asignacion_rol", usuario_id=u, rol="ADMIN")


async def test_roles_distintos_abiertos_del_mismo_usuario_se_aceptan(conexion):
    u = await insertar(conexion, "usuario")
    await insertar(conexion, "asignacion_rol", usuario_id=u, rol="ADMIN")
    await insertar(conexion, "asignacion_rol", usuario_id=u, rol="MECANICO")


# --- 4.9 claves foráneas e índices -------------------------------------------


async def test_estado_fuera_del_catalogo_falla_aunque_haya_catalogo(conexion):
    e = await escenario(conexion)
    error = await rechaza(
        conexion, lambda: insertar(conexion, "orden_trabajo", vehiculo_id=e["vehiculo"], estado="DEMORADA")
    )
    assert constraint_name(error) == "fk_orden_trabajo_estado_estado_orden"


async def test_estado_valido_con_el_catalogo_vacio_tambien_falla(conexion):
    e = await escenario(conexion, catalogo=False)
    error = await rechaza(
        conexion, lambda: insertar(conexion, "orden_trabajo", vehiculo_id=e["vehiculo"], estado="PENDIENTE")
    )
    assert constraint_name(error) == "fk_orden_trabajo_estado_estado_orden"


async def test_cliente_inexistente_falla_por_la_fk(conexion):
    error = await rechaza(conexion, lambda: insertar(conexion, "vehiculo", cliente_id=999999))
    assert constraint_name(error) == "fk_vehiculo_cliente_id_cliente"


async def test_cada_fk_tiene_un_indice_que_empieza_por_su_columna(conexion):
    res = await conexion.execute(
        text(
            """
            SELECT c.conrelid::regclass::text AS tabla, a.attname AS columna,
                   EXISTS (SELECT 1 FROM pg_index i
                           WHERE i.indrelid = c.conrelid AND i.indkey[0] = c.conkey[1]) AS con_indice
            FROM pg_constraint c
            JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
            WHERE c.contype = 'f' AND c.connamespace = 'public'::regnamespace
            """
        )
    )
    filas = res.all()
    assert len(filas) == 18
    assert [(t, c) for t, c, ok in filas if not ok] == []


async def test_intento_acceso_tiene_el_indice_email_ip_cuando_en_ese_orden(conexion):
    res = await conexion.execute(
        text(
            """
            SELECT array_agg(a.attname ORDER BY k.ord)
            FROM pg_index i
            JOIN pg_class ci ON ci.oid = i.indexrelid
            CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum
            WHERE ci.relname = 'ix_intento_acceso_email_ip_cuando'
            """
        )
    )
    assert res.scalar_one() == ["email", "ip", "cuando"]


# --- 4.10 navegación y carga perezosa ----------------------------------------


@pytest.fixture
async def sesion(conexion):
    async with AsyncSession(
        bind=conexion, join_transaction_mode="create_savepoint", expire_on_commit=False
    ) as s:
        yield s


@pytest.fixture
def sentencias(motor):
    ejecutadas = []

    def _contar(conn, cursor, statement, *args):
        ejecutadas.append(statement)

    event.listen(motor.sync_engine, "before_cursor_execute", _contar)
    yield ejecutadas
    event.remove(motor.sync_engine, "before_cursor_execute", _contar)


async def test_usuario_con_cliente_precargado_navega_en_los_dos_sentidos(conexion, sesion):
    e = await escenario(conexion)
    sin_cliente = await insertar(conexion, "usuario")
    usuarios = (
        await sesion.exec(
            select(m.Usuario)
            .options(selectinload(m.Usuario.cliente))
            .where(m.Usuario.id.in_([e["usuario"], sin_cliente]))
        )
    ).all()
    por_id = {u.id: u for u in usuarios}
    assert isinstance(por_id[e["usuario"]].cliente, m.Cliente)
    assert por_id[sin_cliente].cliente is None
    cliente = (
        await sesion.exec(
            select(m.Cliente).options(selectinload(m.Cliente.usuario)).where(m.Cliente.id == e["cliente"])
        )
    ).one()
    assert cliente.usuario is por_id[e["usuario"]]


async def test_orden_con_items_y_repuestos_precargados(conexion, sesion):
    e = await escenario(conexion)
    await insertar(conexion, "item_orden", orden_id=e["orden"], repuesto_id=e["repuesto"], cantidad=3)
    orden = (
        await sesion.exec(
            select(m.OrdenTrabajo)
            .options(selectinload(m.OrdenTrabajo.items).selectinload(m.ItemOrden.repuesto))
            .where(m.OrdenTrabajo.id == e["orden"])
        )
    ).one()
    assert [(i.cantidad, i.repuesto.id) for i in orden.items] == [(3, e["repuesto"])]


async def test_la_carga_perezosa_falla_en_el_acto_sin_consultar(conexion, sesion, sentencias):
    e = await escenario(conexion)
    cliente = (await sesion.exec(select(m.Cliente).where(m.Cliente.id == e["cliente"]))).one()
    antes = len(sentencias)
    with pytest.raises(InvalidRequestError):
        cliente.vehiculos
    assert len(sentencias) == antes


async def test_precargado_el_acceso_devuelve_la_lista(conexion, sesion, sentencias):
    e = await escenario(conexion)
    cliente = (
        await sesion.exec(
            select(m.Cliente).options(selectinload(m.Cliente.vehiculos)).where(m.Cliente.id == e["cliente"])
        )
    ).one()
    antes = len(sentencias)
    assert [v.id for v in cliente.vehiculos] == [e["vehiculo"]]
    assert len(sentencias) == antes
