"""Dos grupos de rutas en main.py; el protegido nace vacío y sin dependencias."""
from fastapi import APIRouter

import main


def test_existen_los_dos_grupos_y_son_distintos():
    assert isinstance(main.rutas_abiertas, APIRouter)
    assert isinstance(main.rutas_protegidas, APIRouter)
    assert main.rutas_abiertas is not main.rutas_protegidas


def test_el_grupo_protegido_no_tiene_rutas_ni_dependencias():
    # CH-05 le agrega, una sola vez, el control del cambio obligatorio.
    assert main.rutas_protegidas.routes == []
    assert main.rutas_protegidas.dependencies == []


def test_rutas_propias_de_la_app():
    # Hasta CH-04 las únicas rutas propias son las dos de salud (grupo abierto).
    # openapi() lista sólo las rutas propias (sin /docs, /redoc ni /openapi.json)
    # y resuelve los routers incluidos en cualquier versión de FastAPI.
    rutas = set(main.app.openapi()["paths"])
    assert {"/health/live", "/health/ready"}.issubset(rutas)
