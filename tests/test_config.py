"""Tests de app.core.config: Settings sin secretos por defecto (CH-01)."""
import pytest
from pydantic import ValidationError
from sqlalchemy.engine import make_url

from app.core.config import Settings, get_settings

# Las pruebas de secretos usan valores sintéticos; no son credenciales reales.
PASSWORD_PRUEBA = "pwd-de-prueba"
CLAVE_PRUEBA = "k" * 32

ENTORNO_BASE = {
    "POSTGRES_USER": "taller",
    "POSTGRES_PASSWORD": PASSWORD_PRUEBA,
    "POSTGRES_DB": "taller",
    "JWT_SECRET_KEY": CLAVE_PRUEBA,
}

VARIABLES_CONOCIDAS = (
    "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT",
    "POSTGRES_DB", "JWT_SECRET_KEY", "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_SECONDS", "COOKIE_SECURE", "BCRYPT_COST",
    "BCRYPT_MAX_CONCURRENT", "DB_POOL_SIZE", "SQL_ECHO",
)


@pytest.fixture(autouse=True)
def _limpiar_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def construir(monkeypatch):
    """Devuelve una función que arma Settings sobre un entorno controlado.

    Parte de un entorno sin ninguna variable conocida, aplica `base` más
    `extra`, y no lee el .env real (`_env_file=None`).
    """
    for nombre in VARIABLES_CONOCIDAS:
        monkeypatch.delenv(nombre, raising=False)

    def _construir(extra=None, quitar=(), base=ENTORNO_BASE):
        entorno = {**base, **(extra or {})}
        for nombre in quitar:
            entorno.pop(nombre, None)
        for nombre, valor in entorno.items():
            monkeypatch.setenv(nombre, valor)
        return Settings(_env_file=None)

    return _construir


def test_falla_sin_postgres_password(construir):
    with pytest.raises(ValidationError) as exc:
        construir(quitar=["POSTGRES_PASSWORD"])
    assert "POSTGRES_PASSWORD" in str(exc.value)


def test_falla_sin_jwt_secret_key(construir):
    with pytest.raises(ValidationError) as exc:
        construir(quitar=["JWT_SECRET_KEY"])
    assert "JWT_SECRET_KEY" in str(exc.value)


@pytest.mark.parametrize("variable", ["POSTGRES_PASSWORD", "JWT_SECRET_KEY"])
def test_secreto_vacio_falla_igual_que_si_faltara(construir, variable):
    with pytest.raises(ValidationError) as exc:
        construir(extra={variable: ""})
    assert variable in str(exc.value)


def test_clave_de_firma_de_31_caracteres_falla(construir):
    with pytest.raises(ValidationError) as exc:
        construir(extra={"JWT_SECRET_KEY": "k" * 31})
    assert "JWT_SECRET_KEY" in str(exc.value)


def test_clave_de_firma_de_32_caracteres_pasa(construir):
    settings = construir(extra={"JWT_SECRET_KEY": "k" * 32})
    assert settings.JWT_SECRET_KEY.get_secret_value() == "k" * 32


def test_repr_y_str_no_exponen_los_secretos(construir):
    settings = construir(
        extra={"POSTGRES_PASSWORD": "pwd-unica-123", "JWT_SECRET_KEY": "z" * 40}
    )
    for texto in (repr(settings), str(settings)):
        assert "pwd-unica-123" not in texto
        assert "z" * 40 not in texto


def test_database_url_con_los_cinco_valores(construir):
    settings = construir(
        extra={"POSTGRES_HOST": "localhost", "POSTGRES_PORT": "5432"}
    )
    assert settings.DATABASE_URL == (
        f"postgresql+asyncpg://taller:{PASSWORD_PRUEBA}@localhost:5432/taller"
    )


def test_database_url_con_otro_host_puerto_y_base(construir):
    settings = construir(
        extra={
            "POSTGRES_HOST": "db.local",
            "POSTGRES_PORT": "5433",
            "POSTGRES_DB": "taller_test",
        }
    )
    assert settings.DATABASE_URL.endswith("@db.local:5433/taller_test")
    assert settings.DATABASE_URL.startswith("postgresql+asyncpg://")


def test_database_url_escapa_caracteres_especiales_de_la_password(construir):
    original = "p@ss:wo/rd"
    settings = construir(
        extra={
            "POSTGRES_PASSWORD": original,
            "POSTGRES_HOST": "db.local",
            "POSTGRES_PORT": "5433",
        }
    )
    url = make_url(settings.DATABASE_URL)
    assert url.password == original
    assert url.host == "db.local"
    assert url.port == 5433
    assert url.drivername == "postgresql+asyncpg"


def test_database_url_no_puede_fijarse_desde_el_entorno(construir):
    settings = construir(extra={"DATABASE_URL": "postgresql+asyncpg://x:y@z/w"})
    assert "z/w" not in settings.DATABASE_URL


def test_database_url_no_aparece_en_repr(construir):
    assert "DATABASE_URL" not in repr(construir())


def test_valores_por_defecto_de_parametros_operativos(construir):
    settings = construir()
    assert settings.ACCESS_TOKEN_EXPIRE_SECONDS == 1800
    assert settings.COOKIE_SECURE is False
    assert settings.BCRYPT_COST == 12
    assert settings.BCRYPT_MAX_CONCURRENT == 4
    assert settings.DB_POOL_SIZE == 5
    assert settings.SQL_ECHO is False
    assert settings.JWT_ALGORITHM == "HS256"
    assert settings.POSTGRES_HOST == "localhost"
    assert settings.POSTGRES_PORT == 5432


def test_parametros_operativos_tomados_del_entorno_con_su_tipo(construir):
    settings = construir(
        extra={
            "SQL_ECHO": "true",
            "COOKIE_SECURE": "true",
            "BCRYPT_COST": "4",
            "DB_POOL_SIZE": "2",
        }
    )
    assert settings.SQL_ECHO is True
    assert settings.COOKIE_SECURE is True
    assert settings.BCRYPT_COST == 4 and isinstance(settings.BCRYPT_COST, int)
    assert settings.DB_POOL_SIZE == 2 and isinstance(settings.DB_POOL_SIZE, int)


@pytest.mark.parametrize(
    "variable, valor",
    [
        ("BCRYPT_COST", "3"),
        ("BCRYPT_COST", "32"),
        ("DB_POOL_SIZE", "0"),
        ("BCRYPT_MAX_CONCURRENT", "0"),
        ("ACCESS_TOKEN_EXPIRE_SECONDS", "0"),
    ],
)
def test_valor_fuera_de_rango_falla(construir, variable, valor):
    with pytest.raises(ValidationError) as exc:
        construir(extra={variable: valor})
    assert variable in str(exc.value)


@pytest.mark.parametrize("variable", ["POSTGRES_DB", "POSTGRES_USER"])
def test_datos_de_conexion_obligatorios(construir, variable):
    with pytest.raises(ValidationError) as exc:
        construir(quitar=[variable])
    assert variable in str(exc.value)


@pytest.fixture
def archivo_env(tmp_path, construir):
    """Un .env temporal completo con POSTGRES_DB=taller (sin tocar el real)."""
    construir()  # deja el entorno del proceso sin ninguna variable conocida
    contenido = "\n".join(f"{k}={v}" for k, v in ENTORNO_BASE.items())
    ruta = tmp_path / ".env"
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_el_entorno_pisa_al_env(monkeypatch, archivo_env):
    # `archivo_env` -> `construir` ya fijó el entorno base; lo reemplazamos.
    monkeypatch.setenv("POSTGRES_DB", "taller_test")
    settings = Settings(_env_file=archivo_env)
    assert settings.POSTGRES_DB == "taller_test"


def test_sin_variables_de_entorno_se_toma_el_env(monkeypatch, archivo_env):
    for nombre in VARIABLES_CONOCIDAS:
        monkeypatch.delenv(nombre, raising=False)
    settings = Settings(_env_file=archivo_env)
    assert settings.POSTGRES_DB == "taller"
    assert settings.POSTGRES_USER == "taller"
    assert settings.JWT_SECRET_KEY.get_secret_value() == CLAVE_PRUEBA
