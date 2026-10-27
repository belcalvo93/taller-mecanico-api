import asyncio
import secrets
from contextlib import asynccontextmanager

import bcrypt
from fastapi import APIRouter, FastAPI

from app.core.config import Settings, get_settings
from app.core.database import crear_fabrica_sesiones, crear_motor
import app.modules.modelos  # noqa: F401  (registra los 13 mapeos; sin esto las relaciones entre módulos no se resuelven)
from app.modules.health.router import router as health_router
from app.modules.usuarios.router import router as auth_router


async def _calcular_hash_ficticio(
    settings: Settings, semaforo: asyncio.Semaphore
) -> bytes:
    """Hash bcrypt de una contraseña aleatoria que se descarta (nadie la conoce).

    Se llama a bcrypt a través del módulo para poder contar las llamadas en
    los tests. bcrypt corre en un hilo y bajo el semáforo (regla 9).
    """
    async with semaforo:
        return await asyncio.to_thread(
            bcrypt.hashpw,
            secrets.token_bytes(32),
            bcrypt.gensalt(rounds=settings.BCRYPT_COST),
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Crea los recursos compartidos y los guarda en app.state (regla 7).

    Contrato de app.state: settings, engine, session_factory, bcrypt_semaforo
    y hash_ficticio (bytes). Si faltan secretos, get_settings() lanza
    ValidationError y la app no arranca. No conecta a la base: eso lo informa
    /health/ready.
    """
    settings = get_settings()
    engine = crear_motor(settings)
    try:
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = crear_fabrica_sesiones(engine)
        app.state.bcrypt_semaforo = asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENT)
        app.state.hash_ficticio = await _calcular_hash_ficticio(
            settings, app.state.bcrypt_semaforo
        )
        yield
    finally:
        await engine.dispose()


# Un FastAPI no es un recurso: no abre conexiones ni lee el entorno al importar.
app = FastAPI(title="Taller mecánico API", lifespan=lifespan)

rutas_abiertas = APIRouter()
rutas_protegidas = APIRouter()  # CH-05 le agrega, una sola vez, el control del cambio obligatorio

rutas_abiertas.include_router(health_router)

# Un include_router por change. Los módulos se agregan a cada grupo ANTES de
# incluir el grupo en la app: así funciona en todas las versiones de FastAPI
# (las anteriores copian las rutas en el momento de incluirlas).
rutas_abiertas.include_router(auth_router)
# CH-05: rutas_protegidas.include_router(usuarios_router)
# CH-06: rutas_protegidas.include_router(clientes_router)
# CH-07: rutas_protegidas.include_router(repuestos_router)
# CH-08: rutas_protegidas.include_router(ordenes_router)

app.include_router(rutas_abiertas)
app.include_router(rutas_protegidas)
