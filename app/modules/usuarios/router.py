from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.modules.usuarios import service
from app.modules.usuarios.schemas import RegistroRequest, RegistroResponse
from app.modules.usuarios.unit_of_work import UsuarioUnitOfWork, get_usuario_uow

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/registro",
    response_model=RegistroResponse,
    status_code=status.HTTP_201_CREATED,
)
async def registro(
    datos: RegistroRequest,
    request: Request,
    uow: UsuarioUnitOfWork = Depends(get_usuario_uow),
) -> RegistroResponse:
    settings = request.app.state.settings
    semaforo = request.app.state.bcrypt_semaforo

    try:
        return await service.registrar_cliente(datos, uow, settings, semaforo)
    except service.EmailDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except service.DocumentoDuplicadoError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
