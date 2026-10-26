"""Modelos del taller sin base de datos (CH-02): convención de nombres, hora UTC,
tablas, columnas, nulos, tipos, restricciones, índices y relaciones. Lo que
necesita la base real vive en test_esquema.py."""
import os
import re
import subprocess
import sys
import time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, DateTime, Numeric, UniqueConstraint
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import configure_mappers
from sqlmodel import SQLModel

import app.core.database as database


def test_convencion_de_nombres():
    convencion = SQLModel.metadata.naming_convention
    assert convencion == {
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_N_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
    assert database.NAMING_CONVENTION == convencion


def test_ahora_utc_devuelve_hora_con_zona_utc():
    ahora = database.ahora_utc()
    assert ahora.tzinfo is not None
    assert ahora.utcoffset() == timedelta(0)


def test_ahora_utc_es_actual_y_no_decrece():
    antes = time.time()
    primera = database.ahora_utc()
    segunda = database.ahora_utc()
    assert segunda >= primera
    assert abs(primera.timestamp() - antes) < 5
    # conserva las fracciones de segundo (no se trunca)
    muestras = {database.ahora_utc().microsecond for _ in range(50)}
    assert len(muestras) > 1


# --- Registro de modelos (2.1) ---

TABLAS = {
    "usuario", "asignacion_rol", "intento_acceso", "evento_seguridad",
    "cliente", "vehiculo",
    "repuesto", "movimiento_stock", "historial_precio_repuesto",
    "estado_orden", "orden_trabajo", "item_orden", "historial_estado_orden",
}
CLASES = {
    "Usuario", "AsignacionRol", "IntentoAcceso", "EventoSeguridad",
    "Cliente", "Vehiculo",
    "Repuesto", "MovimientoStock", "HistorialPrecio",
    "EstadoOrden", "OrdenTrabajo", "ItemOrden", "HistorialEstadoOrden",
}


def test_el_registro_expone_las_13_clases():
    import app.modules.modelos as modelos

    for nombre in CLASES:
        assert hasattr(modelos, nombre), nombre


def test_la_metadata_tiene_exactamente_las_13_tablas():
    import app.modules.modelos  # noqa: F401

    assert set(SQLModel.metadata.tables) == TABLAS


# --- Helpers de inspección de la metadata (sin base de datos) ---

def _tabla(nombre):
    import app.modules.modelos  # noqa: F401

    return SQLModel.metadata.tables[nombre]


def _nombres_unique(tabla):
    return {c.name for c in tabla.constraints if isinstance(c, UniqueConstraint)}


def _nombres_check(tabla):
    return {c.name for c in tabla.constraints if isinstance(c, CheckConstraint)}


def _ddl(tabla):
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.schema import CreateTable

    return str(CreateTable(tabla).compile(dialect=postgresql.dialect()))


def _indice(tabla, nombre):
    (indice,) = [i for i in tabla.indexes if i.name == nombre]
    return indice


def _where(indice):
    return str(indice.dialect_options["postgresql"]["where"])


# --- 2.2 Módulo usuarios ---

# tabla -> (columnas, columnas que aceptan NULL, columnas con fecha y zona)
USUARIOS = {
    "usuario": (
        {"id", "email", "nombre", "password_hash", "activo",
         "debe_cambiar_password", "password_cambiada_en"},
        {"password_cambiada_en"},
        {"password_cambiada_en"},
    ),
    "asignacion_rol": (
        {"id", "usuario_id", "rol", "desde", "vence_en", "revocada_en", "otorgada_por"},
        {"vence_en", "revocada_en", "otorgada_por"},
        {"desde", "vence_en", "revocada_en"},
    ),
    "intento_acceso": (
        {"id", "cuando", "email", "ip", "exito"},
        set(),
        {"cuando"},
    ),
    "evento_seguridad": (
        {"id", "cuando", "actor", "accion"},
        set(),
        {"cuando"},
    ),
}


@pytest.mark.parametrize("nombre", USUARIOS)
def test_usuarios_columnas_exactas(nombre):
    assert set(_tabla(nombre).columns.keys()) == USUARIOS[nombre][0]


@pytest.mark.parametrize("nombre", USUARIOS)
def test_usuarios_solo_estas_columnas_aceptan_null(nombre):
    nulables = {c.name for c in _tabla(nombre).columns if c.nullable}
    assert nulables == USUARIOS[nombre][1]


@pytest.mark.parametrize("nombre", USUARIOS)
def test_usuarios_fechas_con_zona_horaria(nombre):
    tabla = _tabla(nombre)
    for col in USUARIOS[nombre][2]:
        tipo = tabla.columns[col].type
        assert isinstance(tipo, DateTime) and tipo.timezone is True, col


def test_usuario_no_tiene_columna_rol():
    assert "rol" not in _tabla("usuario").columns


def test_usuario_email_unico_con_nombre_fijo():
    assert "uq_usuario_email" in _nombres_unique(_tabla("usuario"))


def test_asignacion_rol_check_con_nombre_fijo_y_roles_validos():
    tabla = _tabla("asignacion_rol")
    (check,) = [c for c in tabla.constraints if isinstance(c, CheckConstraint)]
    assert check.name == "ck_asignacion_rol_rol_valido"
    for rol in ("ADMIN", "RECEPCION", "MECANICO", "CLIENTE"):
        assert rol in str(check.sqltext)


def test_asignacion_rol_indice_unico_parcial():
    indice = _indice(_tabla("asignacion_rol"), "uq_asignacion_rol_abierta")
    assert indice.unique is True
    assert [c.name for c in indice.columns] == ["usuario_id", "rol"]
    assert _where(indice) == "revocada_en IS NULL"


def test_intento_acceso_indice_email_ip_cuando_en_ese_orden():
    indice = _indice(_tabla("intento_acceso"), "ix_intento_acceso_email_ip_cuando")
    assert [c.name for c in indice.columns] == ["email", "ip", "cuando"]


def test_asignacion_rol_fk_a_usuario_con_indice():
    tabla = _tabla("asignacion_rol")
    destinos = {fk.parent.name: fk.target_fullname for fk in tabla.foreign_keys}
    assert destinos == {"usuario_id": "usuario.id", "otorgada_por": "usuario.id"}
    indexadas = {i.columns.keys()[0] for i in tabla.indexes}
    assert {"usuario_id", "otorgada_por"} <= indexadas


# --- 2.3 Módulo clientes ---

CLIENTES = {
    "cliente": (
        {"id", "usuario_id", "nombre", "documento", "telefono"},
        {"usuario_id"},
        set(),
    ),
    "vehiculo": (
        {"id", "cliente_id", "patente", "marca", "modelo", "anio", "borrado_en"},
        {"borrado_en"},
        {"borrado_en"},
    ),
}


@pytest.mark.parametrize("nombre", CLIENTES)
def test_clientes_columnas_nulos_y_fechas(nombre):
    columnas, nulos, fechas = CLIENTES[nombre]
    tabla = _tabla(nombre)
    assert set(tabla.columns.keys()) == columnas
    assert {c.name for c in tabla.columns if c.nullable} == nulos
    for col in fechas:
        tipo = tabla.columns[col].type
        assert isinstance(tipo, DateTime) and tipo.timezone is True


def test_cliente_unicos_usuario_id_y_documento():
    assert {"uq_cliente_usuario_id", "uq_cliente_documento"} <= _nombres_unique(
        _tabla("cliente")
    )


def test_vehiculo_check_anio_entre_1950_y_2100():
    tabla = _tabla("vehiculo")
    (check,) = [c for c in tabla.constraints if isinstance(c, CheckConstraint)]
    assert check.name == "ck_vehiculo_anio_rango"
    assert "1950" in str(check.sqltext) and "2100" in str(check.sqltext)


def test_vehiculo_patente_unica_solo_entre_vigentes():
    tabla = _tabla("vehiculo")
    indice = _indice(tabla, "uq_vehiculo_patente_vigente")
    assert indice.unique is True
    assert [c.name for c in indice.columns] == ["patente"]
    assert _where(indice) == "borrado_en IS NULL"
    # la patente NO es UNIQUE común (la consigna lo prohíbe)
    assert not any(
        [c.name for c in u.columns] == ["patente"]
        for u in tabla.constraints
        if isinstance(u, UniqueConstraint)
    )


def test_cliente_y_vehiculo_fk():
    destinos = {
        (t, fk.parent.name): fk.target_fullname
        for t in ("cliente", "vehiculo")
        for fk in _tabla(t).foreign_keys
    }
    assert destinos == {
        ("cliente", "usuario_id"): "usuario.id",
        ("vehiculo", "cliente_id"): "cliente.id",
    }
    assert "cliente_id" in {i.columns.keys()[0] for i in _tabla("vehiculo").indexes}


# --- 2.4 Módulo repuestos ---

REPUESTOS = {
    "repuesto": (
        {"id", "codigo", "descripcion", "precio", "stock", "borrado_en"},
        {"borrado_en"},
        {"borrado_en"},
    ),
    "movimiento_stock": (
        {"id", "repuesto_id", "orden_id", "usuario_id", "cantidad", "motivo", "cuando"},
        {"orden_id"},
        {"cuando"},
    ),
    "historial_precio_repuesto": (
        {"id", "repuesto_id", "usuario_id", "precio_anterior", "precio_nuevo", "cuando"},
        set(),
        {"cuando"},
    ),
}


@pytest.mark.parametrize("nombre", REPUESTOS)
def test_repuestos_columnas_nulos_y_fechas(nombre):
    columnas, nulos, fechas = REPUESTOS[nombre]
    tabla = _tabla(nombre)
    assert set(tabla.columns.keys()) == columnas
    assert {c.name for c in tabla.columns if c.nullable} == nulos
    for col in fechas:
        tipo = tabla.columns[col].type
        assert isinstance(tipo, DateTime) and tipo.timezone is True


@pytest.mark.parametrize(
    "tabla, columna",
    [
        ("repuesto", "precio"),
        ("historial_precio_repuesto", "precio_anterior"),
        ("historial_precio_repuesto", "precio_nuevo"),
    ],
)
def test_dinero_de_repuestos_es_numeric_10_2_y_decimal(tabla, columna):
    tipo = _tabla(tabla).columns[columna].type
    assert isinstance(tipo, Numeric)
    assert (tipo.precision, tipo.scale) == (10, 2)
    assert tipo.asdecimal is True


def test_dinero_de_repuestos_se_anota_como_decimal_y_no_float():
    from app.modules.repuestos.models import HistorialPrecio, Repuesto

    assert Repuesto.model_fields["precio"].annotation is Decimal
    for campo in ("precio_anterior", "precio_nuevo"):
        assert HistorialPrecio.model_fields[campo].annotation is Decimal


def test_repuesto_checks_con_nombre_fijo():
    assert _nombres_check(_tabla("repuesto")) == {
        "ck_repuesto_precio_positivo",
        "ck_repuesto_stock_no_negativo",
    }


def test_repuesto_codigo_unico_solo_entre_vigentes():
    indice = _indice(_tabla("repuesto"), "uq_repuesto_codigo_vigente")
    assert indice.unique is True
    assert [c.name for c in indice.columns] == ["codigo"]
    assert _where(indice) == "borrado_en IS NULL"


def test_movimiento_stock_check_cantidad_no_cero():
    assert _nombres_check(_tabla("movimiento_stock")) == {
        "ck_movimiento_stock_cantidad_no_cero"
    }


def test_historial_precio_checks_con_nombre_fijo():
    assert _nombres_check(_tabla("historial_precio_repuesto")) == {
        "ck_historial_precio_repuesto_precio_nuevo_positivo",
        "ck_historial_precio_repuesto_precio_distinto",
    }


def test_repuestos_fk():
    destinos = {
        (t, fk.parent.name): fk.target_fullname
        for t in REPUESTOS
        for fk in _tabla(t).foreign_keys
    }
    assert destinos == {
        ("movimiento_stock", "repuesto_id"): "repuesto.id",
        ("movimiento_stock", "orden_id"): "orden_trabajo.id",
        ("movimiento_stock", "usuario_id"): "usuario.id",
        ("historial_precio_repuesto", "repuesto_id"): "repuesto.id",
        ("historial_precio_repuesto", "usuario_id"): "usuario.id",
    }


# --- 2.5 Módulo ordenes ---

ORDENES = {
    "estado_orden": (
        {"codigo", "descripcion", "posicion", "es_final"},
        set(),
        set(),
    ),
    "orden_trabajo": (
        {"id", "vehiculo_id", "mecanico_id", "estado", "falla", "creada_en", "total"},
        {"mecanico_id"},
        {"creada_en"},
    ),
    "item_orden": (
        {"id", "orden_id", "repuesto_id", "cantidad", "precio_unitario"},
        set(),
        set(),
    ),
    "historial_estado_orden": (
        {"id", "orden_id", "desde_estado", "hasta_estado", "usuario_id", "cuando"},
        {"desde_estado"},
        {"cuando"},
    ),
}


@pytest.mark.parametrize("nombre", ORDENES)
def test_ordenes_columnas_nulos_y_fechas(nombre):
    columnas, nulos, fechas = ORDENES[nombre]
    tabla = _tabla(nombre)
    assert set(tabla.columns.keys()) == columnas
    assert {c.name for c in tabla.columns if c.nullable} == nulos
    for col in fechas:
        tipo = tabla.columns[col].type
        assert isinstance(tipo, DateTime) and tipo.timezone is True


def test_estado_orden_tiene_por_clave_primaria_el_codigo():
    tabla = _tabla("estado_orden")
    assert [c.name for c in tabla.primary_key.columns] == ["codigo"]
    assert "uq_estado_orden_posicion" in _nombres_unique(tabla)


@pytest.mark.parametrize(
    "tabla, columna",
    [
        ("orden_trabajo", "estado"),
        ("historial_estado_orden", "desde_estado"),
        ("historial_estado_orden", "hasta_estado"),
    ],
)
def test_los_estados_son_fk_al_catalogo(tabla, columna):
    (fk,) = [f for f in _tabla(tabla).foreign_keys if f.parent.name == columna]
    assert fk.target_fullname == "estado_orden.codigo"


def test_ningun_check_de_ordenes_enumera_estados():
    estados = ("PENDIENTE", "EN_REPARACION", "TERMINADA", "CANCELADA")
    for nombre in ("orden_trabajo", "historial_estado_orden", "estado_orden"):
        for c in _tabla(nombre).constraints:
            if isinstance(c, CheckConstraint):
                assert not any(e in str(c.sqltext) for e in estados), c.name


def test_orden_trabajo_total_numeric_12_2_no_negativo():
    tabla = _tabla("orden_trabajo")
    tipo = tabla.columns["total"].type
    assert (tipo.precision, tipo.scale) == (12, 2)
    assert _nombres_check(tabla) == {"ck_orden_trabajo_total_no_negativo"}
    # El nombre de una FK se resuelve al generar el DDL, no antes.
    assert "CONSTRAINT fk_orden_trabajo_estado_estado_orden FOREIGN KEY" in _ddl(tabla)


def test_item_orden_dinero_checks_y_unico():
    tabla = _tabla("item_orden")
    tipo = tabla.columns["precio_unitario"].type
    assert (tipo.precision, tipo.scale) == (10, 2)
    assert _nombres_check(tabla) == {
        "ck_item_orden_cantidad_positiva",
        "ck_item_orden_precio_unitario_positivo",
    }
    assert "uq_item_orden_orden_id_repuesto_id" in _nombres_unique(tabla)
    (u,) = [
        c for c in tabla.constraints
        if isinstance(c, UniqueConstraint) and c.name == "uq_item_orden_orden_id_repuesto_id"
    ]
    assert [c.name for c in u.columns] == ["orden_id", "repuesto_id"]


def test_dinero_de_ordenes_se_anota_como_decimal():
    from app.modules.ordenes.models import ItemOrden, OrdenTrabajo

    assert OrdenTrabajo.model_fields["total"].annotation is Decimal
    assert ItemOrden.model_fields["precio_unitario"].annotation is Decimal


def test_fk_de_ordenes():
    destinos = {
        (t, fk.parent.name): fk.target_fullname
        for t in ORDENES
        for fk in _tabla(t).foreign_keys
    }
    assert destinos == {
        ("orden_trabajo", "vehiculo_id"): "vehiculo.id",
        ("orden_trabajo", "mecanico_id"): "usuario.id",
        ("orden_trabajo", "estado"): "estado_orden.codigo",
        ("item_orden", "orden_id"): "orden_trabajo.id",
        ("item_orden", "repuesto_id"): "repuesto.id",
        ("historial_estado_orden", "orden_id"): "orden_trabajo.id",
        ("historial_estado_orden", "desde_estado"): "estado_orden.codigo",
        ("historial_estado_orden", "hasta_estado"): "estado_orden.codigo",
        ("historial_estado_orden", "usuario_id"): "usuario.id",
    }


# --- 2.6 Registro importado por main.py ---

_RAIZ = Path(__file__).resolve().parent.parent


def _en_subproceso(codigo, cwd):
    """Importar sin .env ni secretos: ni los modelos ni main.py leen la config (regla 7)."""
    entorno = {
        k: v for k, v in os.environ.items() if k not in ("POSTGRES_PASSWORD", "JWT_SECRET_KEY")
    }
    entorno["PYTHONPATH"] = str(_RAIZ)
    return subprocess.run(
        [sys.executable, "-c", codigo], cwd=cwd, env=entorno,
        capture_output=True, text=True, timeout=60,
    )


def test_importar_main_registra_los_13_modelos(tmp_path):
    resultado = _en_subproceso(
        "import main\n"
        "from sqlmodel import SQLModel\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "assert len(SQLModel.metadata.tables) == 13, sorted(SQLModel.metadata.tables)\n"
        "configure_mappers()\n",
        tmp_path,
    )
    assert resultado.returncode == 0, resultado.stderr


def test_importar_un_solo_models_no_alcanza_para_configurar_los_mapeos(tmp_path):
    # Es la razón de ser de app/modules/modelos.py (design D6).
    resultado = _en_subproceso(
        "import app.modules.usuarios.models\n"
        "from sqlalchemy.orm import configure_mappers\n"
        "configure_mappers()\n",
        tmp_path,
    )
    assert resultado.returncode != 0
    assert "Cliente" in resultado.stderr


# --- 2.7 Nombres de restricciones (contrato para la traducción a 409) ---

NOMBRES_D3 = [
    ("usuario", "uq_usuario_email"),
    ("asignacion_rol", "ck_asignacion_rol_rol_valido"),
    ("asignacion_rol", "uq_asignacion_rol_abierta"),
    ("intento_acceso", "ix_intento_acceso_email_ip_cuando"),
    ("cliente", "uq_cliente_usuario_id"),
    ("cliente", "uq_cliente_documento"),
    ("vehiculo", "ck_vehiculo_anio_rango"),
    ("vehiculo", "uq_vehiculo_patente_vigente"),
    ("repuesto", "ck_repuesto_precio_positivo"),
    ("repuesto", "ck_repuesto_stock_no_negativo"),
    ("repuesto", "uq_repuesto_codigo_vigente"),
    ("estado_orden", "uq_estado_orden_posicion"),
    ("orden_trabajo", "ck_orden_trabajo_total_no_negativo"),
    ("orden_trabajo", "fk_orden_trabajo_estado_estado_orden"),
    ("item_orden", "uq_item_orden_orden_id_repuesto_id"),
    ("item_orden", "ck_item_orden_cantidad_positiva"),
    ("item_orden", "ck_item_orden_precio_unitario_positivo"),
    ("movimiento_stock", "ck_movimiento_stock_cantidad_no_cero"),
    ("historial_precio_repuesto", "ck_historial_precio_repuesto_precio_nuevo_positivo"),
    ("historial_precio_repuesto", "ck_historial_precio_repuesto_precio_distinto"),
]


@pytest.mark.parametrize("tabla, nombre", NOMBRES_D3)
def test_cada_restriccion_tiene_el_nombre_de_design_d3(tabla, nombre):
    t = _tabla(tabla)
    indices = {i.name for i in t.indexes}
    assert nombre in indices or f"CONSTRAINT {nombre} " in _ddl(t)


def test_todos_los_nombres_caben_en_63_caracteres():
    for t in SQLModel.metadata.sorted_tables:
        for nombre in re.findall(r"CONSTRAINT (\w+) ", _ddl(t)):
            assert len(nombre) <= 63, nombre
        for i in t.indexes:
            assert len(str(i.name)) <= 63, i.name


def test_cada_fk_tiene_un_indice_que_empieza_por_su_columna():
    _tabla("usuario")
    fks = [fk for t in SQLModel.metadata.sorted_tables for fk in t.foreign_keys]
    assert len(fks) == 18
    for fk in fks:
        t = fk.parent.table
        primeras = {i.columns.keys()[0] for i in t.indexes}
        primeras |= {
            c.columns.keys()[0] for c in t.constraints if isinstance(c, UniqueConstraint)
        }
        assert fk.parent.name in primeras, f"{t.name}.{fk.parent.name} sin índice"


# --- 2.8 Relaciones (design D5) ---


def _clases():
    import app.modules.modelos as m

    return {n: getattr(m, n) for n in CLASES}


# (clase A, relación A, clase B, relación B)
PARES = [
    ("Usuario", "asignaciones", "AsignacionRol", "usuario"),
    ("Usuario", "cliente", "Cliente", "usuario"),
    ("Cliente", "vehiculos", "Vehiculo", "cliente"),
    ("Vehiculo", "ordenes", "OrdenTrabajo", "vehiculo"),
    ("Usuario", "ordenes_asignadas", "OrdenTrabajo", "mecanico"),
    ("OrdenTrabajo", "items", "ItemOrden", "orden"),
    ("Repuesto", "items", "ItemOrden", "repuesto"),
    ("OrdenTrabajo", "historial", "HistorialEstadoOrden", "orden"),
    ("Repuesto", "movimientos", "MovimientoStock", "repuesto"),
    ("Repuesto", "historial_precios", "HistorialPrecio", "repuesto"),
    ("EstadoOrden", "ordenes", "OrdenTrabajo", "estado_orden"),
]


@pytest.mark.parametrize("a, rel_a, b, rel_b", PARES)
def test_cada_relacion_esta_declarada_en_los_dos_extremos(a, rel_a, b, rel_b):
    clases = _clases()
    ra = sa_inspect(clases[a]).relationships[rel_a]
    rb = sa_inspect(clases[b]).relationships[rel_b]
    assert ra.back_populates == rel_b and rb.back_populates == rel_a
    assert ra.mapper.class_ is clases[b] and rb.mapper.class_ is clases[a]


def test_todas_las_relaciones_son_lazy_raise():
    todas = [
        (nombre, r.key, r.lazy)
        for nombre, clase in _clases().items()
        for r in sa_inspect(clase).relationships
    ]
    assert len(todas) == 2 * len(PARES)
    assert all(lazy == "raise" for _, _, lazy in todas), todas


def test_usuario_cliente_devuelve_objeto_y_no_lista():
    clases = _clases()
    assert sa_inspect(clases["Usuario"]).relationships["cliente"].uselist is False
    assert sa_inspect(clases["Cliente"]).relationships["usuario"].uselist is False
    # las demás del lado "uno a muchos" sí son listas
    assert sa_inspect(clases["Cliente"]).relationships["vehiculos"].uselist is True


def test_los_items_son_composicion_de_la_orden():
    orden = sa_inspect(_clases()["OrdenTrabajo"]).relationships
    assert orden["items"].cascade.delete_orphan is True
    assert orden["items"].cascade.delete is True
    # el historial no se borra en cascada (es de sólo agregado)
    assert orden["historial"].cascade.delete is False
    assert orden["historial"].cascade.delete_orphan is False


def test_configure_mappers_no_lanza_error():
    _clases()
    configure_mappers()
