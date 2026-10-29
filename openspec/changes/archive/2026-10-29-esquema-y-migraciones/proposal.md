# Proposal

> CH-02 `esquema-y-migraciones` · issue #2 · Responsable: Belén · Ola 1 · Governance: CRITICO (modelos que todo referencia + disparador de inmutabilidad; si `alembic upgrade head` falla sobre una base vacía, el profesor no corrige).

## Why

Hoy la base no tiene tablas: CH-01 dejó el motor, la configuración y la fixture `base_migrada`, pero la fixture se saltea porque no existen `alembic.ini` ni `migrations/`. Toda la ola 2 (CH-04 a CH-07) y la ola 3 (CH-08) necesitan los 13 modelos, el esquema creado por Alembic y los datos iniciales que usan los casos C-01..C-19. Además el Ejercicio 2 de la consigna (14 %) evalúa exactamente esto, y el Ejercicio 7 (10 %) el disparador de sólo agregado.

## What Changes

- **Los 13 modelos SQLModel** con los nombres de tablas y columnas exactos de la consigna, en el módulo que manda la consigna: `usuarios/models.py` (`Usuario`, `AsignacionRol`, `IntentoAcceso`, `EventoSeguridad`), `clientes/models.py` (`Cliente`, `Vehiculo`), `repuestos/models.py` (`Repuesto`, `MovimientoStock`, `HistorialPrecio`), `ordenes/models.py` (`EstadoOrden`, `OrdenTrabajo`, `ItemOrden`, `HistorialEstadoOrden`). Sólo modelos: nada de repositorios, UoW, servicios, routers ni contratos.
- **Restricciones en la base**: UNIQUE, CHECK, FK (los estados de la orden y del historial apuntan a `estado_orden.codigo`, nunca un CHECK con lista), los **tres índices únicos parciales** con `postgresql_where`, el índice `intento_acceso (email, ip, cuando)`, un índice por cada FK, `timestamptz` en todas las fechas y `NUMERIC`/`Decimal` en el dinero.
- **Navegación declarada en los dos extremos** de cada relación que se lee (`Usuario.cliente` devuelve un objeto), con la carga perezosa bloqueada.
- **Alembic con plantilla asincrónica** (`alembic init -t async migrations`): `alembic.ini` sin credenciales; `env.py` toma la URL de `get_settings()` (contrato ya fijado por CH-01).
- **Migración 1** generada con `--autogenerate`: todas las tablas, `estado_orden` vacía, índices parciales incluidos.
- **Migración 2** escrita a mano: función y disparador que rechazan `UPDATE` y `DELETE` sobre `historial_estado_orden`, `movimiento_stock` e `historial_precio_repuesto` (RN-15).
- Cada migración con el comentario de que se leyó antes de aplicarla; ciclo `upgrade head` → `downgrade base` → `upgrade head` probado contra `taller_test`.
- **`seed.py`**: vacía las tablas y carga los datos iniciales de la consigna (catálogo primero), con los datos que la consigna no fija propuestos en `design.md` para que Belén los apruebe. Calcula los hashes con `bcrypt` directamente (no depende de CH-04), con el costo de la configuración.
- **`test/solo_agregado.sql`** (caso C-14): los seis rechazos del disparador y el de la FK de estado inexistente, escrito y probado acá.
- Tests pytest en `tests/` que verifican todo lo anterior contra la base real `taller_test`.

Fuera de alcance: repositorios concretos, UoW, contratos, servicios y routers (CH-03 a CH-08); el enum de estados del contrato de la API (CH-08); la traducción de `IntegrityError` a 409 (cada change de módulo); la captura de psql de C-14 y el README (CH-09). Sin Docker, CI ni linter (DD-04).

## Capabilities

### New Capabilities
- `esquema-de-datos`: las 13 tablas con sus columnas, tipos, nulos, restricciones, índices (incluidos los tres parciales e índice por FK) y la navegación entre modelos.
- `migraciones`: cómo se crea y se deshace el esquema: Alembic asincrónico sin credenciales, migración 1 autogenerada, migración 2 escrita a mano, comentario de lectura previa y ciclo up/down/up.
- `solo-agregado`: la inmutabilidad de las tres tablas de historial impuesta por la base (RN-15) y el script `test/solo_agregado.sql` del caso C-14.
- `datos-iniciales`: el estado conocido que deja `seed.py` (catálogo, usuarios y roles, clientes, vehículos, repuestos y stock, órdenes, historiales y evento de seguridad), reproducible en cada corrida.

### Modified Capabilities
<!-- openspec/specs/ todavía está vacío: infra-base (CH-01) no está archivado. -->
- (ninguna)

## Impact

- **Código nuevo**: `app/modules/{usuarios,clientes,repuestos,ordenes}/models.py`, un módulo que importa los 13 modelos para Alembic y la app (ver design), `alembic.ini`, `migrations/` (`env.py`, `script.py.mako`, dos versiones), `seed.py`, `test/solo_agregado.sql`, tests en `tests/`.
- **Código tocado de CH-01**: `app/core/database.py` (convención de nombres de restricciones) y una línea de import en `main.py` para que los mapeos se configuren en la app; ningún contrato de CH-01 cambia. La fixture `base_migrada` de `tests/conftest.py` deja de saltearse.
- **Base de datos**: `alembic upgrade head` crea 13 tablas, la función y los tres disparadores; `downgrade base` las quita.
- **Otros changes**: todos los demás importan estos modelos y **no los modifican** (si necesitan una columna, se la piden a Belén). Los nombres de restricciones e índices quedan fijos para que CH-04/06/07 traduzcan el `IntegrityError` a 409. CH-03 debe probar su núcleo con un modelo de test sobre una `MetaData` propia (ver design). CH-08 escribe el enum de estados, que debe coincidir con el catálogo que carga `seed.py`.
- **Dependencias**: ninguna nueva (Alembic, SQLModel y bcrypt ya están en `requirements.txt`).
