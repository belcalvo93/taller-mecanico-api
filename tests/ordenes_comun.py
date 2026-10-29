"""Ayudas compartidas de los tests de órdenes (CH-08): sesión real por login (design D12)."""
import seed
from sqlalchemy import text

# Ids del seed: 1 admin, 2 admin2, 3 recepción, 4 mecánico, 5 mecánico2, 6 Laura, 7 nuevo.
ADMIN, ADMIN2, RECEPCION, MECANICO, MECANICO2, LAURA, NUEVO = 1, 2, 3, 4, 5, 6, 7
EMAIL = {
    ADMIN: "admin@example.com", ADMIN2: "admin2@example.com", RECEPCION: "recepcion@example.com",
    MECANICO: "mecanico@example.com", MECANICO2: "mecanico2@example.com",
    LAURA: "cliente@example.com", NUEVO: "nuevo@example.com",
}
TEXTO_DE_LA_BASE = ("uq_", "duplicate", "violates", "viola", "asyncpg", "sqlalchemy", "traceback", "ck_")


async def sesion(client, usuario_id: int) -> dict[str, str]:
    """Login real por POST /auth/login; devuelve el encabezado Cookie para cada petición.

    Se limpia el cookie jar del cliente para que varias sesiones convivan en un test.
    """
    email = EMAIL[usuario_id]
    res = await client.post("/auth/login", json={"email": email, "password": seed.CONTRASENAS[email]})
    assert res.status_code == 200, res.text
    token = res.cookies["access_token"]
    client.cookies.clear()
    return {"Cookie": f"access_token={token}"}


def sin_texto_de_la_base(respuesta) -> None:
    cuerpo = respuesta.text.lower()
    for palabra in TEXTO_DE_LA_BASE:
        assert palabra not in cuerpo, palabra


async def crear_orden(motor, vehiculo_id: int, repuestos: list[int], lineas_historial: int = 1,
                      estado: str = "PENDIENTE", mecanico_id: int | None = None) -> int:
    """Inserta por SQL una orden con un ítem por repuesto (cantidad 1) y N líneas de historial."""
    async with motor.begin() as c:
        orden_id = (await c.execute(text(
            "INSERT INTO orden_trabajo (vehiculo_id, mecanico_id, estado, falla, creada_en, total) "
            "VALUES (:v, :m, :e, 'Prueba', now(), 0) RETURNING id"),
            {"v": vehiculo_id, "e": estado, "m": mecanico_id})).scalar()
        for r in repuestos:
            await c.execute(text(
                "INSERT INTO item_orden (orden_id, repuesto_id, cantidad, precio_unitario) "
                "VALUES (:o, :r, 1, 100)"), {"o": orden_id, "r": r})
        for n in range(lineas_historial):
            desde = None if n == 0 else "PENDIENTE"
            await c.execute(text(
                "INSERT INTO historial_estado_orden (orden_id, desde_estado, hasta_estado, usuario_id, cuando) "
                "VALUES (:o, :d, 'PENDIENTE', 3, now())"), {"o": orden_id, "d": desde})
    return orden_id
