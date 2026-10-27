"""Registro de modelos: importa los cuatro models.py y reexporta las 13 clases.

Las relaciones entre módulos se resuelven por nombre al configurar los mapeos;
si sólo se importó un módulo, la primera consulta falla porque no conoce a los
otros. Lo importan migrations/env.py, seed.py, los tests y main.py.
"""
from app.modules.usuarios.models import (  # noqa: F401
    AsignacionRol,
    EventoSeguridad,
    IntentoAcceso,
    Usuario,
)
from app.modules.clientes.models import Cliente, Vehiculo  # noqa: F401
from app.modules.repuestos.models import (  # noqa: F401
    HistorialPrecio,
    MovimientoStock,
    Repuesto,
)
from app.modules.ordenes.models import (  # noqa: F401
    EstadoOrden,
    HistorialEstadoOrden,
    ItemOrden,
    OrdenTrabajo,
)
