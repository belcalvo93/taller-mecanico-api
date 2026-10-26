import asyncio
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["salud"])

TIEMPO_MAXIMO_READY_SEGUNDOS = 3
CUERPO_LIVE = {"estado": "ok"}
CUERPO_READY_OK = {"estado": "ok", "base": "ok"}
CUERPO_READY_NO_DISPONIBLE = {"estado": "no disponible", "base": "no disponible"}


@router.get("/live")
async def live() -> dict[str, str]:
    """Liveness: el proceso responde. No toca la base."""
    return CUERPO_LIVE


@router.get("/ready")
async def ready(session: AsyncSession = Depends(get_session)):
    """Readiness: hace SELECT 1 con tiempo máximo.

    Se captura Exception a propósito (es una sonda, RN-18): cualquier falla de
    la base significa "no listo" y nunca se devuelve el texto del error.
    """
    try:
        await asyncio.wait_for(
            session.exec(text("SELECT 1")), timeout=TIEMPO_MAXIMO_READY_SEGUNDOS
        )
    except Exception as exc:
        # Sólo la clase: el mensaje puede incluir host o usuario.
        logger.warning("ready: la base no está disponible (%s)", type(exc).__name__)
        return JSONResponse(CUERPO_READY_NO_DISPONIBLE, status_code=503)
    return CUERPO_READY_OK
