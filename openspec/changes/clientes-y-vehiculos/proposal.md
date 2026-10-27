# Proposal

> CH-06 `clientes-y-vehiculos` · issue #6 · Responsable: Joaquín · Ola 2 · Governance: MEDIO (lógica de dominio con borrado lógico y unicidad parcial).

## Why

La recepción no puede registrar a quien trae un vehículo: no hay endpoints de clientes ni de vehículos. CH-08 (`ordenes`) necesita vehículos vigentes para abrir órdenes, y CH-04 (`autenticacion`) necesita `ClienteRepository` para el registro (RN-02, DD-13). Además el caso C-19 (baja de un vehículo y reuso de su patente) y parte de C-01 dependen de este change. Es parte del Ejercicio 3 (contratos y CRUD, 10 %) y aporta al Ejercicio 6 (repositorios y UoW, 20 %).

## What Changes

- **`ClienteRepository`** (hereda de `BaseRepository[Cliente]`, firma `ClienteRepository(session)`; DD-13): lo importa el UoW de `usuarios` para el registro. Extendido con `get_con_vehiculos_vigentes(id)` (precarga declarada en el método).
- **`VehiculoRepository`** (hereda de `SoftDeleteRepository[Vehiculo]`): `listar_vigentes_de_usuario(usuario_id)` y `tiene_ordenes_abiertas(vehiculo_id)` (estado no final según `estado_orden.es_final`, con los modelos de CH-02 y sin depender del módulo `ordenes`).
- **`ClientesUnitOfWork`** con los dos repositorios sobre la misma sesión, y la dependencia `get_clientes_uow` con la que el router lo construye.
- **Contratos** (`schemas.py`) separados de los modelos, con `extra="forbid"`.
- **Servicio** (`service.py`): abre el UoW con `async with`, aplica RN-01 (traduciendo el `IntegrityError` por nombre de restricción, sin consulta previa) y RN-16; lanza errores de dominio que el router traduce.
- **Endpoints** en el grupo protegido de `main.py`:
  - `POST /clientes` → 201 / 409 (documento repetido) / 422 — RECEPCION, ADMIN
  - `GET /clientes/{id}` → 200 con sus vehículos vigentes / 404 — RECEPCION, ADMIN
  - `POST /clientes/{id}/vehiculos` → 201 / 404 / 409 (patente vigente repetida) / 422 (`anio` fuera de 1950..2100) — RECEPCION, ADMIN
  - `DELETE /vehiculos/{id}` → 204 (borrado lógico) / 404 / 409 (órdenes abiertas) — RECEPCION, ADMIN
  - `GET /mis-vehiculos` → 200 con los vehículos vigentes del cliente vinculado al usuario (sólo pide autenticación, RN-17)
- **`.http` de C-19** en `test/` y tests pytest de cada escenario.

Fuera de alcance: autenticación y la versión real de `get_usuario_actual`/`requiere_rol` (CH-04/CH-05); el uso del vehículo en órdenes nuevas (lo valida CH-08 con `get_by_id`, que ya filtra los dados de baja); modelos y migraciones (CH-02: no se tocan).

## Capabilities

### New Capabilities
- `clientes-y-vehiculos`: alta y consulta de clientes, alta y baja lógica de vehículos con unicidad parcial de patente, y consulta de los vehículos propios.

### Modified Capabilities
- (ninguna)

## Impact

- **Código nuevo**: `app/modules/clientes/{repository,unit_of_work,schemas,service,router}.py`, `tests/test_clientes_*.py`, `test/C-19_baja_y_reuso_de_patente.http`.
- **Código tocado**: `main.py` (una línea de import y la línea `include_router` de CH-06 en el grupo protegido); `tests/test_grupos_de_rutas.py` (deja de exigir que el grupo protegido esté vacío; ver design D10); `docs/bitacora.md` (sección Joaquín).
- **Dependencias de otros changes que todavía no están en `main`** (ver design D1): núcleo de CH-03 (`app/core/repository.py`, `app/core/unit_of_work.py`) y la T1 de CH-04 (`app/core/dependencies.py`). Van en un commit separado y marcado como provisorio, para descartarlo cuando se mergeen los de Elías y Hernán.
- **Otros changes**: CH-04 importa `ClienteRepository(session)`; CH-08 usa `VehiculoRepository.get_by_id` (ya excluye los dados de baja) para no aceptar vehículos dados de baja en órdenes nuevas.
