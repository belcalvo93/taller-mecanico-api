"""CH-06: repositorios y Unit of Work del módulo clientes, contra taller_test sembrada.

Datos del seed: cliente 1 = Laura (usuario 6) con vehículos 1 AB123CD y 2 AC456EF;
cliente 2 = Jorge (sin usuario) con el vehículo 3 AD789GH. Orden 1 PENDIENTE del
vehículo 1 y orden 2 EN_REPARACION del vehículo 3; el vehículo 2 no tiene órdenes.
"""
from contextlib import contextmanager

import pytest
from sqlalchemy import event
from sqlalchemy.exc import InvalidRequestError

from app.core.database import crear_fabrica_sesiones
from app.core.repository import BaseRepository, SoftDeleteRepository
from app.modules.clientes.models import Cliente, Vehiculo
from app.modules.clientes.repository import ClienteRepository, VehiculoRepository
from app.modules.clientes.unit_of_work import ClientesUnitOfWork
from tests.helpers import insertar


@pytest.fixture
async def sesion(sembrada):
    async with crear_fabrica_sesiones(sembrada)() as s:
        yield s
        await s.rollback()


@contextmanager
def contar_consultas(motor):
    sentencias: list[str] = []

    def _anotar(conn, cursor, statement, *args):
        sentencias.append(statement)

    event.listen(motor.sync_engine, "before_cursor_execute", _anotar)
    try:
        yield sentencias
    finally:
        event.remove(motor.sync_engine, "before_cursor_execute", _anotar)


# --- ClienteRepository (T1, DD-13) ---------------------------------------------

async def test_cliente_repository_firma_acordada(sesion):
    repo = ClienteRepository(sesion)
    assert isinstance(repo, BaseRepository) and repo.modelo is Cliente
    nuevo = await repo.add(Cliente(nombre="Ana Nueva", documento="40999888", telefono="261 555"))
    assert (await repo.get_by_id(nuevo.id)).documento == "40999888"


async def test_get_con_vehiculos_vigentes_precarga_los_de_laura(sesion):
    cliente = await ClienteRepository(sesion).get_con_vehiculos_vigentes(1)
    assert cliente.nombre == "Laura Cliente"
    assert sorted(v.patente for v in cliente.vehiculos) == ["AB123CD", "AC456EF"]


async def test_get_con_vehiculos_vigentes_excluye_los_dados_de_baja(sesion):
    vehiculos = VehiculoRepository(sesion)
    await vehiculos.soft_delete(await vehiculos.get_by_id(2))
    cliente = await ClienteRepository(sesion).get_con_vehiculos_vigentes(1)
    assert [v.patente for v in cliente.vehiculos] == ["AB123CD"]


async def test_get_con_vehiculos_vigentes_recarga_si_el_cliente_ya_estaba_en_la_sesion(sesion):
    repo = ClienteRepository(sesion)
    assert len((await repo.get_con_vehiculos_vigentes(1)).vehiculos) == 2
    vehiculos = VehiculoRepository(sesion)
    await vehiculos.soft_delete(await vehiculos.get_by_id(2))
    cliente = await repo.get_con_vehiculos_vigentes(1)
    assert [v.patente for v in cliente.vehiculos] == ["AB123CD"]


async def test_get_con_vehiculos_vigentes_inexistente(sesion):
    assert await ClienteRepository(sesion).get_con_vehiculos_vigentes(999) is None


@pytest.mark.parametrize("extra", [0, 3])
async def test_cantidad_fija_de_consultas_sin_n_mas_1(sembrada, sesion, extra):
    async with sembrada.begin() as c:
        for n in range(extra):
            await insertar(c, "vehiculo", cliente_id=1, patente=f"ZZ{n}00AA")
    with contar_consultas(sembrada) as sentencias:
        cliente = await ClienteRepository(sesion).get_con_vehiculos_vigentes(1)
        patentes = [v.patente for v in cliente.vehiculos]
    assert len(patentes) == 2 + extra
    assert len(sentencias) == 2  # cliente + vehículos, sin importar cuántos sean


async def test_sin_precarga_la_relacion_no_se_carga_perezosamente(sesion):
    cliente = await ClienteRepository(sesion).get_by_id(2)
    with pytest.raises(InvalidRequestError):
        cliente.vehiculos  # noqa: B018 — lazy="raise" (CH-02): la precarga es obligatoria


# --- VehiculoRepository ----------------------------------------------------------

async def test_vehiculo_repository_es_de_borrado_logico(sesion):
    repo = VehiculoRepository(sesion)
    assert isinstance(repo, SoftDeleteRepository) and repo.modelo is Vehiculo


@pytest.mark.parametrize(
    "vehiculo_id, abiertas",
    [(1, True), (3, True), (2, False)],  # PENDIENTE, EN_REPARACION, sin órdenes
)
async def test_tiene_ordenes_abiertas_segun_el_catalogo(sesion, vehiculo_id, abiertas):
    assert await VehiculoRepository(sesion).tiene_ordenes_abiertas(vehiculo_id) is abiertas


async def test_ordenes_solo_finales_no_cuentan_como_abiertas(sembrada, sesion):
    async with sembrada.begin() as c:
        await insertar(c, "orden_trabajo", vehiculo_id=2, estado="TERMINADA")
        await insertar(c, "orden_trabajo", vehiculo_id=2, estado="CANCELADA")
    assert await VehiculoRepository(sesion).tiene_ordenes_abiertas(2) is False


async def test_listar_vigentes_de_usuario(sesion):
    repo = VehiculoRepository(sesion)
    assert [v.patente for v in await repo.listar_vigentes_de_usuario(6)] == ["AB123CD", "AC456EF"]
    assert await repo.listar_vigentes_de_usuario(1) == []  # admin: sin ficha de cliente
    await repo.soft_delete(await repo.get_by_id(1))
    assert [v.patente for v in await repo.listar_vigentes_de_usuario(6)] == ["AC456EF"]


# --- Unit of Work del módulo -----------------------------------------------------

async def test_uow_compone_los_repositorios_con_la_misma_sesion(sesion):
    uow = ClientesUnitOfWork(sesion)
    assert isinstance(uow.clientes, ClienteRepository)
    assert isinstance(uow.vehiculos, VehiculoRepository)
    assert uow.clientes.session is uow.vehiculos.session is uow.session is sesion
