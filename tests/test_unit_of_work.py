"""Unit of Work del núcleo (CH-03): confirma, revierte, no cierra la sesión y es el
único que confirma. Contra PostgreSQL real con los modelos de `nucleo_prueba`."""
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.database import get_session
from app.core.repository import BaseRepository
from app.core.unit_of_work import UnitOfWork
from tests.nucleo_modelos import CosaPrueba, DetallePrueba


class UoWPrueba(UnitOfWork):
    """UoW concreto de prueba: compone dos repositorios con la MISMA sesión."""

    def __init__(self, session):
        super().__init__(session)
        self.cosas = BaseRepository(session, CosaPrueba)
        self.detalles = BaseRepository(session, DetallePrueba)


async def _existen(sesiones, modelo) -> int:
    async with sesiones() as otra:
        return await BaseRepository(otra, modelo).count()


async def test_varias_escrituras_se_confirman_juntas(sesion, sesiones):
    """Varias escrituras confirmadas juntas."""
    uow = UoWPrueba(sesion)
    async with uow:
        cosa = await uow.cosas.add(CosaPrueba(nombre="a"))
        await uow.detalles.add(DetallePrueba(cosa_id=cosa.id, texto="t", codigo="k1"))
    assert (await _existen(sesiones, CosaPrueba), await _existen(sesiones, DetallePrueba)) == (1, 1)


async def test_excepcion_despues_de_varias_escrituras_revierte_todo(sesion, sesiones):
    """Excepción después de varias escrituras: sale la misma excepción y no queda nada."""
    error = ValueError("x")
    uow = UoWPrueba(sesion)
    with pytest.raises(ValueError) as info:
        async with uow:
            cosa = await uow.cosas.add(CosaPrueba(nombre="a"))
            await uow.detalles.add(DetallePrueba(cosa_id=cosa.id, texto="t", codigo="k1"))
            raise error
    assert info.value is error
    assert (await _existen(sesiones, CosaPrueba), await _existen(sesiones, DetallePrueba)) == (0, 0)


async def test_error_de_integridad_dentro_del_bloque(sesion, sesiones):
    """Error de integridad dentro del bloque: la escritura anterior tampoco existe."""
    uow = UoWPrueba(sesion)
    with pytest.raises(IntegrityError):
        async with uow:
            await uow.cosas.add(CosaPrueba(nombre="a"))
            await uow.cosas.add(CosaPrueba(nombre="a"))
    assert await _existen(sesiones, CosaPrueba) == 0


async def test_falla_al_confirmar_deja_la_sesion_revertida_y_utilizable(sesion, sesiones):
    """Falla al confirmar: UNIQUE diferido, el flush pasa y el error sale al confirmar."""
    uow = UoWPrueba(sesion)
    with pytest.raises(IntegrityError):
        async with uow:
            cosa = await uow.cosas.add(CosaPrueba(nombre="a"))
            await uow.detalles.add(DetallePrueba(cosa_id=cosa.id, texto="1", codigo="repetido"))
            await uow.detalles.add(DetallePrueba(cosa_id=cosa.id, texto="2", codigo="repetido"))
    assert not sesion.in_transaction()
    assert (await sesion.exec(text("SELECT 1"))).scalar_one() == 1
    assert (await _existen(sesiones, CosaPrueba), await _existen(sesiones, DetallePrueba)) == (0, 0)


async def test_sesion_utilizable_despues_de_revertir(sesion):
    """Sesión utilizable después de revertir."""
    with pytest.raises(RuntimeError):
        async with UoWPrueba(sesion) as uow:
            await uow.cosas.add(CosaPrueba(nombre="a"))
            raise RuntimeError("falla")
    assert (await sesion.exec(text("SELECT 1"))).scalar_one() == 1


async def test_sesion_utilizable_despues_de_confirmar_y_segundo_bloque(sesion, sesiones, monkeypatch):
    """Sesión utilizable después de confirmar; además el UoW nunca llama a close."""
    cierres = []
    original = sesion.close

    async def espia():
        cierres.append(1)
        await original()

    monkeypatch.setattr(sesion, "close", espia)
    uow = UoWPrueba(sesion)
    async with uow:
        await uow.cosas.add(CosaPrueba(nombre="a"))
    async with uow:
        await uow.cosas.add(CosaPrueba(nombre="b"))
    with pytest.raises(RuntimeError):
        async with uow:
            raise RuntimeError("x")
    assert cierres == []
    assert await _existen(sesiones, CosaPrueba) == 2


async def test_entidades_legibles_despues_de_confirmar(sesion, sentencias):
    """Entidades legibles después de confirmar (expire_on_commit=False de la fábrica)."""
    uow = UoWPrueba(sesion)
    async with uow:
        cosa = await uow.cosas.add(CosaPrueba(nombre="a", etiqueta="e"))
    antes = len(sentencias)
    assert cosa.id is not None
    assert (cosa.nombre, cosa.etiqueta) == ("a", "e")
    assert len(sentencias) == antes


async def test_los_repositorios_comparten_la_sesion_del_uow(sesion, sesiones):
    """Repositorios compartiendo la sesión: se confirman o se revierten juntos."""
    uow = UoWPrueba(sesion)
    assert uow.cosas.session is uow.detalles.session is sesion
    with pytest.raises(RuntimeError):
        async with uow:
            cosa = await uow.cosas.add(CosaPrueba(nombre="a"))
            await uow.detalles.add(DetallePrueba(cosa_id=cosa.id, texto="t", codigo="k"))
            raise RuntimeError("x")
    assert (await _existen(sesiones, CosaPrueba), await _existen(sesiones, DetallePrueba)) == (0, 0)


def test_nadie_mas_confirma():
    """Nadie más confirma: la única llamada a commit en app/ y main.py está en el UoW base."""
    raiz = Path(__file__).resolve().parent.parent
    archivos = [raiz / "main.py", *(raiz / "app").rglob("*.py")]
    # Excepción reservada para CH-04: la escritura de intento_acceso en sesión y
    # transacción propias (Ejercicio 7). Hoy no existe; se agrega aquí, comentada, cuando exista.
    excepciones_permitidas: set[str] = set()
    con_commit = {
        a.relative_to(raiz).as_posix() for a in archivos if ".commit(" in a.read_text(encoding="utf-8")
    }
    assert con_commit - excepciones_permitidas == {"app/core/unit_of_work.py"}


# --- Petición completa: el router construye, el servicio abre --------------------
class ErrorDeDominio(Exception):
    pass


async def crear_cosa(uow: UoWPrueba, nombre: str, fallar: bool) -> None:
    """Servicio de prueba: recibe el UoW sin abrir y lo abre con `async with`."""
    async with uow:
        await uow.cosas.add(CosaPrueba(nombre=nombre))
        if fallar:
            raise ErrorDeDominio(nombre)


class FabricaEspia:
    """Envuelve la fábrica real y anota cuántas sesiones se cerraron."""

    def __init__(self, fabrica):
        self._fabrica = fabrica
        self.cerradas = 0

    def __call__(self):
        espia = self

        @asynccontextmanager
        async def _sesion():
            async with espia._fabrica() as s:
                try:
                    yield s
                finally:
                    espia.cerradas += 1

        return _sesion()


def _mini_app(fabrica):
    @asynccontextmanager
    async def lifespan(app):
        app.state.session_factory = fabrica
        yield

    app = FastAPI(lifespan=lifespan)

    def get_uow_prueba(session=Depends(get_session)) -> UoWPrueba:
        return UoWPrueba(session)  # el router lo construye

    @app.post("/cosas/{nombre}", status_code=201)
    async def crear(nombre: str, fallar: bool = False, uow: UoWPrueba = Depends(get_uow_prueba)):
        try:
            await crear_cosa(uow, nombre, fallar)
        except ErrorDeDominio:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=409, content={"detail": "conflicto"})
        return {"nombre": nombre}

    return app


async def _post(app, ruta):
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            return await c.post(ruta)


async def test_peticion_que_escribe(esquema_nucleo, sesiones):
    """Petición que escribe: queda confirmada y la sesión se cerró al terminar."""
    fabrica = FabricaEspia(sesiones)
    r = await _post(_mini_app(fabrica), "/cosas/a")
    assert r.status_code == 201
    assert await _existen(sesiones, CosaPrueba) == 1
    assert fabrica.cerradas == 1


async def test_peticion_que_falla(esquema_nucleo, sesiones):
    """Petición que falla: el código traducido por la ruta y la fila no existe."""
    fabrica = FabricaEspia(sesiones)
    r = await _post(_mini_app(fabrica), "/cosas/a?fallar=true")
    assert r.status_code == 409
    assert await _existen(sesiones, CosaPrueba) == 0
    assert fabrica.cerradas == 1
