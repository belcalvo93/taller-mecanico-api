# Design

## Context

Motivación y alcance: ver `proposal.md`. Requisitos: `specs/repuestos-y-stock/spec.md`.

Estado de `main`: están mergeados CH-01 (`infra-base`), CH-02 (`esquema-y-migraciones`), CH-03 (`nucleo-repositorios-uow`), CH-04 (`autenticacion`) y CH-06 (`clientes-y-vehiculos`).

Modelos de CH-02 en `app/modules/repuestos/models.py` (no se modifican):
- `Repuesto` (`repuesto`): `id`, `codigo`, `descripcion`, `precio` (`Numeric(10, 2)`), `stock` (`int`), `borrado_en`. Restricciones: `ck_repuesto_precio_positivo` (`precio > 0`), `ck_repuesto_stock_no_negativo` (`stock >= 0`), índice único parcial `uq_repuesto_codigo_vigente` sobre `(codigo) WHERE borrado_en IS NULL`. Relaciones `items`, `movimientos`, `historial_precios` con `lazy="raise"`.
- `MovimientoStock` (`movimiento_stock`, tabla de sólo agregado con trigger en migración 0002): `id`, `repuesto_id`, `orden_id` (`int | None`), `usuario_id`, `cantidad` (`ck_movimiento_stock_cantidad_no_cero`: `cantidad <> 0`), `motivo`, `cuando`.
- `HistorialPrecio` (`historial_precio_repuesto`, tabla de sólo agregado con trigger en migración 0002): `id`, `repuesto_id`, `usuario_id`, `precio_anterior`, `precio_nuevo` (`ck_historial_precio_repuesto_precio_nuevo_positivo`, `ck_historial_precio_repuesto_precio_distinto`), `cuando`.

Datos del seed (`seed.py`):
- Usuarios: `1` (`admin@example.com`, `ADMIN`), `3` (`recepcion@example.com`, `RECEPCION`), `4` (`mecanico@example.com`, `MECANICO`), `6` (`cliente@example.com`, `CLIENTE`).
- Repuestos:
  - `1`: `FIL-001` ("Filtro de aceite", `8500.00`, `stock: 10`), con 1 movimiento `"Stock inicial"` (`+10`) y 1 historial de precio (`8000.00` → `8500.00`).
  - `2`: `FRE-010` ("Pastillas de freno delanteras", `32000.00`, `stock: 4`), con 1 movimiento `"Stock inicial"` (`+4`).
  - `3`: `BUJ-100` ("Bujía de encendido", `6500.00`, `stock: 2`), con 1 movimiento `"Stock inicial"` (`+2`); figura en la orden 2 (`EN_REPARACION`, 4 unidades).
  - `4`: `ACE-530` ("Aceite 5W30 por litro", `12000.00`, `stock: 20`), con 1 movimiento `"Stock inicial"` (`+20`).

## Goals / Non-Goals

**Goals:**
- Implementar los 8 endpoints de repuestos en el grupo protegido respetando códigos HTTP (`200`, `201`, `204`, `401`, `403`, `404`, `409`, `422`).
- Garantizar que toda modificación de `repuesto.stock` ocurra a través de un único punto de escritura (`RN-14`, `DD-14`) reutilizable desde CH-08 (`ordenes`).
- Registrar el cambio de precio en `historial_precio_repuesto` dentro de la misma transacción del `PATCH /repuestos/{id}` sólo cuando el precio cambia (`RN-13`).
- Búsqueda por `descripcion` en `GET /repuestos?q=` con parámetros ligados y paginación común (`C-16`).

**Non-Goals:**
- Modificar `app/modules/repuestos/models.py` o las migraciones.
- Implementar el cierre de órdenes (`POST /ordenes/{id}/terminar`), que corresponde a CH-08.

## Decisions

### D1 — Punto único de escritura de stock (`RepuestoRepository.mover_stock`, RN-14 y DD-14)
Se define en `app/modules/repuestos/repository.py`:
```python
class RepuestoRepository(SoftDeleteRepository[Repuesto]):
    def __init__(self, session: AsyncSession) -> None: ...

    async def mover_stock(
        self,
        repuesto: Repuesto,
        cantidad: int,
        *,
        motivo: str,
        usuario_id: int,
        orden_id: int | None = None,
    ) -> MovimientoStock: ...
```
- **Por qué en el repositorio y no en un método del servicio que abra el UoW:** `mover_stock` NO hace `commit()` ni abre `async with uow`. La llama quien ya tiene una transacción abierta: `crear_repuesto`, `reponer_stock` y, en CH-08, `terminar_orden` con su propio UoW (`RN-13`, caso `C-11`). Si confirmara por su cuenta, cuando falta stock en el segundo ítem quedarían escrituras a medias. Por eso trabaja sobre la sesión que recibe el repositorio y sólo hace `flush()`.
- **Por qué recibe la instancia `repuesto` ya leída:** CH-07 la obtiene con `get_by_id` (sólo vigentes); CH-08 al terminar una orden la obtiene con `get_by_id_including_deleted`, porque un repuesto dado de baja después de agregarse a la orden igual descuenta stock (`DD-14`, `C-15`).
- **Signo de `cantidad`:** positiva suma, negativa descuenta.
- **Validaciones:**
  - `cantidad == 0` lanza `ValueError("La cantidad del movimiento no puede ser cero")`.
  - `repuesto.stock + cantidad < 0` lanza `StockInsuficiente(repuesto.codigo, repuesto.stock, abs(cantidad))` ANTES de tocar nada. `StockInsuficiente` se define en `repository.py` y CH-08 la importa de ahí. Si en cambio alguien deja pasar el descuento, falla `ck_repuesto_stock_no_negativo` (la restricción conserva su nombre; órdenes maneja ambos caminos).
- **Qué escribe:** actualiza `repuesto.stock`, lo agrega a la sesión, agrega el `MovimientoStock` (`repuesto_id`, `orden_id`, `usuario_id`, `cantidad`, `motivo`) y hace `flush()`. Devuelve el movimiento.
- **Bloqueo en `RepuestoRepository.update`:** se sobreescribe `update(entidad, cambios)` para que si `"stock"` está en `cambios` lance `ValueError("El stock sólo se modifica desde mover_stock (RN-14)")`. El stock no se edita por `PATCH`.

### D2 — Alta con `stock_inicial == 0` vs `stock_inicial > 0`
La tabla `movimiento_stock` tiene la restricción `ck_movimiento_stock_cantidad_no_cero` (`cantidad <> 0`). Por lo tanto:
- En `crear_repuesto`, el `Repuesto` se inserta inicialmente con `stock=0`.
- Si `datos.stock_inicial > 0`, en el mismo bloque `async with uow:` se llama a `uow.repuestos.mover_stock(repuesto, datos.stock_inicial, motivo="Stock inicial", usuario_id=usuario_id)`.
- Si `datos.stock_inicial == 0`, no se inserta fila en `movimiento_stock` y el repuesto queda con `stock=0`.

### D3 — Unicidad de `codigo` garantizada por la base (`uq_repuesto_codigo_vigente`)
Igual que en CH-06, `crear_repuesto` no hace un `SELECT` previo por código. Envuelve el `async with uow:` en `try/except IntegrityError` (fuera del bloque para que el UoW ya haya hecho `rollback()`), inspecciona `exc.orig.__cause__.constraint_name == "uq_repuesto_codigo_vigente"` y lanza `CodigoRepuestoDuplicado`, que el router traduce a `409 Conflict` con `{"detail": "Ya existe un repuesto vigente con ese código"}`.
El `codigo` se normaliza con `strip_whitespace=True` (sin forzar mayúsculas salvo limpieza de espacios extremos, respetando el código que envía el admin) y sin caracteres NUL (`\x00`).

### D4 — `PATCH /repuestos/{id}` e historial de precios en la misma transacción (`RN-13`)
- `RepuestoActualizar` declara `descripcion: _texto(200) | None = None` y `precio: Precio | None = None` con `extra="forbid"`.
- Para distinguir entre "campo no enviado" y "campo enviado como `null`", se usa `datos.model_dump(exclude_unset=True)` y un validador que rechaza `None` explícito en `descripcion` o `precio` (responde `422`).
- Si `"precio"` está en `cambios` y `cambios["precio"] != repuesto.precio`:
  - Se guarda `precio_anterior = repuesto.precio`.
  - Se actualiza el repuesto con `await uow.repuestos.update(repuesto, cambios)`.
  - Se inserta `HistorialPrecio(repuesto_id=repuesto.id, usuario_id=usuario_id, precio_anterior=precio_anterior, precio_nuevo=cambios["precio"])` con `await uow.historial_precios.add(...)` dentro del mismo `async with uow:`.
- Si `"precio"` no vino en `cambios`, o vino con el mismo valor numérico (ej. `Decimal("8500.00") == repuesto.precio`), no se inserta en `historial_precio_repuesto` (además la base tiene `ck_historial_precio_repuesto_precio_distinto`).

### D5 — Baja lógica de repuesto (`DELETE /repuestos/{id}`) nunca devuelve 409 (`DD-14`)
`dar_de_baja_repuesto` busca el repuesto vigente con `uow.repuestos.get_by_id(id)` (si es `None`, lanza `RepuestoNoEncontrado` → `404`) y llama a `await uow.repuestos.soft_delete(repuesto)` → `204 No Content`. No verifica si hay órdenes abiertas: según `DD-14` y `C-15`, un repuesto dado de baja no puede agregarse a órdenes nuevas ni elegirse en el catálogo, pero las órdenes que ya lo tenían pueden terminarse normalmente.

### D6 — Búsqueda en `GET /repuestos` con parámetros ligados (`C-16`)
`RepuestoRepository.listar(q: str | None, pagina: ParametrosPagina) -> Pagina[Repuesto]`:
- Parte de `self._consulta_base()` (que ya filtra `borrado_en IS NULL`).
- Si `q is not None` y `q.strip() != ""`: agrega `.where(col(Repuesto.descripcion).ilike(f"%{q.strip()}%"))`. SQLAlchemy pasa el patrón como parámetro ligado (`$1`), por lo que cualquier comilla como `' OR '1'='1` se trata como carácter literal de búsqueda y nunca altera la sintaxis SQL (`C-16`).
- Delega la paginación y el conteo en `await self._paginar(consulta, pagina)` (heredado de `BaseRepository`).

### D7 — Repositorios de tablas de sólo agregado (`RN-15`)
`MovimientoStockRepository` y `HistorialPrecioRepository` heredan de `BaseRepository` y agregan `listar_por_repuesto(repuesto_id: int)` ordenado por `id` ascendente. Sobreescriben `update` y `delete` lanzando `RuntimeError("Tabla de sólo agregado (RN-15)")` para que ni siquiera por error se intente modificar o borrar desde el repositorio, además del trigger de PostgreSQL.

### D8 — Contratos de entrada y salida (`schemas.py`)
- `Precio`: `Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]`.
- `RepuestoCrear`: `codigo: _texto(40)`, `descripcion: _texto(200)`, `precio: Precio`, `stock_inicial: Annotated[int, Field(ge=0, le=2_147_483_647)] = 0`.
- `RepuestoActualizar`: `descripcion` opcional, `precio` opcional, sin `codigo` ni `stock` (`extra="forbid"`).
- `ReposicionCrear`: `cantidad: Annotated[int, Field(gt=0, le=2_147_483_647)]`, `motivo: _texto(200) = "Reposición"`.
- Salidas (`from_attributes=True`, sin `borrado_en`):
  - `RepuestoLeer`: `id`, `codigo`, `descripcion`, `precio`, `stock`.
  - `MovimientoStockLeer`: `id`, `repuesto_id`, `orden_id`, `usuario_id`, `cantidad`, `motivo`, `cuando`.
  - `HistorialPrecioLeer`: `id`, `repuesto_id`, `usuario_id`, `precio_anterior`, `precio_nuevo`, `cuando`.

## Risks / Trade-offs

- **Serialización de `Decimal` en JSON:** FastAPI/Pydantic v2 serializa `Decimal("8500.00")` como `"8500.00"` en JSON y acepta tanto números como strings numéricos en la entrada (`9500`, `9500.00`, `"9500.00"`).
- **Coordinación con CH-08 (`ordenes`):** se expone `RepuestoRepository.mover_stock` y `StockInsuficiente` en `app.modules.repuestos.repository`. Órdenes la llama dentro de su propia transacción; CH-07 no abre ni confirma nada ahí. Si la firma cambia, hay que avisarle a Elías.
