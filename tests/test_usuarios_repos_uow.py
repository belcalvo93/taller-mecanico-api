from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import ahora_utc
from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import AsignacionRol, IntentoAcceso, Usuario
from app.modules.usuarios.repository import (
    AsignacionRolRepository,
    EventoSeguridadRepository,
    IntentoAccesoRepository,
    UsuarioRepository,
)
from app.modules.usuarios.unit_of_work import UsuarioUnitOfWork, get_usuario_uow


@pytest.fixture
async def session_test(motor, vaciar_al_terminar):
    session_factory = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


async def test_usuario_repository(sembrada, motor):
    session_factory = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        repo = UsuarioRepository(session)
        # get_by_email existente
        user = await repo.get_by_email("admin@example.com")
        assert user is not None
        assert user.email == "admin@example.com"
        assert user.nombre == "Ana Administradora"

        # get_by_email inexistente
        inexistente = await repo.get_by_email("nadie@example.com")
        assert inexistente is None

        # get_by_id_con_asignaciones precarga asignaciones (lazy='raise' no explota)
        user_con_roles = await repo.get_by_id_con_asignaciones(user.id)
        assert user_con_roles is not None
        assert len(user_con_roles.asignaciones) > 0
        assert user_con_roles.asignaciones[0].rol == "ADMIN"


async def test_asignacion_rol_repository(sembrada, motor):
    session_factory = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        repo_user = UsuarioRepository(session)
        repo_roles = AsignacionRolRepository(session)
        user = await repo_user.get_by_email("admin@example.com")
        assert user is not None

        # listar_roles_vigentes inicial
        roles = await repo_roles.listar_roles_vigentes(user.id)
        assert "ADMIN" in roles

        # Agregar un rol revocado
        rol_revocado = AsignacionRol(
            usuario_id=user.id,
            rol="RECEPCION",
            revocada_en=ahora_utc(),
        )
        await repo_roles.add(rol_revocado)

        # Agregar un rol vencido
        rol_vencido = AsignacionRol(
            usuario_id=user.id,
            rol="MECANICO",
            vence_en=ahora_utc() - timedelta(minutes=5),
        )
        await repo_roles.add(rol_vencido)

        # listar_roles_vigentes no debe incluir revocados ni vencidos
        roles_vigentes = await repo_roles.listar_roles_vigentes(user.id)
        assert "RECEPCION" not in roles_vigentes
        assert "MECANICO" not in roles_vigentes
        assert "ADMIN" in roles_vigentes


async def test_intento_acceso_repository(session_test):
    repo = IntentoAccesoRepository(session_test)
    email = "test_limite@example.com"
    ip = "127.0.0.1"
    ahora = ahora_utc()

    # Sin intentos
    cant, primer = await repo.contar_fallos_vigentes_y_primer_fallo(
        email, ip, ahora - timedelta(seconds=60)
    )
    assert cant == 0
    assert primer is None

    # Insertar 3 fallos
    for i in range(3):
        intento = IntentoAcceso(
            email=email,
            ip=ip,
            exito=False,
            cuando=ahora - timedelta(seconds=30 - i * 5),
        )
        await repo.add(intento)

    cant, primer = await repo.contar_fallos_vigentes_y_primer_fallo(
        email, ip, ahora - timedelta(seconds=60)
    )
    assert cant == 3
    assert primer is not None

    # Insertar un intento exitoso posterior
    exito = IntentoAcceso(
        email=email,
        ip=ip,
        exito=True,
        cuando=ahora - timedelta(seconds=10),
    )
    await repo.add(exito)

    # El conteo debe reiniciarse (los 3 fallos anteriores al éxito ya no cuentan)
    cant, primer = await repo.contar_fallos_vigentes_y_primer_fallo(
        email, ip, ahora - timedelta(seconds=60)
    )
    assert cant == 0
    assert primer is None

    # Un nuevo fallo posterior al éxito
    fallo_nuevo = IntentoAcceso(
        email=email,
        ip=ip,
        exito=False,
        cuando=ahora - timedelta(seconds=5),
    )
    await repo.add(fallo_nuevo)

    cant, primer = await repo.contar_fallos_vigentes_y_primer_fallo(
        email, ip, ahora - timedelta(seconds=60)
    )
    assert cant == 1
    assert primer == fallo_nuevo.cuando


async def test_evento_seguridad_repository(session_test):
    repo = EventoSeguridadRepository(session_test)
    ev = await repo.registrar(actor="test@example.com", accion="ALTA_USUARIO_CLIENTE")
    assert ev.id is not None
    assert ev.actor == "test@example.com"
    assert ev.accion == "ALTA_USUARIO_CLIENTE"


async def test_usuario_unit_of_work_commit_and_rollback(motor, vaciar_al_terminar):
    session_factory = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)

    # 1. Commit exitoso al salir del bloque
    async with session_factory() as session:
        uow = UsuarioUnitOfWork(session)
        async with uow:
            u = Usuario(
                email="uow_test@example.com",
                nombre="UoW Test",
                password_hash="hash123",
                activo=True,
            )
            await uow.usuarios.add(u)
            assert u.id is not None

    # Verificar que se persistió en una nueva sesión
    async with session_factory() as session:
        uow = UsuarioUnitOfWork(session)
        u_persisted = await uow.usuarios.get_by_email("uow_test@example.com")
        assert u_persisted is not None

    # 2. Rollback automático ante excepción
    try:
        async with session_factory() as session:
            uow = UsuarioUnitOfWork(session)
            async with uow:
                u2 = Usuario(
                    email="uow_fail@example.com",
                    nombre="UoW Fail",
                    password_hash="hash123",
                    activo=True,
                )
                await uow.usuarios.add(u2)
                raise RuntimeError("Error forzado para rollback")
    except RuntimeError:
        pass

    # Verificar que NO se persistió
    async with session_factory() as session:
        uow = UsuarioUnitOfWork(session)
        u_reverted = await uow.usuarios.get_by_email("uow_fail@example.com")
        assert u_reverted is None
