"""Deja la base en el estado inicial conocido (CH-02, consigna "Datos iniciales").

    python seed.py        (desde la raíz del repo, con el .env o el entorno configurados)

Vacía las 13 tablas y carga los datos en UNA transacción: o queda la carga
completa o la base queda como estaba. Corrido dos veces deja los mismos datos
con los mismos ids (empiezan en 1).

Es una herramienta de puesta en marcha, fuera de las capas de la aplicación:
usa su propia transacción (no un UnitOfWork) y escribe el stock junto con su
movimiento "Stock inicial". Las contraseñas de abajo son DE PRUEBA, de mentira,
y viven sólo en este archivo.
"""
import asyncio
from decimal import Decimal

import bcrypt
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

import app.modules.modelos as m
from app.core.config import get_settings
from app.core.database import crear_motor

# --- Datos (se aprueban en el checkpoint del seed; ver design.md) -------------

# Catálogo de estados: se carga PRIMERO. (codigo, descripcion, posicion, es_final)
CATALOGO = [
    ("PENDIENTE", "Ingresada, a la espera de un mecánico", 1, False),
    ("EN_REPARACION", "Un mecánico la está reparando", 2, False),
    ("TERMINADA", "Reparación terminada", 3, True),
    ("CANCELADA", "Cancelada antes de empezar la reparación", 4, True),
]

# Usuarios con su rol vigente y su contraseña de prueba. El orden fija los ids 1 a 7.
USUARIOS = [
    dict(email="admin@example.com", nombre="Ana Administradora", rol="ADMIN",
         password="Admin.2026", debe_cambiar_password=False),
    dict(email="admin2@example.com", nombre="Andrés Administrador", rol="ADMIN",
         password="Admin2.2026", debe_cambiar_password=False),
    dict(email="recepcion@example.com", nombre="Rita Recepción", rol="RECEPCION",
         password="Recepcion.2026", debe_cambiar_password=False),
    dict(email="mecanico@example.com", nombre="Mario Mecánico", rol="MECANICO",
         password="Mecanico.2026", debe_cambiar_password=False),
    dict(email="mecanico2@example.com", nombre="Marta Mecánica", rol="MECANICO",
         password="Mecanico2.2026", debe_cambiar_password=False),
    dict(email="cliente@example.com", nombre="Laura Cliente", rol="CLIENTE",
         password="Cliente.2026", debe_cambiar_password=False),
    dict(email="nuevo@example.com", nombre="Nicolás Nuevo", rol="MECANICO",
         password="Provisoria.2026", debe_cambiar_password=True),
]
CONTRASENAS = {u["email"]: u["password"] for u in USUARIOS}

# Clientes (ids 1 y 2) con sus vehículos (ids 1, 2 y 3, en este orden).
# usuario=None: cliente sin acceso a la API.
CLIENTES = [
    dict(nombre="Laura Cliente", documento="30111222", telefono="11 4000-1111",
         usuario="cliente@example.com",
         vehiculos=[("AB123CD", "Volkswagen", "Gol Trend", 2015),
                    ("AC456EF", "Toyota", "Etios", 2019)]),
    dict(nombre="Jorge Gómez", documento="25333444", telefono="11 4000-2222",
         usuario=None,
         vehiculos=[("AD789GH", "Ford", "Fiesta", 2012)]),
]

# Repuestos (ids 1 a 4); cada stock se registra como movimiento "Stock inicial".
REPUESTOS = [
    dict(codigo="FIL-001", descripcion="Filtro de aceite", precio=Decimal("8500.00"), stock=10),
    dict(codigo="FRE-010", descripcion="Pastillas de freno delanteras", precio=Decimal("32000.00"), stock=4),
    dict(codigo="BUJ-100", descripcion="Bujía de encendido", precio=Decimal("6500.00"), stock=2),
    dict(codigo="ACE-530", descripcion="Aceite 5W30 por litro", precio=Decimal("12000.00"), stock=20),
]
MOTIVO_STOCK_INICIAL = "Stock inicial"

# Historial de precio inicial: (codigo, precio anterior, precio nuevo); lo hace el admin.
HISTORIAL_PRECIO = ("FIL-001", Decimal("8000.00"), Decimal("8500.00"))

# Órdenes (ids 1 y 2). "vehiculo" es la patente. Los ítems son (codigo, cantidad);
# el precio unitario se copia del repuesto y el total se calcula. El historial son
# (desde, hasta, correo de quien hizo el cambio).
ORDENES = [
    dict(vehiculo="AB123CD", mecanico=None, estado="PENDIENTE",
         falla="Service de 60.000 km: cambio de aceite y filtro",
         items=[("FIL-001", 1), ("ACE-530", 4)],
         historial=[(None, "PENDIENTE", "recepcion@example.com")]),
    # 4 bujías cuando hay 2 en stock, a propósito (caso C-11).
    dict(vehiculo="AD789GH", mecanico="mecanico@example.com", estado="EN_REPARACION",
         falla="Falla de encendido: el motor ratea en frío",
         items=[("BUJ-100", 4)],
         historial=[(None, "PENDIENTE", "recepcion@example.com"),
                    ("PENDIENTE", "EN_REPARACION", "mecanico@example.com")]),
]

EVENTO_DE_SEGURIDAD = ("SISTEMA", "Carga de los datos iniciales")


# --- Carga ----------------------------------------------------------------------


async def _hashear(settings) -> dict[str, str]:
    """Hash bcrypt de cada contraseña de prueba (regla 9): en hilos, bajo un
    semáforo, con el costo de la configuración y ANTES de abrir la transacción."""
    semaforo = asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENT)

    async def uno(clave: str) -> str:
        async with semaforo:
            sal = bcrypt.gensalt(rounds=settings.BCRYPT_COST)
            return (await asyncio.to_thread(bcrypt.hashpw, clave.encode(), sal)).decode()

    correos = list(CONTRASENAS)
    hashes = await asyncio.gather(*(uno(CONTRASENAS[c]) for c in correos))
    return dict(zip(correos, hashes))


async def sembrar(engine, settings) -> None:
    hashes = await _hashear(settings)

    async with AsyncSession(engine, expire_on_commit=False) as session, session.begin():
        # TRUNCATE es transaccional en PostgreSQL: si algo falla después, se revierte.
        await session.exec(
            text(
                "TRUNCATE usuario, asignacion_rol, intento_acceso, evento_seguridad, cliente, vehiculo, "
                "repuesto, movimiento_stock, historial_precio_repuesto, estado_orden, orden_trabajo, "
                "item_orden, historial_estado_orden RESTART IDENTITY CASCADE"
            )
        )

        # 1. Catálogo.
        for codigo, descripcion, posicion, es_final in CATALOGO:
            session.add(m.EstadoOrden(codigo=codigo, descripcion=descripcion, posicion=posicion, es_final=es_final))
        await session.flush()

        # 2. Usuarios y sus roles (los otorga el sistema: otorgada_por vacío).
        usuarios = {}
        for datos in USUARIOS:
            usuario = m.Usuario(
                email=datos["email"],
                nombre=datos["nombre"],
                password_hash=hashes[datos["email"]],
                debe_cambiar_password=datos["debe_cambiar_password"],
            )
            session.add(usuario)
            usuarios[datos["email"]] = usuario
        await session.flush()
        for datos in USUARIOS:
            session.add(m.AsignacionRol(usuario_id=usuarios[datos["email"]].id, rol=datos["rol"]))
        await session.flush()
        admin = usuarios[USUARIOS[0]["email"]]

        # 3. Clientes y vehículos.
        vehiculos = {}
        for datos in CLIENTES:
            cliente = m.Cliente(
                usuario_id=usuarios[datos["usuario"]].id if datos["usuario"] else None,
                nombre=datos["nombre"],
                documento=datos["documento"],
                telefono=datos["telefono"],
            )
            session.add(cliente)
            await session.flush()
            for patente, marca, modelo, anio in datos["vehiculos"]:
                vehiculo = m.Vehiculo(cliente_id=cliente.id, patente=patente, marca=marca, modelo=modelo, anio=anio)
                session.add(vehiculo)
                await session.flush()
                vehiculos[patente] = vehiculo

        # 4. Repuestos, su movimiento "Stock inicial" y el historial de precio.
        repuestos = {}
        for datos in REPUESTOS:
            repuesto = m.Repuesto(**datos)
            session.add(repuesto)
            await session.flush()
            repuestos[repuesto.codigo] = repuesto
            session.add(
                m.MovimientoStock(
                    repuesto_id=repuesto.id,
                    orden_id=None,
                    usuario_id=admin.id,
                    cantidad=repuesto.stock,
                    motivo=MOTIVO_STOCK_INICIAL,
                )
            )
        codigo, anterior, nuevo = HISTORIAL_PRECIO
        session.add(
            m.HistorialPrecio(
                repuesto_id=repuestos[codigo].id, usuario_id=admin.id, precio_anterior=anterior, precio_nuevo=nuevo
            )
        )
        await session.flush()

        # 5. Órdenes con sus ítems (precio copiado, total calculado) y su historial.
        for datos in ORDENES:
            precios = [(repuestos[c], cantidad) for c, cantidad in datos["items"]]
            total = sum((r.precio * cantidad for r, cantidad in precios), Decimal("0.00"))
            orden = m.OrdenTrabajo(
                vehiculo_id=vehiculos[datos["vehiculo"]].id,
                mecanico_id=usuarios[datos["mecanico"]].id if datos["mecanico"] else None,
                estado=datos["estado"],
                falla=datos["falla"],
                total=total,
            )
            session.add(orden)
            await session.flush()
            for repuesto, cantidad in precios:
                session.add(
                    m.ItemOrden(
                        orden_id=orden.id, repuesto_id=repuesto.id, cantidad=cantidad, precio_unitario=repuesto.precio
                    )
                )
            for desde, hasta, quien in datos["historial"]:
                session.add(
                    m.HistorialEstadoOrden(
                        orden_id=orden.id, desde_estado=desde, hasta_estado=hasta, usuario_id=usuarios[quien].id
                    )
                )
            await session.flush()

        # 6. Historial de seguridad.
        actor, accion = EVENTO_DE_SEGURIDAD
        session.add(m.EventoSeguridad(actor=actor, accion=accion))
        await session.flush()


async def main() -> None:
    settings = get_settings()
    engine = crear_motor(settings)
    try:
        await sembrar(engine, settings)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
