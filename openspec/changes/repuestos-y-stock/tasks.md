# Tasks

> TDD estricto en cada tarea: **ROJO** (escribir primero el test, ejecutarlo y ver que falla por la razón esperada) → **VERDE** (código mínimo) → **TRIANGULAR** (otro caso con datos distintos) → **REFACTOR** (suite verde tras cada paso). Cada escenario de la spec tiene al menos un test.
> Tests en `tests/` contra `taller_test` (la fija `tests/conftest.py`). Comando: `python -m pytest` desde la raíz.
> Sin líneas de coautoría ni menciones a IA en los commits. El `.env` no se versiona.

## 0. Red de seguridad

- [x] 0.1 Verificar `.venv`, `.env` y base `taller_test`, correr la suite actual de `main` y anotar la línea base de tests pasando.

## 1. Repositorios y Unit of Work del módulo (`repository.py`, `unit_of_work.py`)

- [x] 1.1 ROJO→VERDE `RepuestoRepository(session)` hereda de `SoftDeleteRepository[Repuesto]`: `get_by_id` excluye dados de baja y `get_by_id_including_deleted` los incluye (`DD-14`); `update` rechaza `"stock"` con `ValueError` (`RN-14`).
- [x] 1.2 ROJO→VERDE `RepuestoRepository.listar(q, pagina)`: devuelve `Pagina[Repuesto]` de vigentes ordenados por `id`, filtra por `descripcion` sin distinguir mayúsculas, trata `' OR '1'='1` como literal con parámetros ligados (`C-16`) y lanza `PaginaInexistente` si `page > pages`.
- [x] 1.3 ROJO→VERDE `MovimientoStockRepository` y `HistorialPrecioRepository`: `listar_por_repuesto(repuesto_id)` ordenado por `id` ascendente; `update` y `delete` bloqueados (`RN-15`).
- [x] 1.4 ROJO→VERDE `RepuestoRepository.mover_stock(repuesto, cantidad, *, motivo, usuario_id, orden_id=None)`: suma o descuenta `repuesto.stock`, agrega el `MovimientoStock` y hace `flush()` sin `commit()`; lanza `StockInsuficiente` si `stock + cantidad < 0` sin dejar cambios y `ValueError` si `cantidad == 0`; si el bloque del UoW falla después, se revierte todo (`RN-14`, `DD-14`).
- [x] 1.5 ROJO→VERDE `RepuestosUnitOfWork(session)`: compone `repuestos`, `movimientos` e `historial_precios` compartiendo la misma sesión.
- [x] 1.6 Commit: `feat(repuestos-y-stock): repositorios y unit of work de repuestos`

## 2. Contratos (`schemas.py`)

- [x] 2.1 ROJO→VERDE `RepuestoCrear`: `extra="forbid"` (rechaza `stock` y `borrado_en`), textos sin espacios alrededor ni carácter NUL, `precio > 0`, `stock_inicial >= 0`.
- [x] 2.2 ROJO→VERDE `RepuestoActualizar` y `ReposicionCrear`: `extra="forbid"` (rechaza `stock` y `codigo` en `PATCH`), rechaza `null` explícito en `descripcion`/`precio`, `cantidad > 0` en reposición y `motivo` con valor por defecto `"Reposición"`.
- [x] 2.3 ROJO→VERDE Salidas `RepuestoLeer` (sin `borrado_en`), `MovimientoStockLeer` e `HistorialPrecioLeer`.
- [x] 2.4 Commit: `feat(repuestos-y-stock): contratos de entrada y salida`

## 3. Servicio (`service.py`)

- [x] 3.1 ROJO→VERDE `crear_repuesto`: con `stock_inicial > 0` usa `uow.repuestos.mover_stock` (`motivo="Stock inicial"`); con `stock_inicial == 0` deja `stock=0` sin fila en `movimiento_stock`; traduce `uq_repuesto_codigo_vigente` a `CodigoRepuestoDuplicado`.
- [x] 3.2 ROJO→VERDE `actualizar_repuesto`: si cambia `precio`, inserta en `historial_precio_repuesto` en la misma transacción; si sólo cambia `descripcion` o el precio es igual al actual, no inserta historial.
- [x] 3.3 ROJO→VERDE `dar_de_baja_repuesto` (soft delete sin 409 aunque esté en orden abierta), `reponer_stock` y consultas de detalle/movimientos/precios.

## 4. Rutas HTTP y montaje en `main.py` (`router.py`, `main.py`)

- [x] 4.1 ROJO→VERDE `GET /repuestos` y `GET /repuestos/{id}`: 200 paginado, búsqueda con `q` (`C-16`), 404 en inexistente o dado de baja, 422 en `page` fuera de rango o `id` inválido.
- [x] 4.2 ROJO→VERDE `POST /repuestos`: 201 con y sin `stock_inicial`, 409 en código vigente repetido, 201 al reutilizar el código de un repuesto dado de baja.
- [x] 4.3 ROJO→VERDE `PATCH /repuestos/{id}`, `DELETE /repuestos/{id}`, `POST /repuestos/{id}/reponer`, `GET /repuestos/{id}/movimientos` y `GET /repuestos/{id}/precios` (`C-18`).
- [x] 4.4 ROJO→VERDE Permisos: 401 sin cookie en las 8 rutas; `CLIENTE` → 403 en todas; `RECEPCION` y `MECANICO` → 200 en los 2 `GET` de catálogo y 403 en las 6 rutas de `ADMIN` (`C-18`).
- [x] 4.5 Montar `repuestos_router` en `main.py` dentro de `rutas_protegidas` y verificar que las 8 rutas estén en el grupo protegido.
- [x] 4.6 Commit: `feat(repuestos-y-stock): servicio y rutas HTTP`

## 5. Casos `.http` (`C-16` y `C-18`) y bitácora

- [ ] 5.1 Crear `test/C-16_busqueda_con_comillas.http` y `test/C-18_historial_de_precios_y_permiso.http` con los comentarios de resultado esperado.
- [ ] 5.2 Completar la sección de Bruno en `docs/bitacora.md`.
- [ ] 5.3 Correr la suite completa de `pytest` y verificar `git status` limpio.
- [ ] 5.4 Commit: `docs(repuestos-y-stock): casos C-16 y C-18 en .http y entrada en bitácora`
