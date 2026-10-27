"""Alembic asincrónico sin credenciales (CH-02, regla 8) y comportamiento de las
migraciones. Los tests de la base real de las migraciones viven en test_esquema.py."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
ALEMBIC_INI = RAIZ / "alembic.ini"
ENV_PY = RAIZ / "migrations" / "env.py"


def test_alembic_ini_existe_y_no_tiene_credenciales():
    assert ALEMBIC_INI.is_file(), "falta alembic.ini"
    texto = ALEMBIC_INI.read_text(encoding="utf-8")
    sin_comentarios = "\n".join(
        l for l in texto.splitlines() if not l.lstrip().startswith(("#", ";"))
    )
    assert not re.search(r"postgresql(\+\w+)?://", texto)
    assert "password" not in texto.lower()
    # la plantilla trae `sqlalchemy.url = driver://...`: no puede quedar con valor
    for linea in sin_comentarios.splitlines():
        if linea.strip().startswith("sqlalchemy.url"):
            assert linea.split("=", 1)[1].strip() == "", linea


def test_env_py_existe():
    assert ENV_PY.is_file(), "falta migrations/env.py"


def _alembic(*args, cwd, env):
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(ALEMBIC_INI), *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_sin_contrasena_de_la_base_alembic_no_arranca(tmp_path):
    # cwd sin .env: el entorno es lo único que ve la configuración.
    entorno = {
        **os.environ,
        "PYTHONPATH": str(RAIZ),
        "POSTGRES_USER": "usuario_de_prueba",
        "POSTGRES_DB": "taller_test",
        "POSTGRES_PASSWORD": "",
        "JWT_SECRET_KEY": "x" * 32,
    }
    res = _alembic("current", cwd=tmp_path, env=entorno)
    assert res.returncode != 0
    assert "POSTGRES_PASSWORD" in res.stdout + res.stderr


def test_con_el_entorno_normal_alembic_current_termina_bien():
    entorno = {**os.environ, "POSTGRES_DB": "taller_test"}
    res = _alembic("current", cwd=RAIZ, env=entorno)
    assert res.returncode == 0, res.stderr


FRASE_LECTURA_PREVIA = "Leída antes de aplicarla"
VERSIONES = sorted((RAIZ / "migrations" / "versions").glob("*.py"))


def tiene_comentario_de_lectura_previa(texto: str) -> bool:
    return FRASE_LECTURA_PREVIA in texto


def test_el_verificador_distingue_con_y_sin_comentario():
    assert tiene_comentario_de_lectura_previa(f'"""x\n\n{FRASE_LECTURA_PREVIA} por Ana.\n"""')
    assert not tiene_comentario_de_lectura_previa('"""x\n\nSin comentario.\n"""')


@pytest.mark.parametrize("version", VERSIONES, ids=lambda p: p.name)
def test_cada_migracion_lleva_el_comentario_de_lectura_previa(version):
    # No puede verificar que se haya leído: eso lo garantiza el checkpoint.
    assert tiene_comentario_de_lectura_previa(version.read_text(encoding="utf-8"))


# --- Primera migración sola (4.11) --------------------------------------------

from sqlalchemy import text  # noqa: E402

from tests.conftest import destino_de_migracion  # noqa: E402


def _alembic_ok(*args):
    res = _alembic(*args, cwd=RAIZ, env={**os.environ, "POSTGRES_DB": "taller_test"})
    assert res.returncode == 0, res.stderr
    return res


async def _consultar(motor, sql):
    # Conexión abierta sólo el tiempo de la consulta: un DROP TABLE de Alembic
    # esperaría el lock de una transacción abierta.
    async with motor.connect() as conexion:
        return (await conexion.execute(text(sql))).scalars().all()


async def test_la_primera_migracion_sola_crea_las_13_tablas_y_los_3_indices_parciales(motor):
    try:
        _alembic_ok("downgrade", "base")
        assert await _consultar(
            motor,
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name <> 'alembic_version'",
        ) == []

        _alembic_ok("upgrade", "0001")
        tablas = await _consultar(
            motor,
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name <> 'alembic_version'",
        )
        assert len(tablas) == 13
        parciales = await _consultar(
            motor,
            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' "
            "AND indexdef LIKE '%WHERE%' ORDER BY indexname",
        )
        assert parciales == [
            "uq_asignacion_rol_abierta",
            "uq_repuesto_codigo_vigente",
            "uq_vehiculo_patente_vigente",
        ]
        assert await _consultar(motor, "SELECT version_num FROM alembic_version") == ["0001"]
    finally:
        # Deja la base como la encontró (la fixture base_migrada es de sesión).
        _alembic_ok("upgrade", destino_de_migracion())


# --- Regla 17: ningún SQL armado por interpolación en las migraciones ----------
import ast  # noqa: E402


def sql_armado_por_interpolacion(codigo: str) -> list[str]:
    """Líneas con f-strings con sustituciones, `.format(`, `%` o `+` sobre un texto."""
    hallazgos = []
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, ast.JoinedStr) and any(
            isinstance(v, ast.FormattedValue) for v in nodo.values
        ):
            hallazgos.append(f"línea {nodo.lineno}: f-string")
        elif (
            isinstance(nodo, ast.Call)
            and isinstance(nodo.func, ast.Attribute)
            and nodo.func.attr == "format"
            and isinstance(nodo.func.value, ast.Constant)
            and isinstance(nodo.func.value.value, str)
        ):
            hallazgos.append(f"línea {nodo.lineno}: .format")
        elif isinstance(nodo, ast.BinOp) and isinstance(nodo.op, (ast.Mod, ast.Add)):
            if any(
                isinstance(lado, ast.Constant) and isinstance(lado.value, str)
                for lado in (nodo.left, nodo.right)
            ):
                hallazgos.append(f"línea {nodo.lineno}: operador sobre texto")
    return hallazgos


@pytest.mark.parametrize(
    "codigo",
    [
        'op.execute(f"DROP TRIGGER t ON {tabla}")',
        'op.execute("DROP TRIGGER t ON {}".format(tabla))',
        'op.execute("DROP TRIGGER t ON %s" % tabla)',
        'op.execute("DROP TRIGGER t ON " + tabla)',
    ],
)
def test_el_detector_encuentra_sql_armado_por_interpolacion(codigo):
    assert sql_armado_por_interpolacion(codigo)


def test_el_detector_no_da_falsos_positivos_con_sql_literal():
    literal = 'op.execute("""RAISE EXCEPTION \'La tabla % es\', TG_TABLE_NAME""")\nf"sin sustitucion"'
    assert sql_armado_por_interpolacion(literal) == []


@pytest.mark.parametrize("version", VERSIONES, ids=lambda p: p.name)
def test_ninguna_migracion_arma_sql_por_interpolacion(version):
    assert sql_armado_por_interpolacion(version.read_text(encoding="utf-8")) == []


# --- Historial, ciclo, alembic check y atajo de los modelos (5.5 a 5.8) ----------------
from alembic.config import Config  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402


def test_el_historial_son_dos_revisiones_lineales_con_una_sola_cabeza():
    guion = ScriptDirectory.from_config(Config(str(ALEMBIC_INI)))
    revisiones = {r.revision: r for r in guion.walk_revisions()}
    assert sorted(revisiones) == ["0001", "0002"]
    assert revisiones["0001"].down_revision is None
    assert revisiones["0002"].down_revision == "0001"
    assert guion.get_heads() == ["0002"]


SQL_FOTO = {
    "columnas": (
        "SELECT table_name || '.' || column_name || ' ' || data_type || ' ' || is_nullable "
        "|| ' ' || coalesce(column_default, '') || ' ' || coalesce(numeric_precision::text, '') "
        "|| ',' || coalesce(numeric_scale::text, '') FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name <> 'alembic_version' ORDER BY 1"
    ),
    "restricciones": (
        "SELECT conrelid::regclass::text || ' ' || conname || ' ' || pg_get_constraintdef(oid) "
        "FROM pg_constraint WHERE connamespace = 'public'::regnamespace ORDER BY 1"
    ),
    "indices": "SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1",
    "disparadores": (
        "SELECT pg_get_triggerdef(oid) FROM pg_trigger WHERE NOT tgisinternal ORDER BY 1"
    ),
    "funciones": (
        "SELECT proname FROM pg_proc WHERE pronamespace = 'public'::regnamespace ORDER BY 1"
    ),
    "tablas": (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'public' AND table_name <> 'alembic_version' ORDER BY 1"
    ),
    "versiones": "SELECT version_num FROM alembic_version ORDER BY 1",
}


async def _foto(motor):
    return {nombre: await _consultar(motor, sql) for nombre, sql in SQL_FOTO.items()}


async def test_el_ciclo_up_down_up_deja_el_mismo_esquema(motor):
    _alembic_ok("upgrade", "head")
    antes = await _foto(motor)
    assert len(antes["tablas"]) == 13 and len(antes["disparadores"]) == 3
    assert antes["funciones"] == ["rechazar_cambio_solo_agregado"]
    assert antes["versiones"] == ["0002"]
    try:
        _alembic_ok("downgrade", "base")
        vacia = await _foto(motor)
        assert vacia["tablas"] == [] and vacia["disparadores"] == []
        assert vacia["funciones"] == [] and vacia["versiones"] == []
        _alembic_ok("upgrade", "head")
        assert await _foto(motor) == antes
    finally:
        _alembic_ok("upgrade", "head")


def test_alembic_check_no_detecta_diferencias_entre_modelos_y_migraciones():
    _alembic_ok("upgrade", "head")
    res = _alembic("check", cwd=RAIZ, env={**os.environ, "POSTGRES_DB": "taller_test"})
    assert res.returncode == 0, res.stdout + res.stderr


def test_nadie_crea_el_esquema_con_el_atajo_de_los_modelos():
    # Una LLAMADA (con paréntesis); los comentarios que lo nombran no cuentan.
    atajo = re.compile(r"create" + r"_all\s*\(")
    carpetas = [RAIZ / "app", RAIZ / "migrations", RAIZ / "tests"]
    archivos = [RAIZ / "main.py", RAIZ / "seed.py"]
    for carpeta in carpetas:
        archivos += [p for p in carpeta.rglob("*.py") if ".venv" not in p.parts]
    encontrados = [
        p.relative_to(RAIZ).as_posix()
        for p in archivos
        if p.exists() and atajo.search(p.read_text(encoding="utf-8"))
    ]
    assert encontrados == []


async def test_downgrade_con_datos_cargados_termina_sin_error(motor, vaciar_al_terminar):
    entorno = {**os.environ, "POSTGRES_DB": "taller_test", "BCRYPT_COST": "4"}
    _alembic_ok("upgrade", "head")
    sembrado = subprocess.run(
        [sys.executable, str(RAIZ / "seed.py")], cwd=RAIZ, env=entorno, capture_output=True, text=True, timeout=120
    )
    assert sembrado.returncode == 0, sembrado.stderr[-500:]
    assert await _consultar(motor, "SELECT count(*) FROM historial_estado_orden") == [3]
    try:
        _alembic_ok("downgrade", "base")  # con filas en las tablas de sólo agregado
        assert await _consultar(
            motor,
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name <> 'alembic_version'",
        ) == []
    finally:
        _alembic_ok("upgrade", "head")
    assert await _consultar(motor, "SELECT count(*) FROM usuario") == [0]
