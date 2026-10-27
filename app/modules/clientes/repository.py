from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.repository import BaseRepository
from app.modules.clientes.models import Cliente


class ClienteRepository(BaseRepository[Cliente]):
    """Repositorio de clientes.
    
    Creado con la firma estándar según DD-13 para ser compartido entre usuarios y clientes.
    """

    def __init__(self, session: AsyncSession, model_cls: type[Cliente] = Cliente) -> None:
        super().__init__(session, model_cls)
