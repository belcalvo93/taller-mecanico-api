"""Regla 7: importar los módulos no lee la config ni crea recursos."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
SECRETOS = ("POSTGRES_PASSWORD", "JWT_SECRET_KEY")


def _importar(codigo, cwd):
    """Corre `codigo` en un subproceso sin .env (cwd temporal) ni secretos."""
    entorno = {k: v for k, v in os.environ.items() if k not in SECRETOS}
    entorno["PYTHONPATH"] = str(RAIZ)
    return subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=cwd, env=entorno, capture_output=True, text=True, timeout=60,
    )


def test_importar_main_no_crea_recursos_ni_lee_config(tmp_path):
    resultado = _importar(
        "import main\n"
        "for nombre in ('engine', 'session_factory', 'hash_ficticio'):\n"
        "    assert not hasattr(main.app.state, nombre), nombre\n",
        tmp_path,
    )
    assert resultado.returncode == 0, resultado.stderr


@pytest.mark.parametrize(
    "modulos", [
        ("app.core.config",),
        ("app.core.database",),
        ("app.modules.health.router",),
        ("app.core.config", "app.core.database", "app.modules.health.router"),
    ]
)
def test_importar_config_y_database_no_requiere_secretos(tmp_path, modulos):
    resultado = _importar("; ".join(f"import {m}" for m in modulos), tmp_path)
    assert resultado.returncode == 0, resultado.stderr
