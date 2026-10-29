# Design

## Context

Motivación y alcance: ver `proposal.md`. Requisitos: `specs/esquema-de-datos`, `specs/migraciones`, `specs/solo-agregado` y `specs/datos-iniciales`.

Estado actual (rama `feat/esquema-y-migraciones`, cortada de `feat/infra-base`, PR #12 todavía sin mergear):
- `app/core/config.py`: `Settings` + `get_settings()` con `lru_cache`; `DATABASE_URL` (`postgresql+asyncpg`) calculada con `URL.create`; `BCRYPT_COST` y `BCRYPT_MAX_CONCURRENT` en la configuración. El `.env` se lee **relativo al directorio actual**.
- `app/core/database.py`: `crear_motor`, `crear_fabrica_sesiones` (`AsyncSession` de SQLModel, `expire_on_commit=False`), `get_session`. Nada se crea al importar.
- `tests/conftest.py`: fija `POSTGRES_DB=taller_test` al importarse; `migrar_base_de_tests()` corre `alembic upgrade head` en un **subproceso** (para no anidar el `asyncio.run` del `env.py` async) y se saltea si no hay `alembic.ini`; fixture `base_migrada` (scope `session`). Contrato con CH-02: `env.py` toma la URL de `get_settings().DATABASE_URL`.
- No existen `alembic.ini`, `migrations/`, `seed.py` ni `test/solo_agregado.sql`; `app/modules/<mod>/` sólo tiene `__init__.py`.
- Entorno de Belén: Windows + Git Bash, Python 3.14, PostgreSQL 17, bases `taller` y `taller_test` (owner `taller`). Versiones instaladas: SQLAlchemy 2.1.6, SQLModel 0.0.48, Alembic 1.20.1, asyncpg 0.32, bcrypt 5.0 (lanza `ValueError` con más de 72 bytes), pytest-asyncio 1.4 con `asyncio_mode=auto` y loop por función.

## Goals / Non-Goals

**Goals:**
- Nombres de restricciones e índices **fijos y predecibles**, para que CH-04/06/07 traduzcan el `IntegrityError` a 409 por nombre de restricción y para que el `downgrade` sea limpio.
- Que la carga perezosa sea imposible por construcción (falla en el acto), no sólo por disciplina.
- Que los ids del seed sean deterministas (los `.http` de todos los changes usan `orden 2`, `vehiculo_id 2`, `repuesto_id 4`, `usuario_id 3`).
- Que toda la suite corra contra `taller_test` real y deje la base en `head`.

**Non-Goals:**
- Repositorios, UoW, contratos, servicios, routers y el enum de estados del contrato (CH-03 a CH-08).
- Permisos de base de datos para las tablas de sólo agregado (la consigna dice que no se pide).
- Bloquear `TRUNCATE` sobre las tablas de sólo agregado (ver D9).

## Decisions

### D1 — Un archivo `models.py` por módulo, sin `from __future__ import annotations`
- `usuarios/models.py`: `Usuario`, `AsignacionRol`, `IntentoAcceso`, `EventoSeguridad`; `clientes/models.py`: `Cliente`, `Vehiculo`; `repuestos/models.py`: `Repuesto`, `MovimientoStock`, `HistorialPrecio`; `ordenes/models.py`: `EstadoOrden`, `OrdenTrabajo`, `ItemOrden`, `HistorialEstadoOrden`.
- **`__tablename__` explícito en los 13** (SQLModel por defecto usaría `ordentrabajo`, `historialprecio`, etc.). `HistorialPrecio` → `historial_precio_repuesto`.
- Relaciones entre módulos con anotaciones en string (`"Cliente"`) e imports bajo `TYPE_CHECKING`; no se usa `from __future__ import annotations` (SQLModel no resuelve bien las relaciones con anotaciones diferidas).
- PK `id: int | None = Field(default=None, primary_key=True)` (SERIAL); `EstadoOrden.codigo: str = Field(primary_key=True)`.
- Todas las columnas NOT NULL salvo las que la consigna marca "nulo" (tipadas `X | None`).
- **Alternativa descartada**: un solo `app/models.py`. La consigna obliga a `app/modules/<módulo>/models.py`.

### D2 — Tipos: `timestamptz`, `Decimal` y textos
- Fechas: `Field(sa_type=DateTime(timezone=True))`; sin `timezone=True` SQLModel crea `timestamp without time zone`.
- Instantes que nacen con la fila (`cuando`, `creada_en`, `desde`): `default_factory=ahora_utc` (`datetime.now(timezone.utc)`, con microsegundos), **sin** `server_default`. Motivo: con `AsyncSession` y `expire_on_commit=False`, un valor generado por el servidor no queda en el objeto después del `flush` y leerlo dispararía una carga implícita (`MissingGreenlet`); con el default de Python el objeto ya tiene el valor. `ahora_utc` vive en `app/core/database.py` (ver D3). Alternativa descartada: `server_default=func.now()` + `eager_defaults`; además `now()` devuelve la misma hora para todas las filas de una transacción.
- Dinero: `Decimal` con `Field(max_digits=10, decimal_places=2)` (→ `NUMERIC(10,2)`); `total` con `max_digits=12`.
- Textos: `str` sin largo (SQLModel → `VARCHAR` sin límite en PostgreSQL). Los largos máximos son del contrato de cada change (422), no de la base.
- `intento_acceso.ip` es `str` (no `INET`): el router la toma de `request.client.host` y así no hay conversión de tipos en asyncpg. Se puede agregar validación en el contrato.
- Booleanos con default de Python: `activo=True`, `debe_cambiar_password=False`, `es_final=False`.

### D3 — Convención de nombres en `SQLModel.metadata`
En `app/core/database.py` (que ya importan todos los modelos para tomar `ahora_utc`, así la convención se fija **antes** de declarar cualquier tabla):

```python
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
SQLModel.metadata.naming_convention = NAMING_CONVENTION
```
Es configuración de metadatos, no un recurso: no viola la regla 7 (no conecta ni lee el entorno). Todos los nombres resultantes miden menos de 63 caracteres (el más largo: `fk_historial_estado_orden_desde_estado_estado_orden`, 50).

Nombres explícitos (CHECK requieren nombre con esta convención; los índices parciales se nombran a mano):

| Tabla | Restricción / índice | Nombre final |
|---|---|---|
| usuario | UNIQUE email | `uq_usuario_email` |
| asignacion_rol | CHECK rol | `ck_asignacion_rol_rol_valido` |
| asignacion_rol | índice único parcial | `uq_asignacion_rol_abierta` (`usuario_id, rol` WHERE `revocada_en IS NULL`) |
| intento_acceso | índice | `ix_intento_acceso_email_ip_cuando` |
| cliente | UNIQUE usuario_id / documento | `uq_cliente_usuario_id`, `uq_cliente_documento` |
| vehiculo | CHECK anio | `ck_vehiculo_anio_rango` |
| vehiculo | índice único parcial | `uq_vehiculo_patente_vigente` |
| repuesto | CHECK precio / stock | `ck_repuesto_precio_positivo`, `ck_repuesto_stock_no_negativo` |
| repuesto | índice único parcial | `uq_repuesto_codigo_vigente` |
| estado_orden | UNIQUE posicion | `uq_estado_orden_posicion` |
| orden_trabajo | CHECK total | `ck_orden_trabajo_total_no_negativo` |
| orden_trabajo | FK estado | `fk_orden_trabajo_estado_estado_orden` |
| item_orden | UNIQUE (orden_id, repuesto_id) | `uq_item_orden_orden_id_repuesto_id` |
| item_orden | CHECK cantidad / precio | `ck_item_orden_cantidad_positiva`, `ck_item_orden_precio_unitario_positivo` |
| movimiento_stock | CHECK cantidad | `ck_movimiento_stock_cantidad_no_cero` |
| historial_precio_repuesto | CHECK | `ck_historial_precio_repuesto_precio_nuevo_positivo`, `ck_historial_precio_repuesto_precio_distinto` |

Los índices parciales van en `__table_args__` con `Index(nombre, *cols, unique=True, postgresql_where=text("borrado_en IS NULL"))`. Esta tabla es el **contrato para la traducción a 409** de los demás changes.
- **Alternativa descartada**: dejar que PostgreSQL ponga los nombres (`usuario_email_key`, `vehiculo_anio_check`). Son deterministas pero los de CHECK y FK quedarían sin nombre en la migración y Alembic no podría referenciarlos.

### D4 — Claves foráneas e índices
- Todas las FK con `index=True` (índice `ix_<tabla>_<columna>`), salvo `cliente.usuario_id`, que ya queda cubierta por su UNIQUE. `item_orden.orden_id` lleva su índice propio aunque el UNIQUE compuesto empiece por ella (redundante pero explícito; el test verifica "un índice cuya primera columna es la FK").
- FK: `asignacion_rol.usuario_id`, `asignacion_rol.otorgada_por` (nulo), `cliente.usuario_id` (nulo), `orden_trabajo.mecanico_id` (nulo), `historial_estado_orden.usuario_id`, `movimiento_stock.usuario_id`, `historial_precio_repuesto.usuario_id` → `usuario.id`; `vehiculo.cliente_id` → `cliente.id`; `orden_trabajo.vehiculo_id` → `vehiculo.id`; `item_orden.orden_id`, `historial_estado_orden.orden_id`, `movimiento_stock.orden_id` (nulo) → `orden_trabajo.id`; `item_orden.repuesto_id`, `movimiento_stock.repuesto_id`, `historial_precio_repuesto.repuesto_id` → `repuesto.id`; `orden_trabajo.estado`, `historial_estado_orden.desde_estado` (nulo), `hasta_estado` → `estado_orden.codigo`.
- **`otorgada_por` como FK a `usuario.id`** es una decisión nuestra: la consigna no lo dice. NULL = otorgada por el sistema (seed). Ver "Datos a aprobar".
- Sin `ON DELETE CASCADE` en ninguna FK: vehículo y repuesto se dan de baja lógicamente, las órdenes no se borran y un `DELETE` en cascada sobre tablas de sólo agregado chocaría con el disparador.

### D5 — Relaciones: dos extremos y `lazy="raise"`
Todas con `sa_relationship_kwargs={"lazy": "raise"}`: acceder a una relación no precargada lanza `InvalidRequestError` en el acto, sin consultar (regla "carga perezosa prohibida"). Los repositorios precargan con `selectinload`/`joinedload`, que pisan el `lazy` de la relación.

| Extremo A | Extremo B | Notas |
|---|---|---|
| `Usuario.asignaciones: list[AsignacionRol]` | `AsignacionRol.usuario` | `foreign_keys=[AsignacionRol.usuario_id]` (hay dos FK a usuario) |
| `Usuario.cliente: Cliente \| None` | `Cliente.usuario` | `uselist=False`: devuelve objeto, no lista |
| `Cliente.vehiculos` | `Vehiculo.cliente` | |
| `Vehiculo.ordenes` | `OrdenTrabajo.vehiculo` | |
| `Usuario.ordenes_asignadas` | `OrdenTrabajo.mecanico` | |
| `OrdenTrabajo.items` | `ItemOrden.orden` | composición: `cascade="all, delete-orphan"` |
| `Repuesto.items` | `ItemOrden.repuesto` | |
| `OrdenTrabajo.historial` | `HistorialEstadoOrden.orden` | `order_by` id; sin cascada de borrado |
| `Repuesto.movimientos` | `MovimientoStock.repuesto` | |
| `Repuesto.historial_precios` | `HistorialPrecio.repuesto` | |
| `EstadoOrden.ordenes` | `OrdenTrabajo.estado_orden` | la columna se llama `estado`, por eso la relación es `estado_orden` |

Sin relación (sólo la columna FK): `AsignacionRol.otorgada_por`, los `usuario_id` de historial/movimiento/precio, `MovimientoStock.orden_id` y los dos estados del historial (el código ya es el dato que se muestra). Si un change necesita leer alguna, se la pide a Belén.
- **Trade-off de `lazy="raise"`**: `orden.items.append(...)` sobre una orden persistente sin `items` cargados también falla; CH-08 crea los ítems junto con la orden nueva (pendiente, sin ese problema) o con `orden_id`. Alternativa descartada: `lazy="raise_on_sql"` (deja pasar accesos resueltos por el identity map; menos estricto y más difícil de explicar en la demo).

### D6 — Registro de modelos: `app/modules/modelos.py`
Las relaciones entre módulos se resuelven por nombre al configurar los mapeos; si sólo se importó `usuarios.models`, la primera consulta falla porque no conoce `"Cliente"`. Se agrega un módulo que importa los cuatro `models.py` (y reexporta las 13 clases). Lo importan `migrations/env.py` (para `target_metadata`), `seed.py`, los tests y `main.py` (una línea, para que la app tenga los 13 mapeos aunque todavía no haya routers).
- **Alternativa descartada**: repetir los cuatro imports en cada lugar (se olvida uno y aparece un error de mapeo lejos de la causa). Otra descartada: ponerlo en `app/modules/__init__.py` (se ejecutaría al importar cualquier módulo, incluso `health`). **Ver "Datos a aprobar"**: la ubicación es un archivo extra que la consigna no lista.

### D7 — Alembic asincrónico sin credenciales
- `alembic init -t async migrations` (CH-01 no creó `migrations/` justamente por esto).
- `alembic.ini`: se **borra** la línea `sqlalchemy.url` de la plantilla; `script_location = %(here)s/migrations`; `file_template = %%(rev)s_%%(slug)s`. Las revisiones se generan con `--rev-id 0001` y `0002` → `0001_esquema_inicial.py`, `0002_solo_agregado.py` (fáciles de citar en la demo).
- `env.py`: `import app.modules.modelos`; `target_metadata = SQLModel.metadata`. Modo online: `create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)` en lugar de `async_engine_from_config`. Modo offline: `context.configure(url=get_settings().DATABASE_URL, ...)`. **No** se usa `config.set_main_option("sqlalchemy.url", ...)`: `ConfigParser` interpreta `%`, y una contraseña con `%` rompería la migración (además, así la URL nunca pasa por la configuración de Alembic).
- `script.py.mako`: se agrega `import sqlmodel` a la plantilla, porque autogenerate escribe `sqlmodel.sql.sqltypes.AutoString()` en las columnas `str` y sin ese import la migración falla con `NameError`.
- Alembic se ejecuta **desde la raíz del repo** (el `.env` se lee relativo al directorio actual); queda anotado para el README de CH-09.

### D8 — Migración 1 (autogenerate) y comentario de lectura previa
- Se genera con `POSTGRES_DB=taller_test alembic revision --autogenerate -m "esquema inicial" --rev-id 0001` contra `taller_test` vacía.
- Alembic 1.20 incluye los índices parciales con `postgresql_where=sa.text(...)` y ordena las tablas por dependencia; igual **Belén la lee entera antes de aplicarla** (checkpoint): tablas, nulos, tipos (`DateTime(timezone=True)`, `Numeric(10, 2)`), CHECKs, índices y el `downgrade`. Si autogenerate omite o deforma algo, se corrige a mano y se anota en el comentario.
- Comentario al principio del archivo, escrito por Belén **después** de leerla: `# Leída antes de aplicarla por Belén Calvo el <fecha>. Correcciones a mano: <ninguna | lista>.` Un test verifica la presencia de la frase "Leída antes de aplicarla" en cada versión (no puede verificar que se haya leído: eso lo garantiza el checkpoint).
- `alembic check` (desde 1.9) compara modelos contra la base en `head`; se usa como test de que la migración 1 y los modelos coinciden.

### D9 — Migración 2 (a mano): disparador por sentencia
```sql
CREATE FUNCTION rechazar_cambio_solo_agregado() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'La tabla % es de sólo agregado: no se permite %', TG_TABLE_NAME, TG_OP;
END $$;
CREATE TRIGGER trg_<tabla>_solo_agregado BEFORE UPDATE OR DELETE ON <tabla>
  FOR EACH STATEMENT EXECUTE FUNCTION rechazar_cambio_solo_agregado();
```
para `historial_estado_orden`, `movimiento_stock` e `historial_precio_repuesto`, con `op.execute(...)`. `downgrade`: `DROP TRIGGER IF EXISTS` de los tres y `DROP FUNCTION IF EXISTS`.
- **`FOR EACH STATEMENT` en lugar de `FOR EACH ROW`**: rechaza también un `UPDATE`/`DELETE` que no toca filas, así el rechazo no depende de que haya datos y los tests corren sobre tablas vacías. Alternativa: `FOR EACH ROW` (más habitual en los apuntes; sólo dispara si hay filas). Ver "Datos a aprobar".
- SQLSTATE: el de `RAISE EXCEPTION` por defecto (`P0001`). Ningún camino de la API hace `UPDATE`/`DELETE` sobre esas tablas, así que nunca se traduce a HTTP; si un change lo provoca, es un bug que tiene que verse.
- **`TRUNCATE` no queda bloqueado**: la consigna pide rechazar `UPDATE` y `DELETE`, y `seed.py` necesita vaciar las tablas. Bloquearlo obligaría al seed a desactivar disparadores (requiere ser dueño de la tabla y es peor para la demo).

### D10 — `seed.py`
- Estructura: `async def sembrar(engine, settings) -> None` y `async def main()` que crea el motor con `crear_motor(get_settings())`, llama a `sembrar` y hace `dispose()`; `if __name__ == "__main__": asyncio.run(main())`. Nada se crea al importar: los tests llaman a `sembrar` con su propio motor contra `taller_test`.
- **Hashes primero, fuera de la transacción**: `asyncio.gather` de `asyncio.to_thread(bcrypt.hashpw, pwd.encode(), bcrypt.gensalt(rounds=settings.BCRYPT_COST))` bajo un `asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENT)`; recién después se abre la sesión. Aunque es un script, se respeta la regla 9 tal cual. No importa nada de `app/core/security.py` (CH-04).
- **Una sola transacción** (`async with AsyncSession(engine) as s, s.begin():`): `TRUNCATE` de las 13 tablas con `RESTART IDENTITY CASCADE` (en PostgreSQL `TRUNCATE` es transaccional: si algo falla después, se revierte todo) y la carga en este orden, con `flush()` entre grupos para que los ids salgan en orden: catálogo → usuarios → asignaciones → clientes → vehículos → repuestos → movimientos "Stock inicial" → historial de precio → órdenes → ítems → historial de estados → evento de seguridad.
- No se fijan ids a mano: `RESTART IDENTITY` hace que empiecen en 1 y las secuencias quedan sincronizadas (la próxima orden de la API es la 3, como en el ejemplo de la consigna).
- Totales y precios unitarios se calculan en el seed a partir de los datos (`precio_unitario = repuesto.precio`, `total = Σ cantidad × precio`), no se escriben a mano.
- Las contraseñas de prueba son constantes de `seed.py` (diccionario correo → contraseña) y **sólo** viven ahí; los tests las importan de `seed`.
- Usa `session.begin()` y no un `UnitOfWork`: `seed.py` es una herramienta de puesta en marcha fuera de las capas (y el UoW de CH-03 se escribe en paralelo). Ver inconsistencias.

### D11 — `test/solo_agregado.sql`
- Encabezado: cómo correrlo (`python seed.py` y después `psql -U taller -d taller -f test/solo_agregado.sql`), `\set ON_ERROR_STOP off` para que muestre los siete errores, y cada sentencia precedida de `-- Esperado: ERROR: La tabla ... es de sólo agregado: no se permite UPDATE`.
- Sentencias sobre filas que el seed garantiza (`id = 1`): `UPDATE`/`DELETE` de `historial_estado_orden`, `movimiento_stock`, `historial_precio_repuesto`, y `UPDATE orden_trabajo SET estado = 'DEMORADA' WHERE id = 1;` (rechazo por `fk_orden_trabajo_estado_estado_orden`).
- Sin `BEGIN`/`COMMIT`: en psql cada sentencia es su propia transacción (autocommit) y un error no arrastra a las siguientes.

### D12 — Estrategia de tests (todo en `tests/`, contra `taller_test`)
- Archivos: `test_modelos.py` (sin base: tablas, columnas, tipos Python, nulos, nombres de restricciones en `SQLModel.metadata`, relaciones y `uselist`), `test_esquema.py` (con base: `information_schema` y `pg_catalog`, CHECK/UNIQUE/FK/índices parciales), `test_migraciones.py` (subprocesos de Alembic), `test_solo_agregado.py`, `test_seed.py`.
- Fixture `motor` (por función, para no cruzar bucles de eventos de pytest-asyncio) creada con `crear_motor(get_settings())` y `dispose()` al final; depende de `base_migrada`.
- Fixture `conexion`: abre una transacción y la **revierte** al final, así los tests de restricciones no dejan datos. Cada inserción que se espera que falle va dentro de un `begin_nested()` (SAVEPOINT), porque un error aborta la transacción entera. El test compara `exc.orig.__cause__.constraint_name` (asyncpg) con el nombre de la tabla de D3.
- Ciclo up/down/up y `alembic check` en subprocesos (mismo motivo que CH-01: el `env.py` hace `asyncio.run`), con `timeout`. Esos tests no deben tener conexiones abiertas: un `DROP TABLE` espera el lock de una transacción abierta. Terminan siempre en `head`.
- Tests del seed: `BCRYPT_COST=4` por `monkeypatch` (velocidad) y triangulación con 5; captura del orden de inserciones con un listener `before_cursor_execute` sobre `motor.sync_engine`. Dejan `taller_test` sembrada (con commit), lo que es inocuo para el resto.
- `solo_agregado.sql` se prueba leyendo el archivo, separando las siete sentencias (ignorando comentarios y metacomandos `\`) y ejecutando cada una en su propia transacción sobre `taller_test` recién sembrada: las seis primeras deben fallar con el mensaje de sólo agregado y la séptima con la FK. La captura de psql es de CH-09.
- Test de "nadie usa `create_all`": busca `create_all` en `app/`, `main.py`, `seed.py`, `migrations/` y `SQLModel.metadata.create_all` en `tests/`.
- Suite completa (`pytest` desde la raíz) en verde antes de cada checkpoint.

### D13 — Coordinación con CH-03 (Elías)
CH-03 prueba su núcleo con un modelo mínimo de test. Para no ensuciar el esquema real ni `alembic check`: ese modelo debe declararse sobre una **`MetaData` propia** (no `SQLModel.metadata`) y crear su tabla efímera con esa metadata (o `CREATE TEMP TABLE`) dentro del test. Se le avisa en la revisión del PR; no lo implementa este change.

## Datos a aprobar por Belén

> La consigna no fija estos valores (DD-16). Son propuestas: **Belén los aprueba o los cambia en el checkpoint de la tarea del seed**. Los valores marcados "fijo" salen de la consigna o de sus ejemplos y no se tocan.

### Usuarios (contraseñas de prueba: sólo en `seed.py`, no son secretos reales)

| id | email | nombre | rol | contraseña de prueba | debe_cambiar_password |
|---|---|---|---|---|---|
| 1 | admin@example.com (fijo) | Ana Administradora | ADMIN | `Admin.2026` | no |
| 2 | admin2@example.com (fijo) | Andrés Administrador | ADMIN | `Admin2.2026` | no |
| 3 | recepcion@example.com (fijo) | Rita Recepción | RECEPCION | `Recepcion.2026` | no |
| 4 | mecanico@example.com (fijo) | Mario Mecánico | MECANICO | `Mecanico.2026` | no |
| 5 | mecanico2@example.com (fijo) | Marta Mecánica | MECANICO | `Mecanico2.2026` | no |
| 6 | cliente@example.com (fijo) | Laura Cliente | CLIENTE | `Cliente.2026` | no |
| 7 | nuevo@example.com (fijo) | Nicolás Nuevo | MECANICO | `Provisoria.2026` | **sí** (fijo) |

- Todos `activo = true`, `password_cambiada_en = NULL`. Asignaciones: `desde = ahora`, `vence_en`, `revocada_en` y `otorgada_por` en NULL (las otorga el sistema).
- El id 3 = recepción coincide con el `usuario_id: 3` del historial en la respuesta de ejemplo de `POST /ordenes`.
- Las contraseñas tienen entre 10 y 15 bytes ASCII (muy por debajo de 72). Van a aparecer también en los cuerpos de login de los `.http` (inevitable).

### Clientes y vehículos

| id | cliente | usuario | documento | teléfono |
|---|---|---|---|---|
| 1 | Laura Cliente (fijo por el ejemplo de la consigna) | cliente@example.com (6) | `30111222` | `11 4000-1111` |
| 2 | Jorge Gómez | — (fijo: sin usuario) | `25333444` | `11 4000-2222` |

| id | cliente | patente | marca | modelo | año |
|---|---|---|---|---|---|
| 1 | Laura | `AB123CD` | Volkswagen | Gol Trend | 2015 |
| 2 | Laura | `AC456EF` (fijo por el ejemplo) | Toyota | Etios | 2019 |
| 3 | Jorge | `AD789GH` | Ford | Fiesta | 2012 |

- El vehículo 2 queda **sin órdenes**: sirve para C-19 (darlo de baja con 204 y volver a registrar `AC456EF` para Jorge con 201) y para el ejemplo de C-10 (orden nueva del vehículo 2 → id 3).

### Repuestos

| id | código | descripción | precio | stock |
|---|---|---|---|---|
| 1 | `FIL-001` (fijo) | Filtro de aceite (fijo) | 8500.00 (fijo) | 10 (fijo) |
| 2 | `FRE-010` (fijo) | Pastillas de freno delanteras (fijo) | 32000.00 (fijo) | 4 (fijo) |
| 3 | `BUJ-100` | Bujía de encendido | **6500.00** | 2 (fijo) |
| 4 | `ACE-530` (fijo) | Aceite 5W30 por litro (fijo) | 12000.00 (fijo) | 20 (fijo) |

- La descripción de la bujía **no** contiene "freno": C-16 espera `q=freno` → total 1.
- Movimientos: uno por repuesto, `motivo = "Stock inicial"`, `cantidad = stock`, `orden_id = NULL`, `usuario_id = 1` (admin).
- Historial de precio: `FIL-001`, 8000.00 → 8500.00 (fijo), `usuario_id = 1`.

### Órdenes

| id | vehículo | estado | mecánico | falla | ítems | total |
|---|---|---|---|---|---|---|
| 1 | 1 (Laura, fijo) | PENDIENTE (fijo) | — | Service de 60.000 km: cambio de aceite y filtro | 1 × `FIL-001` (8500.00) + 4 × `ACE-530` (12000.00) | 56500.00 |
| 2 | 3 (Jorge, fijo) | EN_REPARACION (fijo) | 4 mecanico@ (fijo) | Falla de encendido: el motor ratea en frío | 4 × `BUJ-100` (6500.00) (fijo: 4 cuando hay 2) | 26000.00 |

- Historial de estados: orden 1 → (NULL → PENDIENTE, usuario 3); orden 2 → (NULL → PENDIENTE, usuario 3) y (PENDIENTE → EN_REPARACION, usuario 4).
- La orden 1 es de Laura y está PENDIENTE: sirve para C-06 (el cliente ve la suya, 200; la 2 es ajena, 403) y C-13 (el dueño cancela su orden pendiente).

### Catálogo (códigos, posiciones y finales fijos; descripciones propuestas)

| codigo | posicion | es_final | descripcion |
|---|---|---|---|
| PENDIENTE | 1 | no | Ingresada, a la espera de un mecánico |
| EN_REPARACION | 2 | no | Un mecánico la está reparando |
| TERMINADA | 3 | sí | Reparación terminada |
| CANCELADA | 4 | sí | Cancelada antes de empezar la reparación |

### Evento de seguridad (fijo)
`actor = "SISTEMA"`, `accion = "Carga de los datos iniciales"`.

### Decisiones de diseño que también necesitan el OK de Belén
1. `asignacion_rol.otorgada_por` como FK a `usuario.id` (D4).
2. Disparador `FOR EACH STATEMENT` (D9) en lugar de `FOR EACH ROW`.
3. `TRUNCATE` permitido sobre las tablas de sólo agregado (D9).
4. Archivo extra `app/modules/modelos.py` como registro de modelos (D6) y la línea de import en `main.py`.
5. `intento_acceso.ip` como texto (D2).
6. Revisiones con id `0001`/`0002` (D7).

## Inconsistencias encontradas (manda la consigna)

- **Contraseñas del seed y `env.example`**: el pedido de este change mencionaba que vivirían en "seed.py / env.example"; la consigna dice "Las contraseñas son de mentira y viven sólo en ese archivo" (seed.py). Se dejan **sólo en `seed.py`**; `env.example` no cambia.
- **"Sólo el UoW hace commit" (regla 14) y "el stock se escribe en un único punto" (RN-14, regla 14)** frente a `seed.py`: la consigna define a `seed.py` como herramienta de puesta en marcha que "vacía las tablas y carga" datos, fuera de las capas. Se interpreta que esas reglas valen para la aplicación; el seed usa su propia transacción y escribe el stock junto con su movimiento "Stock inicial". Si Belén prefiere, cuando CH-03 mergee se puede pasar el seed a un UoW (no cambia los datos).
- **Regla 9 (bcrypt con `to_thread` + semáforo)** está pensada para los handlers; el seed la cumple igual (D10) para no abrir una excepción que haya que explicar.
- **`otorgada_por`**: la consigna no dice que sea FK; la KB (`04_modelo_de_datos.md`) lo deja condicional ("si es FK a usuario"). Decisión D4, a aprobar.
- **Nombres de clase vs. tabla**: la consigna llama a la entidad `HistorialPrecio` y a la tabla `historial_precio_repuesto`; se respetan los dos (`__tablename__` explícito).
- **US-023 (KB) pone `test/solo_agregado.sql` en CH-09**; `CHANGES.md` lo asigna a CH-02 (escribir y probar) y a CH-09 sólo la captura. Se sigue `CHANGES.md`, que es más específico y no contradice la consigna.
- **Pregunta abierta de CH-01** ("¿`base_migrada` hace `downgrade base` + `upgrade head` por sesión?"): se resuelve que **no**; sigue haciendo sólo `upgrade head` y el ciclo se prueba en un test propio (D12).
- **Spec de CH-01 `entorno-de-pruebas`** dice que la fixture se saltea "antes de CH-02": con este change deja de saltearse, que es el comportamiento que esa misma spec prevé ("Esquema desde las migraciones"). No hace falta modificarla.

## Risks / Trade-offs

- [autogenerate omite o deforma algo (por ejemplo `postgresql_where`, un `CHECK` o el tipo con zona)] → checkpoint de lectura de la migración 1 + tests de esquema contra la base real + `alembic check`.
- [`alembic check` reporta diferencias falsas (expresiones de índices parciales o tipos `AutoString` vs `VARCHAR`)] → si pasa, se documenta en la bitácora y se ajusta la comparación en `env.py` (`include_object`/`compare_type`) sin tocar la migración; el test de esquema sigue verificando lo esencial.
- [Ciclo down/up bloqueado por una conexión abierta del propio pytest] → los tests de ciclo no usan fixtures de conexión, corren en subproceso con `timeout` y los motores de los otros tests son por función y se cierran con `dispose()`.
- [`lazy="raise"` incomoda a los changes de la ola 2] → es exactamente la regla de la consigna; se documenta en el PR con un ejemplo de `selectinload`.
- [Otros changes necesitan una columna o relación nueva] → se pide a Belén y se agrega con una migración nueva (`0003_...`), nunca editando las ya aplicadas en `main`.
- [Seed lento por bcrypt con costo 12] → 7 hashes en paralelo bajo el semáforo (~1 s); los tests usan costo 4.
- [`TRUNCATE` permitido] → un usuario con acceso a psql puede vaciar los historiales; queda fuera de RN-15 (que habla de modificar o borrar filas) y del alcance (el segundo mecanismo, permisos, no se pide).
- [Correr Alembic o `seed.py` fuera de la raíz] → no encuentra el `.env` y falla con error de configuración (no con un esquema a medias); se documenta para el README.

## Migration Plan

1. PR `feat/esquema-y-migraciones` → `main` con `Closes #2`, después de que se mergee CH-01 (#12); si `main` avanza, rebase sobre `main`.
2. Cada integrante, tras el merge: `alembic upgrade head` sobre su base `taller` y su `taller_test`, y `python seed.py`.
3. Rollback: `alembic downgrade base` (probado) y revertir el merge.
4. Cambios futuros de esquema: siempre con una migración nueva; las dos de este change no se editan una vez en `main`.

## Open Questions

- Si `alembic check` necesita algún ajuste de comparación con SQLAlchemy 2.1 / SQLModel 0.0.48 (se sabe recién al correrlo; no cambia specs ni tareas).
- C-13 necesita una orden TERMINADA para el 409; el seed no la trae (la consigna no la pide). Se resuelve en el `.http` de CH-08 (terminando una orden antes) o pidiendo una orden extra al seed; no bloquea este change.
