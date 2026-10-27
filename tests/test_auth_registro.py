import pytest
from sqlmodel import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession

from app.modules.clientes.models import Cliente
from app.modules.usuarios.models import AsignacionRol, EventoSeguridad, Usuario
from app.modules.usuarios.schemas import ACCION_ALTA_CLIENTE


async def test_registro_cliente_exitoso_201(client, sembrada, motor):
    datos = {
        "email": "nuevo_cliente@example.com",
        "nombre": "Nuevo Cliente",
        "password": "Password.123",
        "documento": "99888777",
        "telefono": "11 5555-5555",
    }
    response = await client.post("/auth/registro", json=datos)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "nuevo_cliente@example.com"
    assert body["nombre"] == "Nuevo Cliente"
    assert body["documento"] == "99888777"
    assert body["telefono"] == "11 5555-5555"
    assert "password_hash" not in body
    assert body["id"] is not None
    user_id = body["id"]

    # Verificación en la base de datos de las cuatro tablas
    session_factory = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # 1. Usuario
        usuario = await session.get(Usuario, user_id)
        assert usuario is not None
        assert usuario.email == "nuevo_cliente@example.com"
        assert usuario.activo is True
        assert usuario.debe_cambiar_password is False

        # 2. Asignación de rol CLIENTE
        stmt_rol = select(AsignacionRol).where(
            AsignacionRol.usuario_id == user_id,
            AsignacionRol.rol == "CLIENTE",
            AsignacionRol.revocada_en.is_(None),
        )
        rol = (await session.exec(stmt_rol)).first()
        assert rol is not None

        # 3. Ficha de Cliente
        stmt_cli = select(Cliente).where(Cliente.usuario_id == user_id)
        cliente_db = (await session.exec(stmt_cli)).first()
        assert cliente_db is not None
        assert cliente_db.documento == "99888777"

        # 4. Evento de seguridad
        stmt_ev = select(EventoSeguridad).where(
            EventoSeguridad.actor == "nuevo_cliente@example.com",
            EventoSeguridad.accion == ACCION_ALTA_CLIENTE,
        )
        evento = (await session.exec(stmt_ev)).first()
        assert evento is not None


async def test_registro_email_duplicado_409(client, sembrada, motor):
    # cliente@example.com ya existe en el seed
    datos = {
        "email": "cliente@example.com",
        "nombre": "Otro Nombre",
        "password": "Password.123",
        "documento": "99111222",
        "telefono": "11 9999-9999",
    }
    response = await client.post("/auth/registro", json=datos)
    assert response.status_code == 409
    body = response.json()
    assert "correo" in body["detail"].lower() or "email" in body["detail"].lower()
    # No filtra texto de PostgreSQL / asyncpg
    assert "asyncpg" not in body["detail"].lower()
    assert "duplicate" not in body["detail"].lower()
    assert "uq_usuario_email" not in body["detail"]

    # Verificar que no quedaron filas huérfanas
    session_factory = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        stmt_cli = select(Cliente).where(Cliente.documento == "99111222")
        cli = (await session.exec(stmt_cli)).first()
        assert cli is None


async def test_registro_documento_duplicado_rollback_total_409(client, sembrada, motor):
    # En el seed, Jorge Gómez tiene doc 25333444 y usuario_id=None
    datos = {
        "email": "nuevo_intento@example.com",
        "nombre": "Jorge Intento",
        "password": "Password.123",
        "documento": "25333444",
        "telefono": "11 8888-8888",
    }
    response = await client.post("/auth/registro", json=datos)
    assert response.status_code == 409
    body = response.json()
    assert "documento" in body["detail"].lower()
    assert "asyncpg" not in body["detail"].lower()
    assert "uq_cliente_documento" not in body["detail"]

    # Verificar rollback atómico total:
    session_factory = async_sessionmaker(motor, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        # El usuario no quedó creado
        stmt_user = select(Usuario).where(Usuario.email == "nuevo_intento@example.com")
        assert (await session.exec(stmt_user)).first() is None

        # La ficha de Jorge Gómez sigue intacta con usuario_id=None
        stmt_jorge = select(Cliente).where(Cliente.documento == "25333444")
        jorge = (await session.exec(stmt_jorge)).first()
        assert jorge is not None
        assert jorge.usuario_id is None

        # No se creó evento de seguridad
        stmt_ev = select(EventoSeguridad).where(
            EventoSeguridad.actor == "nuevo_intento@example.com"
        )
        assert (await session.exec(stmt_ev)).first() is None


async def test_registro_validaciones_422(client):
    # 1. Campo extra no permitido (ej. 'rol')
    res_extra = await client.post(
        "/auth/registro",
        json={
            "email": "hacker@example.com",
            "nombre": "Hacker",
            "password": "Password.123",
            "documento": "11222333",
            "telefono": "11 2222-3333",
            "rol": "ADMIN",
        },
    )
    assert res_extra.status_code == 422

    # 2. Contraseña de más de 72 bytes en UTF-8
    res_larga = await client.post(
        "/auth/registro",
        json={
            "email": "larga@example.com",
            "nombre": "Larga",
            "password": "a" * 73,
            "documento": "11222334",
            "telefono": "11 2222-3334",
        },
    )
    assert res_larga.status_code == 422

    # 3. Contraseña de 37 letras 'ñ' = 74 bytes UTF-8
    res_enes = await client.post(
        "/auth/registro",
        json={
            "email": "enes@example.com",
            "nombre": "Enes",
            "password": "ñ" * 37,
            "documento": "11222335",
            "telefono": "11 2222-3335",
        },
    )
    assert res_enes.status_code == 422
