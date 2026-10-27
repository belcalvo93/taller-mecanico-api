"""Ayudas compartidas de los tests contra la base real (CH-02)."""
import itertools
from datetime import datetime, timezone

import pytest
from sqlalchemy import column, table
from sqlalchemy.exc import DBAPIError

_contador = itertools.count(1)


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def constraint_name(exc: BaseException) -> str | None:
    """Nombre de la restricción violada, tal como lo informa PostgreSQL (asyncpg).

    Es lo que usan los changes siguientes para traducir IntegrityError a 409:
    nunca el texto del mensaje."""
    original = getattr(exc, "orig", exc)
    causa = getattr(original, "__cause__", None)
    return getattr(causa, "constraint_name", None)


async def rechaza(conexion, operacion) -> DBAPIError:
    """Ejecuta `operacion()` dentro de un SAVEPOINT y devuelve el error de la base."""
    with pytest.raises(DBAPIError) as exc:
        async with conexion.begin_nested():
            await operacion()
    return exc.value


def _validas() -> dict[str, dict]:
    n = next(_contador)
    return {
        "usuario": dict(email=f"u{n}@example.com", nombre="Usuario", password_hash="x",
                        activo=True, debe_cambiar_password=False),
        "asignacion_rol": dict(rol="ADMIN", desde=ahora()),
        "cliente": dict(nombre="Cliente", documento=f"doc{n}", telefono="1"),
        "vehiculo": dict(patente=f"PAT{n}", marca="Ford", modelo="Fiesta", anio=2012),
        "repuesto": dict(codigo=f"COD{n}", descripcion="Filtro", precio=100, stock=5),
        "estado_orden": dict(codigo=f"E{n}", descripcion="Estado", posicion=100 + n, es_final=False),
        "orden_trabajo": dict(estado="PENDIENTE", falla="Ruido", creada_en=ahora(), total=0),
        "item_orden": dict(cantidad=1, precio_unitario=100),
        "movimiento_stock": dict(cantidad=5, motivo="Stock inicial", cuando=ahora()),
        "historial_precio_repuesto": dict(precio_anterior=100, precio_nuevo=120, cuando=ahora()),
        "historial_estado_orden": dict(desde_estado=None, hasta_estado="PENDIENTE", cuando=ahora()),
        "evento_seguridad": dict(cuando=ahora(), actor="SISTEMA", accion="Prueba"),
        "intento_acceso": dict(cuando=ahora(), email="a@example.com", ip="127.0.0.1", exito=False),
    }


async def insertar(conexion, nombre: str, **valores):
    """INSERT de una fila válida de `nombre` con `valores` pisando los de por defecto.
    Devuelve el id (o el código en estado_orden). Sin SQL armado a mano."""
    fila = {**_validas()[nombre], **valores}
    tabla = table(nombre, *[column(c) for c in fila])
    clave = "codigo" if nombre == "estado_orden" else "id"
    res = await conexion.execute(tabla.insert().values(**fila).returning(column(clave)))
    return res.scalar_one()


async def escenario(conexion, catalogo: bool = True) -> dict:
    """Cadena mínima de filas válidas: usuario → cliente → vehículo → orden, un
    repuesto y (si `catalogo`) los estados PENDIENTE y EN_REPARACION."""
    if catalogo:
        await insertar(conexion, "estado_orden", codigo="PENDIENTE", posicion=1)
        await insertar(conexion, "estado_orden", codigo="EN_REPARACION", posicion=2)
    usuario = await insertar(conexion, "usuario")
    cliente = await insertar(conexion, "cliente", usuario_id=usuario)
    vehiculo = await insertar(conexion, "vehiculo", cliente_id=cliente)
    repuesto = await insertar(conexion, "repuesto")
    orden = None
    if catalogo:
        orden = await insertar(conexion, "orden_trabajo", vehiculo_id=vehiculo)
    return dict(usuario=usuario, cliente=cliente, vehiculo=vehiculo, repuesto=repuesto, orden=orden)
