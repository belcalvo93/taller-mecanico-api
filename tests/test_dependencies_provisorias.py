import inspect
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi import Depends, FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import Settings
from app.core.database import ahora_utc, get_session
from app.modules.usuarios.models import AsignacionRol, Usuario


def test_firmas_definitivas_dependencies():
    """Verifica que las firmas de get_usuario_actual y requiere_rol sean las definitivas."""
    from app.core.dependencies import get_usuario_actual, requiere_rol

    # Firma de get_usuario_actual(request: Request, session: AsyncSession = Depends(get_session))
    sig_usuario = inspect.signature(get_usuario_actual)
    assert "request" in sig_usuario.parameters
    assert "session" in sig_usuario.parameters
    assert sig_usuario.parameters["session"].default is not inspect.Parameter.empty

    # Firma de requiere_rol(*roles: str) -> dependencia inyectable
    dep_rol = requiere_rol("ADMIN", "RECEPCION")
    assert callable(dep_rol)
    sig_rol = inspect.signature(dep_rol)
    assert "usuario" in sig_rol.parameters
    assert "session" in sig_rol.parameters


@pytest.fixture
def settings():
    return Settings(
        POSTGRES_USER="taller",
        POSTGRES_PASSWORD="secretpassword",
        POSTGRES_DB="taller",
        JWT_SECRET_KEY="supersecretkeythatisatleast32characterslong!",
        ACCESS_TOKEN_EXPIRE_SECONDS=1800,
    )


async def test_get_usuario_actual_sin_cookie_da_401(settings):
    from app.core.dependencies import get_usuario_actual

    app = FastAPI()
    app.state.settings = settings
    app.dependency_overrides[get_session] = lambda: AsyncMock(spec=AsyncSession)

    @app.get("/yo")
    async def yo(u: Usuario = Depends(get_usuario_actual)):
        return {"id": u.id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Petición sin cookie
        r = await c.get("/yo")
        assert r.status_code == 401


async def test_get_usuario_actual_con_authorization_sin_cookie_da_401(settings):
    from app.core.dependencies import get_usuario_actual
    from app.core.security import crear_access_token

    app = FastAPI()
    app.state.settings = settings
    app.dependency_overrides[get_session] = lambda: AsyncMock(spec=AsyncSession)

    token = crear_access_token(usuario_id=1, roles=["ADMIN"], settings=settings)

    @app.get("/yo")
    async def yo(u: Usuario = Depends(get_usuario_actual)):
        return {"id": u.id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Petición enviando token sólo en cabecera Authorization: Bearer
        r = await c.get("/yo", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 401


async def test_get_usuario_actual_token_invalido_da_401(settings):
    from app.core.dependencies import get_usuario_actual

    app = FastAPI()
    app.state.settings = settings
    app.dependency_overrides[get_session] = lambda: AsyncMock(spec=AsyncSession)

    @app.get("/yo")
    async def yo(u: Usuario = Depends(get_usuario_actual)):
        return {"id": u.id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies={"access_token": "token_invalido"}) as c:
        r = await c.get("/yo")
        assert r.status_code == 401


async def test_get_usuario_actual_token_anterior_a_cambio_password_da_401(settings):
    from app.core.dependencies import get_usuario_actual
    from app.core.security import crear_access_token

    ahora = ahora_utc()
    # Token emitido a las T0
    token = crear_access_token(usuario_id=1, roles=["CLIENTE"], settings=settings, ahora=ahora)

    # El usuario cambió la contraseña a T0 + 1 microsegundo
    usuario = Usuario(
        id=1,
        email="test@example.com",
        nombre="Test",
        password_hash="hash",
        activo=True,
        password_cambiada_en=ahora + timedelta(microseconds=1),
    )

    app = FastAPI()
    app.state.settings = settings

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.get.return_value = usuario

    app.dependency_overrides[get_session] = lambda: mock_session

    @app.get("/yo")
    async def yo(u: Usuario = Depends(get_usuario_actual)):
        return {"id": u.id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies={"access_token": token}) as c:
        r = await c.get("/yo")
        assert r.status_code == 401


async def test_get_usuario_actual_usuario_inactivo_da_401(settings):
    from app.core.dependencies import get_usuario_actual
    from app.core.security import crear_access_token

    token = crear_access_token(usuario_id=1, roles=["CLIENTE"], settings=settings)

    usuario = Usuario(
        id=1,
        email="inactivo@example.com",
        nombre="Inactivo",
        password_hash="hash",
        activo=False,
    )

    app = FastAPI()
    app.state.settings = settings

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.get.return_value = usuario
    app.dependency_overrides[get_session] = lambda: mock_session

    @app.get("/yo")
    async def yo(u: Usuario = Depends(get_usuario_actual)):
        return {"id": u.id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies={"access_token": token}) as c:
        r = await c.get("/yo")
        assert r.status_code == 401


async def test_get_usuario_actual_valido_da_200(settings):
    from app.core.dependencies import get_usuario_actual
    from app.core.security import crear_access_token

    ahora = ahora_utc()
    usuario = Usuario(
        id=10,
        email="valido@example.com",
        nombre="Valido",
        password_hash="hash",
        activo=True,
        password_cambiada_en=ahora - timedelta(minutes=10),
    )

    token = crear_access_token(usuario_id=10, roles=["MECANICO"], settings=settings, ahora=ahora)

    app = FastAPI()
    app.state.settings = settings

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.get.return_value = usuario
    app.dependency_overrides[get_session] = lambda: mock_session

    @app.get("/yo")
    async def yo(u: Usuario = Depends(get_usuario_actual)):
        return {"id": u.id, "email": u.email}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies={"access_token": token}) as c:
        r = await c.get("/yo")
        assert r.status_code == 200
        assert r.json() == {"id": 10, "email": "valido@example.com"}


async def test_requiere_rol_valida_rol_vigente(settings):
    from app.core.dependencies import get_usuario_actual, requiere_rol
    from app.core.security import crear_access_token

    usuario = Usuario(
        id=5,
        email="mecanico@example.com",
        nombre="Mecanico",
        password_hash="hash",
        activo=True,
    )

    token = crear_access_token(usuario_id=5, roles=["MECANICO"], settings=settings)

    app = FastAPI()
    app.state.settings = settings

    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.get.return_value = usuario

    # Simular roles vigentes devueltos por la consulta
    mock_result_mecanico = MagicMock()
    mock_result_mecanico.scalars.return_value.all.return_value = ["MECANICO"]
    mock_session.exec.return_value = mock_result_mecanico

    app.dependency_overrides[get_session] = lambda: mock_session

    @app.get("/reparar")
    async def reparar(u: Usuario = Depends(requiere_rol("MECANICO"))):
        return {"reparando": True}

    @app.get("/administrar")
    async def administrar(u: Usuario = Depends(requiere_rol("ADMIN"))):
        return {"administrando": True}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", cookies={"access_token": token}) as c:
        # Tiene rol MECANICO -> 200
        r_ok = await c.get("/reparar")
        assert r_ok.status_code == 200
        assert r_ok.json() == {"reparando": True}

        # Pide rol ADMIN y no lo tiene -> 403
        r_forbidden = await c.get("/administrar")
        assert r_forbidden.status_code == 403
