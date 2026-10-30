# Proposal

> CH-08 `ordenes` · issue #8 · Responsable: Elías · Ola 3 · Governance: ALTO (máquina de estados y transacción multi-tabla que toca stock).

## Why

El taller todavía no puede registrar el trabajo que hace: no hay endpoints de órdenes de trabajo ni del catálogo de estados. Es el núcleo de negocio del TP y está en el camino crítico: cubre RN-10..RN-13 y RN-19, aporta la operación de varias escrituras más pesada del Ejercicio 6 (RN-13, 20 %) y todo el Ejercicio 8 (detalle sin N+1 y `BackgroundTasks`, 8 %), y es dueño de los casos C-06 (completo), C-10, C-11, C-12, C-13, C-15 y C-17, más la parte de C-01 de sus rutas `{id}`. CH-01..CH-06 ya están en `main` (modelos, núcleo, autenticación, autorización real, clientes y vehículos); CH-07 (`repuestos-y-stock`) todavía no.

## What Changes

- **Repositorios** (`app/modules/ordenes/repository.py`):
  - `EstadoOrdenRepository`: **sólo lectura, NO hereda de `BaseRepository`** (PK `codigo`); lista el catálogo por `posicion` y busca un estado por código.
  - `OrdenRepository(BaseRepository[OrdenTrabajo])`: detalle con carga anticipada declarada en el método (vehículo, cliente, ítems, repuesto de cada ítem, historial) en un número fijo de consultas; listado paginado con filtro `estado`; listado paginado de las órdenes de un usuario dueño; lectura con bloqueo para las transiciones.
  - `HistorialEstadoOrdenRepository(BaseRepository[HistorialEstadoOrden])`: sólo agrega (la tabla es de sólo agregado, RN-15).
- **`OrdenesUnitOfWork`**: los tres repositorios anteriores más `VehiculoRepository` (CH-06), `AsignacionRolRepository` (CH-05, roles vigentes para las decisiones del servicio) y el repositorio de repuestos con el **punto único de escritura de stock de CH-07**, todos con la misma sesión; dependencia `get_ordenes_uow`.
- **Contratos** (`schemas.py`): `EstadoOrdenCodigo` (enum que coincide con el catálogo), `OrdenCrear` / `ItemOrdenCrear` con `extra="forbid"` (sin precio, total, estado ni fecha; ≥ 1 ítem; sin repuestos repetidos), salidas `OrdenDetalle`, `OrdenResumen`, `EstadoOrdenLeer`.
- **Servicio** (`service.py`): crear (RN-10, RN-16, RN-19, un solo bloque), iniciar (RN-11), terminar (RN-11, RN-13, RN-14, un solo bloque), cancelar (RN-12, 403 antes que 409), detalle con control de dueño (RN-17), listados y catálogo. Errores de dominio que el router traduce a 403/404/409 con mensaje propio.
- **Endpoints** en el grupo protegido de `main.py`:
  - `POST /ordenes` → 201 / 409 / 422 — RECEPCION, ADMIN
  - `GET /ordenes` (`estado`, `page`, `size`) → 200 / 422 — RECEPCION, ADMIN, MECANICO
  - `GET /ordenes/{id}` → 200 / 403 / 404 — personal o dueño del vehículo
  - `POST /ordenes/{id}/iniciar` → 200 / 404 / 409 — sólo MECANICO (SU-03)
  - `POST /ordenes/{id}/terminar` → 200 / 403 / 404 / 409 — mecánico asignado o ADMIN; agenda el aviso con `BackgroundTasks`
  - `POST /ordenes/{id}/cancelar` → 200 / 403 / 404 / 409 — RECEPCION, ADMIN o el dueño (la ruta **no** lleva `requiere_rol`)
  - `GET /estados-orden` → 200 — autenticado
  - `GET /mis-ordenes` (`page`, `size`) → 200 / 422 — autenticado
- **Casos**: `.http` de C-06 (completo), C-10, C-11, C-12, C-13, C-15 y C-17 en `test/`, y tests pytest de cada escenario.

**Dependencia con CH-07**: terminar una orden descuenta stock por el punto único de escritura de stock que escribe CH-07 (DD-14, RN-14). CH-08 **no** escribe ese código: lo consume con la firma acordada en `design.md` (D4). Todo lo que no depende de él (catálogo, crear, listar, detalle, iniciar, cancelar, y los 403/404/409 de terminar que se deciden antes de tocar stock) se implementa y prueba primero; lo que depende de CH-07 queda aislado en el último grupo de `tasks.md`.

Fuera de alcance: el catálogo de repuestos, la reposición y la escritura de stock y movimientos (CH-07); modelos y migraciones (CH-02: no se tocan); endpoints de crear, editar o borrar estados (AP-02, no existen); la evidencia de consola de C-15 y la consolidación de los `.http` (CH-09).

## Capabilities

### New Capabilities
- `ordenes-de-trabajo`: alta de una orden con sus ítems y su ciclo de vida (iniciar, terminar, cancelar) con sus reglas de permiso, estado, stock e historial.
- `consulta-de-ordenes`: detalle de una orden sin N+1 con control de dueño, listado del personal filtrado por estado, listado propio paginado, y la separación 401/403 sobre estas rutas (C-06).
- `catalogo-estados-orden`: consulta de sólo lectura del catálogo de estados por posición y su correspondencia con el enum del contrato.

### Modified Capabilities
- (ninguna)

## Impact

- **Código nuevo**: `app/modules/ordenes/{repository,unit_of_work,schemas,service,router}.py`; `tests/test_ordenes_*.py`; `test/C-06_*.http`, `test/C-10_*.http`, `test/C-11_*.http`, `test/C-12_*.http`, `test/C-13_*.http`, `test/C-15_*.http`, `test/C-17_*.http`.
- **Código tocado**: `main.py` (import y la línea `include_router` de CH-08 en el grupo protegido); `docs/bitacora.md` (sección Elías). Opcional: una línea en `test/C-01_parametro_no_entero.http` con una ruta de órdenes.
- **Usa lo ya mergeado**: modelos de CH-02 (`app/modules/ordenes/models.py`, `repuestos/models.py`), núcleo de CH-03 (`BaseRepository`, `SoftDeleteRepository`, `UnitOfWork`, paginación), `get_usuario_actual` y `requiere_rol` reales (CH-04/CH-05), `AsignacionRolRepository.listar_roles_vigentes` (CH-05) y `VehiculoRepository.get_by_id` (CH-06, ya excluye los dados de baja).
- **Depende de CH-07** (no mergeado): `RepuestoRepository` y su punto único de escritura de stock. Bloquea sólo el último grupo de tareas (terminar con stock, C-11, C-12, aviso en segundo plano). Hay que coordinar con Bruno la firma de D4 antes de que mergee.
