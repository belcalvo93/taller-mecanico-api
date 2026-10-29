from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import ahora_utc
from app.core.paginacion import PaginaInexistente, ParametrosPagina
from app.modules.usuarios.models import AsignacionRol, IntentoAcceso, Usuario
from app.modules.usuarios.repository import (
    AsignacionRolRepository,
    EventoSeguridadRepository,
    IntentoAccesoRepository,
    UsuarioRepository,
)
from app.modules.usuarios.unit_of_work import UsuarioUnitOfWork


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

        # CH-05: listar_asignaciones_usuario incluye vigentes, vencidas y revocadas en orden de id
        asignaciones = await repo_roles.listar_asignaciones_usuario(user.id)
        assert [a.rol for a in asignaciones] == ["ADMIN", "RECEPCION", "MECANICO"]

        # CH-05: obtener_asignacion_abierta devuelve la fila con revocada_en IS NULL
        abierta_admin = await repo_roles.obtener_asignacion_abierta(user.id, "ADMIN")
        assert abierta_admin is not None and abierta_admin.revocada_en is None
        abierta_recepcion = await repo_roles.obtener_asignacion_abierta(user.id, "RECEPCION")
        assert abierta_recepcion is None

        # CH-05: contar_admins_vigentes en el seed cuenta a admin y admin2 (2)
        assert await repo_roles.contar_admins_vigentes() == 2


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


async def test_evento_seguridad_repository_y_paginacion(session_test):
    repo = EventoSeguridadRepository(session_test)
    ev1 = await repo.registrar(actor="SISTEMA", accion="Carga de los datos iniciales")
    ev2 = await repo.registrar(actor="admin@example.com", accion="Alta de usuario de personal")
    ev3 = await repo.registrar(actor="admin@example.com", accion="Asignación de rol")
    assert ev1.id is not None

    pagina1 = await repo.listar_paginado(ParametrosPagina(page=1, size=2))
    assert pagina1.total == 3
    assert pagina1.page == 1
    assert pagina1.size == 2
    assert pagina1.pages == 2
    assert [e.id for e in pagina1.items] == [ev1.id, ev2.id]

    pagina2 = await repo.listar_paginado(ParametrosPagina(page=2, size=2))
    assert [e.id for e in pagina2.items] == [ev3.id]

    with pytest.raises(PaginaInexistente):
        await repo.listar_paginado(ParametrosPagina(page=3, size=2))


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
