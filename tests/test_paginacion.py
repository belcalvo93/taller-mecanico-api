"""Paginación del núcleo (CH-03): cálculo de páginas, envoltorio, parámetros y 422."""
import pytest

from app.core.paginacion import PaginaInexistente, calcular_paginas


@pytest.mark.parametrize(
    "total, size, esperado",
    [(0, 20, 1), (0, 1, 1), (1, 1, 1), (1, 20, 1), (40, 20, 2), (41, 20, 3)],
)
def test_calcular_paginas(total, size, esperado):
    """Cálculo de la cantidad de páginas: cero resultados, un resultado, varios."""
    assert calcular_paginas(total, size) == esperado


@pytest.mark.parametrize(
    "page, pages, mensaje",
    [(3, 2, "La página 3 no existe: hay 2"), (2, 1, "La página 2 no existe: hay 1")],
)
def test_pagina_inexistente_tiene_mensaje_propio(page, pages, mensaje):
    exc = PaginaInexistente(page, pages)
    assert exc.mensaje == mensaje
    assert str(exc) == mensaje
    assert (exc.page, exc.pages) == (page, pages)


def test_forma_del_envoltorio():
    """Forma del envoltorio: exactamente items, total, page, size y pages."""
    from app.core.paginacion import Pagina

    pagina = Pagina[int](items=[1, 2], total=4, page=1, size=2, pages=2)
    assert pagina.model_dump() == {"items": [1, 2], "total": 4, "page": 1, "size": 2, "pages": 2}


def test_envoltorio_vacio_conserva_pages_recibido():
    from app.core.paginacion import Pagina

    pagina = Pagina[str](items=[], total=0, page=1, size=20, pages=1)
    assert pagina.model_dump() == {"items": [], "total": 0, "page": 1, "size": 20, "pages": 1}


# --- Mini app de prueba: parámetros y manejador --------------------------------
from fastapi import Depends, FastAPI  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.paginacion import (  # noqa: E402
    ParametrosPagina,
    parametros_pagina,
    responder_pagina_inexistente,
)


def _mini_app(registrar_manejador: bool = True):
    app = FastAPI()
    llamadas = {"n": 0}
    if registrar_manejador:
        app.add_exception_handler(PaginaInexistente, responder_pagina_inexistente)

    @app.get("/listado")
    async def listado(p: ParametrosPagina = Depends(parametros_pagina)):
        llamadas["n"] += 1
        return {"page": p.page, "size": p.size}

    @app.get("/fuera")
    async def fuera():
        raise PaginaInexistente(3, 2)

    return app, llamadas


async def _pedir(app, ruta):
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://t"
    ) as c:
        return await c.get(ruta)


async def test_parametros_por_defecto():
    """Valores por defecto: página 1, tamaño 20."""
    app, _ = _mini_app()
    r = await _pedir(app, "/listado")
    assert r.status_code == 200 and r.json() == {"page": 1, "size": 20}


@pytest.mark.parametrize("size", [1, 100])
async def test_limites_de_size_aceptados(size):
    app, _ = _mini_app()
    r = await _pedir(app, f"/listado?size={size}&page=2")
    assert r.status_code == 200 and r.json() == {"page": 2, "size": size}


@pytest.mark.parametrize("consulta", ["size=0", "size=101", "size=500", "page=0", "page=-1", "page=abc", "size=x"])
async def test_parametros_invalidos_dan_422_sin_ejecutar_el_listado(consulta):
    """Tamaño fuera de rango / página menor que uno o no entera."""
    app, llamadas = _mini_app()
    r = await _pedir(app, f"/listado?{consulta}")
    assert r.status_code == 422
    assert llamadas["n"] == 0


async def test_pagina_inexistente_responde_422_con_mensaje_y_sin_traza():
    app, _ = _mini_app()
    r = await _pedir(app, "/fuera")
    assert r.status_code == 422
    assert r.json() == {"detail": "La página 3 no existe: hay 2"}
    assert "Traceback" not in r.text


async def test_sin_registrar_el_manejador_la_pagina_inexistente_es_500():
    """Documenta por qué main.py registra el manejador (RN-18)."""
    app, _ = _mini_app(registrar_manejador=False)
    r = await _pedir(app, "/fuera")
    assert r.status_code == 500


def test_la_app_real_registra_el_manejador_de_pagina_inexistente():
    """RN-18: ningún listado de la app real termina en 500 por una página inexistente."""
    from main import app

    assert app.exception_handlers[PaginaInexistente] is responder_pagina_inexistente
