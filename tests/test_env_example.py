"""Contrato de env.example: todas las variables de Settings, sin secretos."""
import secrets
from pathlib import Path

import pytest
from dotenv import dotenv_values
from pydantic import ValidationError

from app.core.config import Settings

RAIZ = Path(__file__).resolve().parent.parent
ENV_EXAMPLE = RAIZ / "env.example"
SECRETOS = ("POSTGRES_PASSWORD", "JWT_SECRET_KEY")


def _leer():
    return dotenv_values(ENV_EXAMPLE)


def test_claves_de_env_example_son_los_campos_de_settings():
    campos = set(Settings.model_fields)  # computed_field DATABASE_URL no está
    assert set(_leer()) == campos
    assert len(campos) == 13


def test_los_secretos_figuran_con_valor_vacio():
    valores = _leer()
    for secreto in SECRETOS:
        assert valores[secreto] in ("", None)


def _valores_no_secretos():
    return {k: v for k, v in _leer().items() if k not in SECRETOS}


def test_los_valores_no_secretos_son_validos_para_settings(monkeypatch):
    for nombre in _leer():
        monkeypatch.delenv(nombre, raising=False)
    entorno = {
        **_valores_no_secretos(),
        "POSTGRES_PASSWORD": secrets.token_urlsafe(8),
        "JWT_SECRET_KEY": secrets.token_urlsafe(64),
    }
    for k, v in entorno.items():
        monkeypatch.setenv(k, v)
    settings = Settings(_env_file=None)
    assert settings.POSTGRES_DB == "taller"
    assert settings.SQL_ECHO is True


def test_con_los_secretos_vacios_de_env_example_la_construccion_falla(monkeypatch):
    for nombre in _leer():
        monkeypatch.delenv(nombre, raising=False)
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=ENV_EXAMPLE)
    mensaje = str(exc.value)
    assert "POSTGRES_PASSWORD" in mensaje
    assert "JWT_SECRET_KEY" in mensaje
