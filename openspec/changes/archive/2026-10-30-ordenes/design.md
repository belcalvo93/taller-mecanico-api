# Design

## Context

Motivación y alcance: ver `proposal.md`. Requisitos: `specs/ordenes-de-trabajo`, `specs/consulta-de-ordenes`, `specs/catalogo-estados-orden`.

Estado de `main` (29/10, commit `b7e5b73`): CH-01..CH-06 mergeados. CH-07 (`repuestos-y-stock`, Bruno) **no** está en `main` ni tiene rama. Ver D1 y D4.

Modelos de CH-02 que se usan (no se tocan): `EstadoOrden` (PK `codigo`, `posicion` única, `es_final`), `OrdenTrabajo` (`estado` FK al catálogo, CHECK `total >= 0`, `total` NUMERIC(12,2)), `ItemOrden` (UNIQUE `uq_item_orden_orden_id_repuesto_id`, CHECKs de cantidad y precio), `HistorialEstadoOrden` (sólo agregado por trigger; relación `OrdenTrabajo.historial` con `order_by id`), `Repuesto` (CHECK `ck_repuesto_stock_no_negativo`), `MovimientoStock`. **Todas las relaciones tienen `lazy="raise"`**: cualquier acceso sin precarga revienta, lo que hace visible un N+1.

Datos del seed que usan los tests y los `.http`: usuarios 1 admin, 2 admin2, 3 recepción, 4 mecánico, 5 mecánico2, 6 Laura (CLIENTE), 7 nuevo (MECANICO, cambio obligatorio). Cliente 1 Laura (vehículos 1 `AB123CD` y 2 `AC456EF`), cliente 2 Jorge (sin usuario, vehículo 3 `AD789GH`). Repuestos 1 `FIL-001` (10), 2 `FRE-010` (4, 32000.00), 3 `BUJ-100` (2), 4 `ACE-530` (20, 12000.00). Orden 1 PENDIENTE del vehículo 1 (ítems FIL-001×1, ACE-530×4); orden 2 EN_REPARACION del vehículo 3, asignada al usuario 4, con BUJ-100×4.

## Goals / Non-Goals

**Goals:**
- Las ocho rutas de la tabla de la consigna con exactamente sus códigos (más 401/403 del grupo protegido).
- RN-13 en un único bloque de UoW; RN-10 (alta) también.
- Detalle con un número fijo de consultas (3 para la orden, independiente de ítems e historial).
- Que todo lo que no toca stock se pueda implementar, probar y revisar **antes** de que CH-07 llegue a `main`.

**Non-Goals:**
- Escribir stock o movimientos: es del punto único de CH-07 (D4).
- Concurrencia fina sobre el stock (la garantiza el CHECK de la base y el punto único de CH-07).
- Notificación real al cliente: el aviso es simulado (sleep + registro).

## Decisions

### D1 — Qué se usa de lo ya mergeado

| Pieza | De dónde | Cómo la usa CH-08 |
|---|---|---|
| `BaseRepository`, `SoftDeleteRepository`, `_paginar`, `Pagina`, `parametros_pagina`, `PaginaInexistente` | CH-03 | base de `OrdenRepository` y del historial; listados paginados (el 422 de página inexistente ya lo traduce `main.py`) |
| `UnitOfWork` | CH-03 | base de `OrdenesUnitOfWork` |
| `get_usuario_actual`, `requiere_rol` (reales) | CH-04/CH-05 | 401 y 403 por rol en la ruta |
| `AsignacionRolRepository.listar_roles_vigentes(usuario_id)` | CH-05 | roles vigentes para las decisiones del servicio (detalle, cancelar, terminar), en la misma sesión |
| `VehiculoRepository.get_by_id` | CH-06 | vehículo vigente al crear (RN-16) |
| `RepuestoRepository` + punto único de stock | **CH-07 (pendiente)** | ver D2 y D4 |

### D2 — `OrdenesUnitOfWork` y el repositorio de repuestos antes y después de CH-07
`OrdenesUnitOfWork(session)` compone, todos con la misma sesión: `ordenes` (`OrdenRepository`), `historial` (`HistorialEstadoOrdenRepository`), `estados` (`EstadoOrdenRepository`), `vehiculos` (`VehiculoRepository`), `roles` (`AsignacionRolRepository`) y `repuestos`.
- **Hasta que CH-07 esté en `main`**, `repuestos` es `SoftDeleteRepository(session, Repuesto)`: el genérico de CH-03 ya ofrece todo lo que usan crear (`get_by_id`, que excluye dados de baja) y terminar (`get_by_id_including_deleted`). No se crea un `RepuestoRepository` propio en CH-08 (sería duplicar el de Bruno).
- **Cuando CH-07 mergee**, se cambia esa única línea por `RepuestoRepository(session)` (hereda de `SoftDeleteRepository[Repuesto]`, así que lo ya probado sigue valiendo) y recién ahí se implementa el descuento de stock.
- **Alternativa descartada**: esperar a CH-07 para empezar. Dejaría todo CH-08 en el último día.

### D3 — `EstadoOrdenRepository` de sólo lectura, sin herencia
Clase propia que recibe la sesión y ofrece `listar_por_posicion()` y `get(codigo)`. **No** hereda de `BaseRepository` (su PK no es `id` y desde la API no se escribe): no tiene `add`, `update` ni `delete`. Un test lo verifica (`not issubclass(...)` y ausencia de esos atributos).
El enum `EstadoOrdenCodigo(StrEnum)` (PENDIENTE, EN_REPARACION, TERMINADA, CANCELADA) vive en `schemas.py`; un test compara sus valores con los códigos que carga `seed.py`. El servicio nombra los estados con el enum, nunca con cadenas sueltas.

### D4 — Contrato con CH-07: el punto único de escritura de stock
CH-08 **consume** y no escribe el punto único (RN-14, DD-14). Firma esperada, a acordar con Bruno antes de su merge:

```python
# app/modules/repuestos/repository.py (CH-07)
class RepuestoRepository(SoftDeleteRepository[Repuesto]):
    async def mover_stock(
        self, repuesto: Repuesto, cantidad: int, *,
        motivo: str, usuario_id: int, orden_id: int | None = None,
    ) -> MovimientoStock: ...
```

- `cantidad` positiva suma, negativa descuenta; actualiza `repuesto.stock` y agrega el `movimiento_stock` (con `orden_id`) **en la sesión recibida**, con `flush()` y **sin commit**.
- **No abre ni construye un Unit of Work**: por eso tiene que vivir en el repositorio (o ser una función que recibe repositorios/sesión), no en un método de servicio que haga `async with uow`. Es el requisito no negociable: si abriera su propia transacción, RN-13 no se cumpliría (el UoW no se anida).
- Stock insuficiente: lanza una excepción de dominio de CH-07 (p. ej. `StockInsuficiente`) **o** deja que el CHECK `ck_repuesto_stock_no_negativo` falle en el `flush`. CH-08 cubre las dos: atrapa la excepción de dominio y, fuera del bloque, traduce el `IntegrityError` de esa restricción (por nombre, como CH-06) a su propio `StockInsuficiente` → 409.
- Si el nombre o la ubicación finales difieren, CH-08 adapta **sólo** la llamada en `terminar_orden` (un único lugar); no toca el código de CH-07.
- Motivo de los movimientos: `"Orden {id} terminada"`.

### D5 — Alta de una orden (un solo bloque)
Orden de comprobaciones dentro de `async with uow`:
1. El catálogo tiene PENDIENTE (`estados.get`) → si no, `CatalogoVacio` (409). Va primero porque sin catálogo no hay nada que validar, y permite probarlo sin armar vehículo ni repuestos.
2. Vehículo vigente (`vehiculos.get_by_id`) → si no, `VehiculoNoDisponible` (409; inexistente y dado de baja dan lo mismo: el id viaja en el cuerpo, no en la ruta, y la tabla de la consigna no da 404).
3. Cada repuesto vigente (`repuestos.get_by_id`) → si alguno falta, `RepuestoNoDisponible` (409). No es una "consulta previa de unicidad" (regla 6): un repuesto dado de baja no violaría ninguna FK, hay que mirarlo.
4. Total = Σ `cantidad × precio` en `Decimal`; si supera `9_999_999_999.99` → `TotalExcedido` (409): si no, el INSERT daría un error numérico (500, RN-18).
5. `ordenes.add(orden)` (flush, obtiene el id), los ítems con `precio_unitario` copiado, y `historial.add` (null → PENDIENTE, usuario actual).

Al salir, el UoW confirma; luego el servicio abre otro bloque y devuelve `get_detalle(id)` (D7). Cualquier excepción dentro del bloque revierte todo (nada queda creado).

### D6 — Transiciones: lectura con bloqueo, permiso, estado, escritura
`OrdenRepository.get_para_transicion(id)`: la orden con `joinedload(vehiculo → cliente)` (para saber el dueño) y `selectinload(items)` (para terminar), con `with_for_update(of=OrdenTrabajo)`. El bloqueo evita que dos peticiones simultáneas hagan la misma transición y dupliquen la línea de historial (`of=` porque PostgreSQL no admite `FOR UPDATE` sobre el lado nulo de un outer join).

| Operación | Ruta (`requiere_rol`) | Servicio, en este orden |
|---|---|---|
| iniciar | `MECANICO` | 404 → estado ≠ PENDIENTE: 409 → `estado=EN_REPARACION`, `mecanico_id=usuario.id`, historial |
| terminar | `MECANICO`, `ADMIN` | 404 → ni ADMIN vigente ni `mecanico_id == usuario.id`: 403 → estado ≠ EN_REPARACION: 409 → stock (D4) por ítem, ordenado por `repuesto_id` → `estado=TERMINADA`, historial |
| cancelar | **ninguno** | 404 → ni RECEPCION/ADMIN vigente ni dueño: 403 → estado ≠ PENDIENTE: 409 → `estado=CANCELADA`, historial |

**Bloqueo de repuestos al terminar.** Bloquear la orden no basta: dos órdenes distintas con el mismo repuesto leerían el mismo stock y `mover_stock` (absoluto: `SET stock = <valor>`) pisaría un descuento. Por eso `terminar_orden` llama a `OrdenRepository.bloquear_repuestos(ids)`: `SELECT ... WHERE id IN (...) ORDER BY id FOR UPDATE` con `populate_existing` (incluye dados de baja, DD-14), dentro del mismo bloque del UoW y antes de comprobar el stock. El orden ascendente de `repuesto_id` es el orden único de bloqueo (sin interbloqueos); la segunda terminación espera, relee el stock ya descontado y obtiene 409 si no alcanza. La escritura sigue siendo sólo de `mover_stock` (RN-14).

- "Dueño" = `orden.vehiculo.cliente.usuario_id == usuario.id` (aunque el vehículo esté dado de baja: la orden sigue siendo suya).
- En terminar, el 403 del mecánico asignado requiere además su rol MECANICO vigente: lo garantiza `requiere_rol` en la ruta. Un ADMIN que además es el asignado, pasa por cualquiera de las dos.
- 404 antes que 403: una orden inexistente no tiene relación con nadie (mismo criterio que SU-04).
- Cada repuesto de terminar se busca con `get_by_id_including_deleted` (DD-14). Se recorren ordenados por `repuesto_id` para que dos terminaciones concurrentes tomen los bloqueos de fila en el mismo orden.

### D7 — Detalle sin N+1
`OrdenRepository.get_detalle(id)` declara en el método:
`joinedload(OrdenTrabajo.vehiculo).joinedload(Vehiculo.cliente)`, `selectinload(OrdenTrabajo.items).joinedload(ItemOrden.repuesto)`, `selectinload(OrdenTrabajo.historial)`, con `execution_options(populate_existing=True)`.
- Son **3 SELECT fijos** (orden+vehículo+cliente; ítems+repuestos; historial), con 2 o con 40 ítems.
- `populate_existing` porque después de una transición el objeto ya está en el identity map (`expire_on_commit=False`) con colecciones viejas o sin cargar; sin eso el detalle podría salir desactualizado o tocar una relación `lazy="raise"`.
- Los ítems se ordenan por `id` al armar la salida (el `selectinload` no garantiza orden; el historial ya tiene `order_by` en el modelo).
- La salida la arma una función pura `armar_detalle(orden) -> OrdenDetalle` (calcula `subtotal = cantidad × precio_unitario`, toma `patente` y `cliente` de las relaciones): se prueba sin base.
- Permiso del detalle: personal (RECEPCION, ADMIN o MECANICO vigente) o dueño → si no, 403. Las consultas de roles son una cantidad fija y no dependen de los ítems.

### D8 — Listados
- `OrdenRepository.listar(estado: str | None, pagina)`: `joinedload(vehiculo → cliente)` (muchos-a-uno: una fila por orden, no infla el total de `_paginar`), filtro `estado` con parámetro ligado, orden por `id`. Ruta con `requiere_rol("RECEPCION", "ADMIN", "MECANICO")`; `estado: EstadoOrdenCodigo | None = Query(None)` → un valor no declarado da 422 antes del handler.
- `OrdenRepository.listar_de_usuario(usuario_id, pagina)`: `JOIN vehiculo JOIN cliente WHERE cliente.usuario_id = :usuario`; incluye órdenes de vehículos dados de baja (son historia del cliente). Usuario sin ficha → página vacía (`total` 0, `pages` 1). Ruta sin rol (sólo `get_usuario_actual`).
- Salida `OrdenResumen` (sin ítems ni historial) dentro de `Pagina[OrdenResumen]`.

### D9 — Contratos (`schemas.py`)
- Entradas con `ConfigDict(extra="forbid")`. `OrdenCrear`: `vehiculo_id` (1..2³¹−1), `falla` (strip, 1..500, sin NUL), `items: list[ItemOrdenCrear]` (1..50) con un `model_validator` que rechaza `repuesto_id` repetidos (RN-10 "DTO"). `ItemOrdenCrear`: `repuesto_id` (1..2³¹−1), `cantidad` (1..10 000).
- Ids de ruta: `IdRuta = Annotated[int, Path(ge=1, le=2_147_483_647)]`, igual que CH-06 (C-01, sin 500 de asyncpg).
- Salidas: `OrdenDetalle`, `ItemOrdenLeer`, `HistorialLeer`, `OrdenResumen`, `EstadoOrdenLeer`. Importes `Decimal` (Pydantic los serializa como texto: `"68000.00"`), fechas con zona.

### D10 — Router y traducción de errores
Mismo patrón que CH-06: `get_ordenes_uow` construye el UoW, el handler llama al servicio dentro de `_traducir_errores()`, una tabla `excepción → (código, mensaje propio)`:
`OrdenNoEncontrada` 404 · `SinPermisoSobreOrden` 403 · `TransicionInvalida` 409 ("La orden está en <estado>: no se puede <acción>") · `CatalogoVacio` 409 ("El catálogo de estados está vacío: cargue los datos iniciales") · `VehiculoNoDisponible` 409 · `RepuestoNoDisponible` 409 · `TotalExcedido` 409 · `StockInsuficiente` 409 ("No hay stock suficiente de <código>"). Nunca texto de la base.
Se registra con una línea en el grupo protegido de `main.py` (la de CH-08, ya reservada con un comentario).

### D11 — Aviso con `BackgroundTasks`
El handler de terminar recibe `background_tasks: BackgroundTasks`, llama al servicio y, **sólo si volvió sin excepción** (el UoW ya confirmó al salir del bloque), agenda `avisar_cliente(orden_id, cliente, patente)`: `await asyncio.sleep(0.5)` y `logger.info(...)` en el logger `taller.avisos`. Starlette ejecuta las tareas después de enviar el cuerpo de la respuesta. Un 403/404/409 sale por excepción antes de agendar: no hay aviso.
Para que el mensaje se vea en la consola de uvicorn (que no configura el logger raíz), el módulo le pone nivel INFO y un `StreamHandler` si no tiene ninguno (idempotente; `propagate` queda activo para que `caplog` lo vea en los tests).

### D12 — Tests
- Base `taller_test` con `sembrada` (seed, bcrypt costo 4) y `vaciar_al_terminar`.
- **Sesión real**: login por `POST /auth/login` con las contraseñas de `seed.CONTRASENAS` y la cookie en cada petición (CH-05 ya está en `main`; C-06 exige el 401/403 de verdad). Un helper `sesion(client, email)` devuelve las cookies.
- Conteo de consultas (C-15): fixture `sentencias` de `conftest.py`; se comparan las sentencias de `GET /ordenes/{id}` con una orden de 2 ítems y otra de 4 (creadas por `POST /ordenes`).
- Catálogo vacío: test de servicio sobre `tests/helpers.escenario(conexion, catalogo=False)` con un `OrdenesUnitOfWork` en una sesión ligada a esa conexión.
- Órdenes TERMINADA (para cancelar → 409) y con repuesto dado de baja: se insertan o actualizan con `tests/helpers.insertar` / SQL de prueba, no por la API de CH-07.
- Aviso "después de la respuesta": se llama a la app ASGI con un `send` que anota cada mensaje y un handler de logging que anota en la misma lista; el registro del aviso tiene que aparecer después del `http.response.body` final. `asyncio.sleep` se reemplaza por uno sin espera para no demorar la suite.
- Sin aviso en 409: `caplog` sin el mensaje.

### D13 — `.http`
Uno por caso en `test/`, con la respuesta esperada en un comentario y la nota "correr `python seed.py` antes". C-06 y C-13 usan dos sesiones (`# @name loginX` + `# @no-cookie-jar` + `Cookie: {{loginX.response.headers.Set-Cookie}}`). C-15 indica correr el servidor con `SQL_ECHO=true` y comparar la consola (la captura la saca CH-09).

## Risks / Trade-offs

- **CH-07 no mergea a tiempo o cambia la firma de D4** → todo lo demás ya está probado (D2); el grupo final se adapta en un único lugar. Si llega la noche del 29/10 sin CH-07, se coordina con Bruno para mergear primero su repositorio con el punto único (sin endpoints) y destrabar CH-08.
- **El punto único de CH-07 abre su propio UoW** → rompería RN-13. Se acuerda explícitamente con Bruno (D4) y la revisión del PR de CH-07 lo controla.
- **`FOR UPDATE` en las transiciones** → bloquea la fila de la orden durante la transacción (corta). Aceptado: evita historial duplicado.
- **Órdenes de vehículos dados de baja en `/mis-ordenes` y en el permiso del dueño** → decisión nuestra (la consigna no lo dice); se documenta en la bitácora.
- **`TotalExcedido` como 409** → la consigna no lo menciona; es la forma de no dar 500 con cantidades enormes (RN-18).
- **El logger del aviso con handler propio** → si CH-09 configura logging global, puede duplicar líneas; se revisa al consolidar.

## Migration Plan

Sin migraciones (CH-02 ya creó las tablas). Despliegue: mergear CH-07, rebasear `feat/ordenes` sobre `main`, completar el grupo bloqueado, PR con `Closes #8`. Rollback: revertir el merge (sólo agrega rutas y un módulo).

## Open Questions

- Nombre y ubicación finales del punto único de stock y de su excepción (D4): se cierran con Bruno; no cambian specs ni tareas.
- Texto exacto del mensaje del aviso en el registro (D11).
- (apply, grupo 8) Hasta que CH-07 esté en `main`, `terminar_orden` llega hasta las comprobaciones de permiso y estado y, si pasan, lanza `NotImplementedError` dentro del bloque (revierte) en vez de pasar la orden a TERMINADA sin descontar stock. El grupo 9 lo reemplaza por el descuento (D4).
- (apply, grupo 4) `TotalExcedido` usa el máximo de `NUMERIC(12,2)` (9 999 999 999.99); `OrdenNoEncontrada` también cubre, por el lado del servicio, un detalle releído que desapareció (no debería ocurrir).
