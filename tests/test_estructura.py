"""Estructura del proyecto: módulos importables y test/ fuera de la recolección."""
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
MODULOS = ["health", "usuarios", "clientes", "repuestos", "ordenes"]


@pytest.mark.parametrize("nombre", ["app.core"] + [f"app.modules.{m}" for m in MODULOS])
def test_los_paquetes_se_importan(nombre):
    assert importlib.import_module(nombre) is not None


def test_el_modulo_health_solo_tiene_init_y_router():
    archivos = {p.name for p in (RAIZ / "app/modules/health").iterdir() if p.is_file()}
    assert archivos == {"__init__.py", "router.py"}


def test_pytest_no_recolecta_nada_de_test():
    salida = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=RAIZ, capture_output=True, text=True, timeout=120,
    ).stdout
    nodos = [l for l in salida.splitlines() if "::" in l]
    assert nodos, "no se recolectó ningún test"
    assert not [n for n in nodos if n.startswith("test/")]
