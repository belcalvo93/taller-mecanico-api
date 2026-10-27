"""Dos grupos de rutas en main.py; el protegido nace sin dependencias.

Desde CH-06 el grupo protegido tiene rutas: cada change de la ola 2 agrega las
suyas y verifica en su propio archivo de tests que están en el grupo correcto
(design D10 de clientes-y-vehiculos). Acá sólo se fija lo común.
"""
from fastapi import APIRouter

import main


def test_existen_los_dos_grupos_y_son_distintos():
    assert isinstance(main.rutas_abiertas, APIRouter)
    assert isinstance(main.rutas_protegidas, APIRouter)
    assert main.rutas_abiertas is not main.rutas_protegidas


def test_el_grupo_protegido_no_tiene_dependencias():
    # CH-05 le agrega, una sola vez, el control del cambio obligatorio.
    assert main.rutas_protegidas.dependencies == []


def test_las_rutas_de_salud_siguen_en_la_app():
    # openapi() lista sólo las rutas propias (sin /docs, /redoc ni /openapi.json)
    # y resuelve los routers incluidos en cualquier versión de FastAPI.
    rutas = set(main.app.openapi()["paths"])
    assert {"/health/live", "/health/ready"}.issubset(rutas)
