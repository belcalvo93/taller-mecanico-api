"""Tablas de sólo agregado (RN-15, caso C-14): la base rechaza UPDATE y DELETE
en historial_estado_orden, movimiento_stock e historial_precio_repuesto.
Todo corre en la transacción revertida de la fixture `conexion`."""
import pytest
from sqlalchemy import column, func, select, table

from tests.helpers import constraint_name, escenario, insertar, rechaza

FRASE = "sólo agregado"


async def _fila_historial_estado(c, e):
    return await insertar(c, "historial_estado_orden", orden_id=e["orden"], usuario_id=e["usuario"])


async def _fila_movimiento(c, e):
    return await insertar(c, "movimiento_stock", repuesto_id=e["repuesto"], usuario_id=e["usuario"])


async def _fila_precio(c, e):
    return await insertar(c, "historial_precio_repuesto", repuesto_id=e["repuesto"], usuario_id=e["usuario"])


# (tabla, creador de fila válida, columna a intentar cambiar, nuevo valor)
TABLAS = [
    ("historial_estado_orden", _fila_historial_estado, "hasta_estado", "EN_REPARACION"),
    ("movimiento_stock", _fila_movimiento, "motivo", "Otro motivo"),
    ("historial_precio_repuesto", _fila_precio, "precio_nuevo", 999),
]
IDS = [t[0] for t in TABLAS]


def _t(nombre, *columnas):
    return table(nombre, column("id"), *[column(c) for c in columnas])


@pytest.mark.parametrize("tabla,crear,columna,nuevo", TABLAS, ids=IDS)
async def test_se_puede_agregar_una_fila_valida(conexion, tabla, crear, columna, nuevo):
    e = await escenario(conexion)
    id_ = await crear(conexion, e)
    t = _t(tabla)
    assert (await conexion.execute(select(func.count()).select_from(t).where(t.c.id == id_))).scalar_one() == 1


@pytest.mark.parametrize("tabla,crear,columna,nuevo", TABLAS, ids=IDS)
async def test_el_update_se_rechaza_con_el_nombre_de_la_tabla_y_la_fila_no_cambia(
    conexion, tabla, crear, columna, nuevo
):
    e = await escenario(conexion)
    id_ = await crear(conexion, e)
    t = _t(tabla, columna)
    antes = (await conexion.execute(select(t.c[columna]).where(t.c.id == id_))).scalar_one()

    error = await rechaza(
        conexion, lambda: conexion.execute(t.update().where(t.c.id == id_).values({columna: nuevo}))
    )

    mensaje = str(error.orig)
    assert FRASE in mensaje and tabla in mensaje
    despues = (await conexion.execute(select(t.c[columna]).where(t.c.id == id_))).scalar_one()
    assert despues == antes


async def _filas(c, tabla):
    t = _t(tabla)
    return (await c.execute(select(func.count()).select_from(t))).scalar_one()


@pytest.mark.parametrize("tabla,crear,columna,nuevo", TABLAS, ids=IDS)
async def test_el_delete_se_rechaza_y_la_cantidad_de_filas_no_cambia(conexion, tabla, crear, columna, nuevo):
    e = await escenario(conexion)
    id_ = await crear(conexion, e)
    t = _t(tabla)
    antes = await _filas(conexion, tabla)

    error = await rechaza(conexion, lambda: conexion.execute(t.delete().where(t.c.id == id_)))

    assert FRASE in str(error.orig) and tabla in str(error.orig)
    assert await _filas(conexion, tabla) == antes == 1


@pytest.mark.parametrize("tabla,crear,columna,nuevo", TABLAS, ids=IDS)
async def test_update_y_delete_que_no_tocan_filas_tambien_se_rechazan(conexion, tabla, crear, columna, nuevo):
    # Tabla vacía y WHERE falso: el disparador es por sentencia, no por fila.
    t = _t(tabla, columna)
    assert await _filas(conexion, tabla) == 0
    error = await rechaza(conexion, lambda: conexion.execute(t.update().where(t.c.id == -1).values({columna: nuevo})))
    assert FRASE in str(error.orig)
    error = await rechaza(conexion, lambda: conexion.execute(t.delete().where(t.c.id == -1)))
    assert FRASE in str(error.orig)


async def test_las_demas_tablas_siguen_aceptando_update(conexion):
    e = await escenario(conexion)
    repuestos = _t("repuesto", "precio")
    ordenes = _t("orden_trabajo", "falla")
    await conexion.execute(repuestos.update().where(repuestos.c.id == e["repuesto"]).values(precio=555))
    await conexion.execute(ordenes.update().where(ordenes.c.id == e["orden"]).values(falla="Otra falla"))
    assert (await conexion.execute(select(repuestos.c.precio).where(repuestos.c.id == e["repuesto"]))).scalar_one() == 555
    assert (await conexion.execute(select(ordenes.c.falla).where(ordenes.c.id == e["orden"]))).scalar_one() == "Otra falla"


async def test_truncate_de_las_tres_tablas_se_acepta(conexion):
    e = await escenario(conexion)
    for crear in (_fila_historial_estado, _fila_movimiento, _fila_precio):
        await crear(conexion, e)
    # Nombres fijos de las tres tablas de sólo agregado.
    await conexion.exec_driver_sql(
        "TRUNCATE historial_estado_orden, movimiento_stock, historial_precio_repuesto"
    )
    for tabla, *_ in TABLAS:
        assert await _filas(conexion, tabla) == 0


# --- test/solo_agregado.sql (caso C-14) ------------------------------------------

import re  # noqa: E402
from pathlib import Path  # noqa: E402

from sqlalchemy.exc import DBAPIError  # noqa: E402

SCRIPT = Path(__file__).resolve().parent.parent / "test" / "solo_agregado.sql"


def sentencias_del_script() -> list[str]:
    """Separa las sentencias ignorando comentarios `--` y metacomandos de psql (líneas que empiezan con barra invertida)."""
    lineas = [
        l for l in SCRIPT.read_text(encoding="utf-8").splitlines()
        if l.strip() and not l.lstrip().startswith(("--", "\\"))
    ]
    return [s.strip() for s in " ".join(lineas).split(";") if s.strip()]


async def _ejecutar_en_su_transaccion(motor, sentencia):
    async with motor.connect() as c:
        trans = await c.begin()
        try:
            await c.exec_driver_sql(sentencia)
        finally:
            await trans.rollback()


async def test_script_c14_tiene_siete_rechazos(sembrada):
    sentencias = sentencias_del_script()
    assert len(sentencias) == 7
    for sentencia in sentencias[:6]:
        with pytest.raises(DBAPIError) as exc:
            await _ejecutar_en_su_transaccion(sembrada, sentencia)
        assert FRASE in str(exc.value.orig), sentencia
    with pytest.raises(DBAPIError) as exc:
        await _ejecutar_en_su_transaccion(sembrada, sentencias[6])
    assert constraint_name(exc.value) == "fk_orden_trabajo_estado_estado_orden"


async def _tablas_tocadas(motor):
    resultado = {}
    async with motor.connect() as c:
        for tabla in ("historial_estado_orden", "movimiento_stock", "historial_precio_repuesto", "orden_trabajo"):
            filas = (await c.exec_driver_sql(f"SELECT * FROM {tabla} ORDER BY id")).all()  # nombres fijos
            resultado[tabla] = [tuple(f) for f in filas]
    return resultado


async def test_el_script_no_modifica_datos_y_no_tiene_transacciones_explicitas(sembrada):
    antes = await _tablas_tocadas(sembrada)
    for sentencia in sentencias_del_script():
        # como psql en autocommit: cada sentencia en su transacción, con intento de commit
        with pytest.raises(DBAPIError):
            async with sembrada.begin() as c:
                await c.exec_driver_sql(sentencia)
    assert await _tablas_tocadas(sembrada) == antes
    assert [len(f) for f in antes.values()] == [3, 4, 1, 2]
    texto = SCRIPT.read_text(encoding="utf-8").upper()
    assert not re.search(r"^\s*(BEGIN|COMMIT|START TRANSACTION)\b", texto, re.MULTILINE)
