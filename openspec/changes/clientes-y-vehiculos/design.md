# Design

## Context

Motivación y alcance: ver `proposal.md`. Requisitos: `specs/clientes-y-vehiculos`.

Estado de `main` (27/10, commit `088185d`): están CH-01, CH-02, CH-03 (núcleo: `app/core/repository.py`, `unit_of_work.py`, `paginacion.py`) y CH-04 (autenticación, con `app/core/dependencies.py` y el `ClienteRepository` básico que creó Hernán para el registro). Ver D1.

Modelos de CH-02 que se usan (no se tocan): `Cliente` (UNIQUE `documento` → `uq_cliente_documento`), `Vehiculo` (índice parcial `uq_vehiculo_patente_vigente`, CHECK `ck_vehiculo_anio_rango`), `OrdenTrabajo` y `EstadoOrden` (para "órdenes abiertas"). Todas las relaciones tienen `lazy="raise"`.

Datos del seed que usan los tests y el `.http`: cliente 1 = Laura (usuario 6, vehículos 1 `AB123CD` y 2 `AC456EF`), cliente 2 = Jorge (sin usuario, vehículo 3 `AD789GH`); orden 1 PENDIENTE del vehículo 1; orden 2 EN_REPARACION del vehículo 3. El vehículo 2 no tiene órdenes.

## Goals / Non-Goals

**Goals:**
- Las cinco rutas de la tabla de la consigna con exactamente sus códigos (201/204/404/409/422, más 401/403 del grupo protegido).
- Unicidad de documento y patente garantizada por la base, sin consulta previa, con 409 y mensaje propio.
- Precarga declarada en el método del repositorio; ninguna carga perezosa.
- Que nada de lo que escribe este change dependa de cómo implementen Elías y Hernán el núcleo y la autenticación, más allá de las firmas acordadas.

**Non-Goals:**
- Autenticación, JWT, roles con vencimiento y el control del cambio obligatorio (CH-04/CH-05).
- Rechazar vehículos dados de baja al crear una orden: lo hace CH-08 con `VehiculoRepository.get_by_id`, que ya los excluye.
- Paginación (ninguna ruta de este change la pide).

## Decisions

### D1 — Qué se usa del núcleo (CH-03) y de la autenticación (CH-04)
Al arrancar, `main` todavía no tenía ni el núcleo ni las dependencias, así que el change se empezó con versiones mínimas propias en un commit aparte. Cuando se mergearon los PR #14 (CH-03) y #15/#16 (CH-04), ese commit se **descartó** al rebasear sobre `main`, y el change quedó usando sólo lo de Elías y Hernán:

| Pieza | Lo que usa CH-06 |
|---|---|
| `BaseRepository` (Elías) | `__init__(session, modelo)`, `self.session`, `_consulta_base()` como punto de partida de las lecturas, `get_by_id`, `add` |
| `SoftDeleteRepository` (Elías) | `get_by_id` que excluye los dados de baja, `soft_delete` |
| `UnitOfWork` (Elías) | `__init__(session)`, `async with uow:` |
| `ClienteRepository` (Hernán, DD-13) | se **extiende** sin cambiar su firma `ClienteRepository(session, model_cls=Cliente)` |
| `get_usuario_actual` (Hernán) | devuelve el `Usuario` (usa `.id`) o responde 401 |
| `requiere_rol(*roles)` (Hernán) | roles como texto (`"RECEPCION"`, `"ADMIN"`); depende de `get_usuario_actual`; 403 sin un rol vigente en la base |

CH-05 reemplaza las dependencias por la versión real sin cambiar las firmas, así que este módulo no se toca.

### D2 — `IntegrityError` → 409 por nombre de restricción, fuera del bloque del UoW
El servicio envuelve el `async with uow:` en un `try/except IntegrityError`. El UoW ya revirtió al salir con la excepción; recién ahí el servicio mira el nombre de la restricción que informa PostgreSQL (`exc.orig.__cause__.constraint_name`, aviso de Belén en la bitácora) y lanza `DocumentoDuplicado` (`uq_cliente_documento`) o `PatenteDuplicada` (`uq_vehiculo_patente_vigente`). Cualquier otra restricción se vuelve a lanzar (no se adivina). El router traduce los errores de dominio a `HTTPException` con mensaje propio.
- Se compara por **nombre de restricción**, nunca por el texto del error (depende del idioma del servidor).
- **Alternativa descartada**: atrapar el error dentro del `async with` (la sesión queda abortada y el UoW intentaría confirmar).

### D3 — 404 del cliente antes del INSERT del vehículo
`crear_vehiculo` busca el cliente con `get_by_id` y responde 404 si no existe; recién después inserta. No es una "consulta previa de unicidad" (eso sigue siendo de la base): sin ella, una patente repetida para un cliente inexistente daría 409, porque PostgreSQL verifica el índice único al insertar y la FK al final de la sentencia. La consigna pide 404 si el recurso de la ruta no existe.

### D4 — "Órdenes abiertas" con el catálogo, sin depender del módulo `ordenes`
`VehiculoRepository.tiene_ordenes_abiertas(id)` hace un `SELECT EXISTS` sobre `orden_trabajo JOIN estado_orden ON estado = codigo WHERE vehiculo_id = :id AND es_final IS false`. Usa los modelos de CH-02 (`app.modules.ordenes.models`), no repositorios de CH-08. Si mañana se agrega un estado no final al catálogo, la regla lo cubre sin tocar este código (RN-16).

### D5 — `GET /clientes/{id}`: precarga filtrada y orden fijo
`ClienteRepository.get_con_vehiculos_vigentes(id)` usa `selectinload(Cliente.vehiculos.and_(Vehiculo.borrado_en.is_(None)))`: dos consultas fijas, sin importar cuántos vehículos tenga. El servicio ordena los vehículos por `id` (el `selectinload` no garantiza orden).

### D6 — `GET /mis-vehiculos` devuelve una lista, no el envoltorio paginado
La tabla de la consigna no le da `page`/`size` ni 422 (a diferencia de `/mis-ordenes`), así que es una lista JSON de vehículos. Es una lectura con un `JOIN cliente` filtrado por `cliente.usuario_id = :usuario` y `borrado_en IS NULL`: un usuario nunca ve un vehículo ajeno (RN-17). Un usuario sin ficha de cliente recibe `[]`.

### D7 — Contratos (`schemas.py`)
- Entradas con `ConfigDict(extra="forbid")`. `ClienteCrear` no acepta `usuario_id` (el vínculo con un usuario lo crea sólo el auto-registro, RN-02).
- Textos con `strip_whitespace`, `min_length=1` y `max_length` (nombre 120, documento 20, teléfono 30, marca/modelo 60) y sin el carácter NUL (`\u0000`): PostgreSQL lo rechaza y terminaría en 500 (RN-18).
- Patente: se normaliza a mayúsculas sin espacios y debe quedar en 4..10 letras o dígitos; así `ab123cd` no esquiva el índice único de `AB123CD`.
- `anio`: `int` entre 1950 y 2100 (422 en el contrato; el CHECK de la base queda como segunda línea).
- Ids de ruta: `Path(ge=1, le=2_147_483_647)`. Sin el tope, un id que no entra en `INTEGER` hace fallar a asyncpg y da 500.
- Salidas: `ClienteLeer`, `ClienteConVehiculos`, `VehiculoLeer` (sin `borrado_en`).

### D8 — Errores con el cuerpo estándar de FastAPI
`HTTPException(status, detail="mensaje propio")` → `{"detail": "..."}`, el mismo formato que usan los 401/403 de las dependencias y los 422 de FastAPI. Mensajes: "Ya existe un cliente con ese documento", "Ya hay un vehículo vigente con esa patente", "Cliente no encontrado", "Vehículo no encontrado", "El vehículo tiene órdenes abiertas: no se puede dar de baja".

### D9 — Tests contra `taller_test` con el seed y la autorización real
- Datos: fixture `sembrada` de `conftest.py` (`seed.sembrar`, bcrypt costo 4) + `vaciar_al_terminar`.
- Sesión: se reemplaza **sólo** `get_usuario_actual` con `app.dependency_overrides`, eligiendo el usuario por un encabezado de test (`X-Usuario-Test: <id>`; sin encabezado → 401). `requiere_rol` queda el real: consulta `asignacion_rol` en la base, así que los 403 se prueban con los roles del seed y siguen valiendo cuando CH-05 reemplace las dependencias (`requiere_rol` depende de `get_usuario_actual`).
- El 401 sin cookie se prueba **sin** reemplazo, con la dependencia de verdad.
- "Órdenes abiertas/finales" se arman insertando órdenes directo en `taller_test` con `tests/helpers.insertar`.
- Precarga sin N+1: se cuentan las sentencias con un listener `before_cursor_execute` (2 consultas para el cliente, con 2 y con 5 vehículos).

### D10 — `tests/test_grupos_de_rutas.py`
El test de CH-01 exigía que el grupo protegido estuviera vacío y que las únicas rutas fueran las de salud ("hasta CH-04"). Con este change se relaja a: el grupo protegido **no tiene dependencias** (las agrega CH-05 una sola vez) y las rutas de salud siguen estando. Así cada change de la ola 2 agrega rutas sin pisarse en ese archivo. Las rutas de este change se verifican en `tests/test_clientes_rutas.py` (están en el grupo protegido y no en el abierto).

## Risks / Trade-offs

- **CH-05 cambia las dependencias** → mantiene las firmas (D1); los tests de este módulo corren contra la versión que esté en `main`.
- **`/mis-vehiculos` como lista** → si el profe espera el envoltorio, se cambia el `response_model` y el método del repositorio (D6). Se consulta en la clase del 27/10.
- **Normalizar la patente** (mayúsculas, sin espacios) es una decisión nuestra: la consigna no la pide, pero sin ella la unicidad se esquiva con minúsculas.
- **Carrera baja de vehículo vs. alta de orden** (dos peticiones a la vez) → concurrencia, fuera de alcance (cap. 7).

## Open Questions

- Confirmar en clase si `/mis-vehiculos` va con lista o con envoltorio (D6).
