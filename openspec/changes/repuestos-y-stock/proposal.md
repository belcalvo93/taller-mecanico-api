# Proposal

> CH-07 `repuestos-y-stock` · issue #7 · Responsable: Bruno · Ola 2 · Governance: ALTO (único punto de escritura del stock e historial de precios en la misma transacción).

## Why

El taller no puede administrar su catálogo de repuestos, reponer mercadería ni auditar los movimientos de stock y los cambios de precio. Además, CH-08 (`ordenes`) depende del punto único de escritura de stock de este módulo para descontar los repuestos al terminar una orden (`RN-14`, `DD-14`), y los casos de prueba `C-16` (búsqueda con comillas sin inyección SQL), `C-18` (cambio de precio e historial restringido a `ADMIN`) y parte de `C-15` (baja lógica de repuesto en orden abierta) requieren este change. Forma parte del Ejercicio 3 (contratos, CRUD y paginación, 10 %), Ejercicio 6 (repositorios y UoW, 20 %) y Ejercicio 4 (transacciones e historiales, 25 %).

## What Changes

- **`RepuestoRepository`** (hereda de `SoftDeleteRepository[Repuesto]`):
  - `listar(q, pagina)`: listado paginado de repuestos vigentes buscando en `descripcion` (sin distinguir mayúsculas) mediante parámetros ligados (`col(Repuesto.descripcion).ilike(...)`), nunca concatenando SQL (`C-16`).
  - `update(entidad, cambios)`: bloquea con `ValueError` cualquier intento de pasar `"stock"` en `cambios`, asegurando que el stock sólo se modifique desde el punto único de escritura (`RN-14`).
  - `mover_stock(repuesto, cantidad, *, motivo, usuario_id, orden_id=None)`: **punto único de escritura de stock** (`RN-14`, `DD-14`). Positiva suma, negativa descuenta; lanza `StockInsuficiente` si el stock quedaría negativo y `ValueError` si `cantidad == 0`. Actualiza `repuesto.stock`, agrega el `MovimientoStock` y hace `flush()`. NO hace `commit()` ni abre el UoW: lo llama quien ya tiene la transacción abierta (alta, reposición y, en CH-08, terminar orden).
- **`MovimientoStockRepository`** (hereda de `BaseRepository[MovimientoStock]`):
  - `listar_por_repuesto(repuesto_id)`: devuelve los movimientos del repuesto ordenados por `id` ascendente. No expone actualización ni borrado (tabla de sólo agregado en la base, `RN-15`).
- **`HistorialPrecioRepository`** (hereda de `BaseRepository[HistorialPrecio]`):
  - `listar_por_repuesto(repuesto_id)`: devuelve el historial de cambios de precio del repuesto ordenado por `id` ascendente. No expone actualización ni borrado (`RN-15`).
- **`RepuestosUnitOfWork`** con los tres repositorios (`repuestos`, `movimientos`, `historial_precios`) sobre la misma sesión, y la dependencia `get_repuestos_uow`.
- **Contratos** (`schemas.py`) separados de los modelos, con `extra="forbid"`: `RepuestoCrear`, `RepuestoActualizar` (`PATCH`, sin `codigo` ni `stock`), `ReposicionCrear`, `RepuestoLeer`, `MovimientoStockLeer` e `HistorialPrecioLeer`.
- **Servicio** (`service.py`):
  - Alta, reposición y consultas usan `uow.repuestos.mover_stock`; el servicio no escribe `repuesto.stock` por otro camino.
  - Alta de repuesto (`POST /repuestos`): crea el repuesto con `stock=0` y, si `stock_inicial > 0`, invoca `uow.repuestos.mover_stock` con `motivo="Stock inicial"` y `orden_id=None` en la misma transacción. Traduce `IntegrityError` de `uq_repuesto_codigo_vigente` a `CodigoRepuestoDuplicado` (409).
  - Edición parcial (`PATCH /repuestos/{id}`): actualiza `descripcion` y/o `precio`; sólo si `"precio"` fue enviado y es distinto del precio anterior, registra una fila en `historial_precio_repuesto` en la misma transacción (`RN-13`).
  - Baja lógica (`DELETE /repuestos/{id}`): marca `borrado_en` mediante `soft_delete` sin devolver 409 aunque el repuesto esté en órdenes abiertas (`DD-14`).
- **Endpoints** en el grupo protegido de `main.py`:
  - `GET /repuestos` → 200 paginado (`items, total, page, size, pages`) / 422 — `ADMIN`, `RECEPCION`, `MECANICO`
  - `GET /repuestos/{id}` → 200 / 404 — `ADMIN`, `RECEPCION`, `MECANICO`
  - `POST /repuestos` → 201 / 409 (código vigente repetido) / 422 — `ADMIN`
  - `PATCH /repuestos/{id}` → 200 / 404 / 422 — `ADMIN`
  - `DELETE /repuestos/{id}` → 204 / 404 — `ADMIN`
  - `POST /repuestos/{id}/reponer` → 200 / 404 / 422 — `ADMIN`
  - `GET /repuestos/{id}/movimientos` → 200 / 404 — `ADMIN`
  - `GET /repuestos/{id}/precios` → 200 / 404 — `ADMIN`
- **Archivos `.http`** en `test/`: `test/C-16_busqueda_con_comillas.http` y `test/C-18_historial_de_precios_y_permiso.http`, más la suite de tests pytest contra `taller_test`.

Fuera de alcance: modelos y migraciones (`app/modules/repuestos/models.py` ya existe de CH-02 y no se modifica); descuento de stock al terminar una orden (lo invoca CH-08 usando el punto único de escritura de este módulo).

## Capabilities

### New Capabilities
- `repuestos-y-stock`: catálogo de repuestos con búsqueda paginada, unicidad parcial de código vigente, baja lógica, punto único de escritura de stock con historial de movimientos e historial de cambios de precio en la misma transacción.

### Modified Capabilities
- (ninguna)

## Impact

- **Código nuevo**: `app/modules/repuestos/{repository,unit_of_work,schemas,service,router}.py`, `tests/test_repuestos_*.py`, `test/C-16_busqueda_con_comillas.http`, `test/C-18_historial_de_precios_y_permiso.http`.
- **Código tocado**: `main.py` (import de `repuestos_router` y `rutas_protegidas.include_router(repuestos_router)` en el lugar reservado para CH-07); `docs/bitacora.md` (sección Bruno).
- **Otros changes**: CH-08 (`ordenes`) usa `RepuestoRepository.mover_stock` y `StockInsuficiente` para descontar stock al terminar una orden (`DD-14`).
