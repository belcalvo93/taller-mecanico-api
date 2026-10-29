# Tasks

> TDD estricto en cada tarea: **ROJO** (escribir primero el test indicado, ejecutarlo y verificar que falla por la razón esperada) → **VERDE** (código mínimo, ejecutado) → **TRIANGULAR** (otro caso con datos distintos) → **REFACTOR** (tests verdes tras cada paso). Cada escenario de las specs tiene al menos un test.
> Tests en `tests/` (pytest) contra la base real `taller_test` (la fija `tests/conftest.py`); `test/` es sólo para `solo_agregado.sql`. Comando: `.venv/Scripts/python -m pytest` desde la raíz.
> Governance CRITICO: en cada **[CHECKPOINT]** se frena y se le muestra a Belén lo hecho; no se sigue sin su OK.
> **No se hacen commits durante el apply**: Belén commitea al final con la división propuesta en el grupo 9. Nunca agregar líneas `Co-Authored-By`, `Claude-Session` ni "Generated with Claude Code". Ninguna contraseña de la base ni clave de firma en archivos versionados, en el chat ni en logs.
> Datos del seed y decisiones a aprobar: `design.md` § "Datos a aprobar por Belén".

## 0. Red de seguridad

- [x] 0.1 Correr la suite actual de CH-01 y anotar la línea base (`N passed, 1 skipped` esperado: el skip es `test_base_migrada_deja_la_tabla_de_versiones`). Si algo falla, PARAR y reportarlo como falla previa (no arreglarlo acá)
- [x] 0.2 Verificar que `taller_test` existe y está vacía (sin tablas en `public`) con una consulta a `information_schema.tables`; si tiene tablas, PARAR y preguntarle a Belén antes de borrarlas

## 1. Convención de nombres y hora UTC en `app/core/database.py`

- [x] 1.1 ROJO: `tests/test_modelos.py::test_convencion_de_nombres` — tras importar `app.core.database`, `SQLModel.metadata.naming_convention` tiene las claves `ix`, `uq`, `ck`, `fk`, `pk` con los patrones de design D3. Ejecutar: falla (no existe `NAMING_CONVENTION`)
- [x] 1.2 VERDE: agregar `NAMING_CONVENTION` y su asignación a `SQLModel.metadata` en `app/core/database.py`. Ejecutar: verde
- [x] 1.3 ROJO→VERDE `ahora_utc()`: devuelve un `datetime` con `tzinfo` UTC; TRIANGULAR: dos llamadas seguidas no son iguales a nivel de microsegundos o la segunda es mayor o igual, y `utcoffset()` es cero. Ejecutar: verdes
- [x] 1.4 Correr toda la suite (los tests de CH-01 sobre `database.py` siguen verdes; la importación sin entorno de `test_importacion.py` sigue pasando)

## 2. Modelos (13) y registro de modelos

- [x] 2.1 ROJO `tests/test_modelos.py`: `import app.modules.modelos` expone las 13 clases y `SQLModel.metadata.tables` tiene exactamente los 13 nombres de tabla de la consigna. Ejecutar: falla (no existe el módulo)
- [x] 2.2 VERDE usuarios: `app/modules/usuarios/models.py` con `Usuario`, `AsignacionRol`, `IntentoAcceso`, `EventoSeguridad` (`__tablename__` explícito, tipos de design D2, FK con índice D4, CHECK `rol_valido`, índice parcial `uq_asignacion_rol_abierta`, índice `ix_intento_acceso_email_ip_cuando`, UNIQUE email). Antes de escribirlos, agregar al test los casos de esas 4 tablas: columnas exactas, nulabilidad (sólo `password_cambiada_en`, `vence_en`, `revocada_en`, `otorgada_por` aceptan NULL), `usuario` sin columna `rol`, `DateTime(timezone=True)` en `password_cambiada_en`, `desde`, `vence_en`, `revocada_en`, `cuando`. Ejecutar: rojo → verde
- [x] 2.3 VERDE clientes: `app/modules/clientes/models.py` (`Cliente`, `Vehiculo`, UNIQUE `usuario_id` y `documento`, CHECK `anio_rango`, índice parcial `uq_vehiculo_patente_vigente` con `postgresql_where`). Test primero: columnas, nulos (`usuario_id`, `borrado_en`), nombre y cláusula `WHERE borrado_en IS NULL` del índice parcial leídos de `Table.indexes`. Ejecutar: rojo → verde
- [x] 2.4 VERDE repuestos: `app/modules/repuestos/models.py` (`Repuesto`, `MovimientoStock`, `HistorialPrecio` → `historial_precio_repuesto`, CHECKs de precio/stock/cantidad/precio_nuevo, índice parcial `uq_repuesto_codigo_vigente`). Test primero: `NUMERIC(10,2)` en `precio`, `precio_anterior`, `precio_nuevo`; anotaciones `Decimal` (nunca `float`); nulos (`borrado_en`, `orden_id`). Ejecutar: rojo → verde
- [x] 2.5 VERDE ordenes: `app/modules/ordenes/models.py` (`EstadoOrden` con PK `codigo` y UNIQUE `posicion`, `OrdenTrabajo` con FK `estado` y CHECK `total_no_negativo` `NUMERIC(12,2)`, `ItemOrden` con UNIQUE `(orden_id, repuesto_id)` y CHECKs, `HistorialEstadoOrden` con dos FK al catálogo). Test primero: PK de `estado_orden` es `codigo`; `estado`, `desde_estado`, `hasta_estado` tienen FK a `estado_orden.codigo`; ninguna `CheckConstraint` de esas tablas menciona `PENDIENTE` u otro estado. Ejecutar: rojo → verde
- [x] 2.6 VERDE registro: `app/modules/modelos.py` (design D6) importando los cuatro `models.py`; agregar a `main.py` una sola línea `import app.modules.modelos  # noqa: F401` con comentario breve. Ejecutar 2.1: verde
- [x] 2.7 TRIANGULAR nombres de restricciones: test parametrizado con la tabla completa de design D3 (cada nombre aparece en `Table.constraints`/`Table.indexes` de su tabla) y test de que cada FK de `SQLModel.metadata` tiene un índice o UNIQUE cuya primera columna es la de la FK. Ejecutar: verdes (corregir lo que falte)
- [x] 2.8 ROJO→VERDE relaciones (sin base): con `sqlalchemy.inspect(Clase).relationships` verificar los dos extremos de cada fila de design D5 (`back_populates` cruzados), `Usuario.cliente` con `uselist=False`, `OrdenTrabajo.items` con cascada `delete-orphan` y `lazy == "raise"` en todas. TRIANGULAR: `configure_mappers()` no lanza error. Ejecutar: verdes
- [x] 2.9 REFACTOR: comentarios breves que citan la consigna/RN en restricciones no obvias; toda la suite verde
- [x] 2.10 **[CHECKPOINT 1 — modelos]** Frenar y mostrarle a Belén los cuatro `models.py`, `modelos.py`, el cambio de `database.py` y `main.py`, y los tests. Confirmar con ella las decisiones D4 (`otorgada_por` FK), D5 (relaciones y `lazy="raise"`) y D6 (archivo `modelos.py`). No seguir sin su OK

## 3. Alembic asincrónico sin credenciales

- [x] 3.1 ROJO `tests/test_migraciones.py`: `alembic.ini` existe, no tiene `sqlalchemy.url` con valor ni texto que matchee `postgresql(\+\w+)?://` ni `password`; `migrations/env.py` existe. Ejecutar: falla (no existen)
- [x] 3.2 VERDE: `alembic init -t async migrations` desde la raíz; borrar la línea `sqlalchemy.url` de `alembic.ini`; `script_location = %(here)s/migrations`; `file_template = %%(rev)s_%%(slug)s`; agregar `import sqlmodel` a `migrations/script.py.mako` (design D7). Ejecutar: verde
- [x] 3.3 ROJO→VERDE `env.py`: test en subproceso — con `POSTGRES_PASSWORD` vacía en el entorno y `cwd` en un directorio temporal sin `.env` (usando `-c <raíz>/alembic.ini`), `alembic current` termina con código distinto de 0 y la salida menciona `POSTGRES_PASSWORD`. Implementar `env.py`: `import app.modules.modelos`, `target_metadata = SQLModel.metadata`, motor con `create_async_engine(get_settings().DATABASE_URL, poolclass=NullPool)`, modo offline con `url=get_settings().DATABASE_URL`, sin `set_main_option`. TRIANGULAR: con el entorno normal y `POSTGRES_DB=taller_test`, `alembic current` termina con código 0. Ejecutar: verdes
- [x] 3.4 REFACTOR: comentarios en `env.py` que citan la regla 8 (sin secretos en `alembic.ini`) y el porqué de no usar `set_main_option` (`%` en la contraseña); suite verde

## 4. Migración 1 (autogenerate)

- [x] 4.1 ROJO `tests/test_esquema.py` (usa `base_migrada` y una fixture `motor` por función con `dispose()`): las 13 tablas existen en `public` (sin contar `alembic_version`) y las 13 están vacías. Ejecutar: falla (`alembic upgrade head` no tiene revisiones o no hay tablas)
- [x] 4.2 VERDE: `POSTGRES_DB=taller_test alembic revision --autogenerate -m "esquema inicial" --rev-id 0001` contra `taller_test` vacía. NO aplicarla todavía
- [x] 4.3 **[CHECKPOINT 2 — migración 1, antes de aplicarla]** Frenar y mostrarle a Belén `migrations/versions/0001_esquema_inicial.py` completo, señalando: tipos con zona, `Numeric`, los CHECK con nombre, los tres `postgresql_where`, el índice de `intento_acceso`, un índice por FK, `estado_orden` sin datos y el `downgrade`. Belén la lee, decide correcciones a mano y **ella** escribe (o dicta) el comentario `# Leída antes de aplicarla por ... el ... Correcciones a mano: ...` al principio del archivo. No aplicar sin su OK
- [x] 4.4 Aplicar (`alembic upgrade head` vía la fixture) y ejecutar 4.1: verde
- [x] 4.5 ROJO→VERDE comentario: `tests/test_migraciones.py` verifica que cada archivo de `migrations/versions/*.py` contiene "Leída antes de aplicarla". Ejecutar: verde para 0001
- [x] 4.6 ROJO→VERDE tipos y nulos contra la base: todas las columnas de fecha son `timestamp with time zone`; columnas de dinero `numeric` con precisión/escala de la spec; nulabilidad según la spec. TRIANGULAR: un instante con microsegundos se guarda y se lee igual y con zona; un `precio` se lee como `Decimal('8500.00')`. Usar la fixture `conexion` con rollback (design D12)
- [x] 4.7 ROJO→VERDE restricciones contra la base (parametrizado, cada caso en `begin_nested()` y comparando el `constraint_name` de asyncpg con la tabla D3): email, documento, `cliente.usuario_id` repetidos; ítem repetido en una orden; posición repetida; cada CHECK prohibido de la spec (rol `JEFE`, año 1949 y 2101, precio 0, stock -1, total -0.01, cantidad 0, precio unitario 0, movimiento 0, precio nuevo 0 y precio nuevo igual al anterior). TRIANGULAR con los valores borde aceptados (1950, 2100, stock 0, total 0, movimientos 5 y -3) y dos clientes con `usuario_id` NULL
- [x] 4.8 ROJO→VERDE índices parciales contra la base: patente vigente repetida falla por `uq_vehiculo_patente_vigente`; tras `borrado_en` se acepta; mismo par para `repuesto.codigo`; asignación abierta repetida falla y tras `revocada_en` se acepta; ADMIN y MECANICO abiertos del mismo usuario se aceptan
- [x] 4.9 ROJO→VERDE FK: estado `DEMORADA` con catálogo cargado (dentro de la transacción revertida) falla por `fk_orden_trabajo_estado_estado_orden`; `PENDIENTE` con catálogo vacío también falla; `cliente_id` inexistente falla; con `pg_catalog`, cada FK del esquema tiene un índice cuya primera columna es la de la FK; `intento_acceso` tiene el índice `(email, ip, cuando)` en ese orden
- [x] 4.10 ROJO→VERDE navegación y carga perezosa contra la base: usuario con `selectinload(Usuario.cliente)` → objeto `Cliente` (o `None`) y `cliente.usuario` es el mismo usuario; orden con ítems y repuestos precargados; acceder a `cliente.vehiculos` sin precargar lanza `InvalidRequestError` sin ejecutar SQL (contar sentencias con un listener `before_cursor_execute`), y precargado devuelve la lista
- [x] 4.11 ROJO→VERDE primera migración sola: en subproceso, `alembic downgrade base` + `alembic upgrade 0001` → las 13 tablas y los 3 índices parciales existen; luego `alembic upgrade head` (deja la base en `head`)
- [x] 4.12 REFACTOR: helpers de test compartidos (`constraint_name(exc)`, consultas a catálogo) en un módulo de `tests/`; toda la suite verde, incluido `test_base_migrada_deja_la_tabla_de_versiones` (ya no se saltea)
- [x] 4.13 Mostrarle a Belén el resultado de la suite completa y cualquier corrección a mano hecha a 0001 (para la bitácora)

## 5. Migración 2 (a mano): sólo agregado

- [x] 5.1 ROJO `tests/test_solo_agregado.py`: insertar una fila válida en cada una de las tres tablas se acepta; un `UPDATE` sobre esa fila falla con un mensaje que contiene "sólo agregado" y el nombre de la tabla, y la fila no cambia. Ejecutar: el `UPDATE` no falla (todavía no hay disparador) → rojo
- [x] 5.2 VERDE: `alembic revision -m "solo agregado" --rev-id 0002` y escribir a mano `upgrade` (función `rechazar_cambio_solo_agregado()` + tres `trg_<tabla>_solo_agregado BEFORE UPDATE OR DELETE ... FOR EACH STATEMENT`, design D9) y `downgrade` (`DROP TRIGGER IF EXISTS` ×3 + `DROP FUNCTION IF EXISTS`). NO aplicarla todavía
- [x] 5.3 **[CHECKPOINT 3 — migración 2, antes de aplicarla]** Frenar y mostrarle a Belén `0002_solo_agregado.py`; confirmar `FOR EACH STATEMENT` y `TRUNCATE` permitido (D9). Ella escribe el comentario de lectura previa. No aplicar sin su OK
- [x] 5.4 Aplicar y ejecutar 5.1: verde. TRIANGULAR: `DELETE` en cada tabla falla y la cantidad de filas no cambia; `UPDATE ... WHERE false` y `DELETE` sobre tabla vacía también fallan; `UPDATE` de `repuesto.precio` y de `orden_trabajo.falla` se aceptan; `TRUNCATE` de las tres tablas se acepta. Ejecutar 4.5: verde también para 0002
- [x] 5.5 ROJO→VERDE historial de revisiones: con `alembic.script.ScriptDirectory` hay exactamente dos revisiones, `0002.down_revision == "0001"` y la única cabeza es `0002`
- [x] 5.6 ROJO→VERDE ciclo (subproceso, con `timeout`): `upgrade head` → `downgrade base` (no queda ninguna de las 13 tablas, ni la función, ni los disparadores; `alembic_version` vacía) → `upgrade head` (mismo inventario de tablas, columnas, restricciones, índices y disparadores que antes: comparar una "foto" del catálogo antes y después). Termina en `head`
- [x] 5.7 ROJO→VERDE `alembic check` en subproceso termina con código 0 (modelos y migraciones coinciden). Si aparecen diferencias falsas (design, Riesgos), PARAR, mostrárselas a Belén y ajustar `env.py` sólo con su OK
- [x] 5.8 ROJO→VERDE nadie usa `create_all`: búsqueda en `app/`, `main.py`, `migrations/`, `seed.py` (cuando exista) y `SQLModel.metadata.create_all` en `tests/`
- [x] 5.9 REFACTOR y suite completa verde

## 6. `seed.py`

- [x] 6.1 ROJO `tests/test_seed.py` (con `monkeypatch` `BCRYPT_COST=4`): tras `await seed.sembrar(motor, get_settings())`, `estado_orden` tiene PENDIENTE 1, EN_REPARACION 2, TERMINADA 3 (final), CANCELADA 4 (final), con descripción no vacía. Ejecutar: falla (no existe `seed.py`)
- [x] 6.2 VERDE mínimo: `seed.py` con `sembrar` (TRUNCATE de las 13 tablas `RESTART IDENTITY CASCADE` + catálogo) y `main()` con `asyncio.run` bajo `if __name__ == "__main__"` (design D10). Ejecutar: verde
- [x] 6.3 ROJO→VERDE orden de carga: con un listener `before_cursor_execute` en `motor.sync_engine`, el `TRUNCATE` va antes que todo y la primera inserción es sobre `estado_orden`
- [x] 6.4 ROJO→VERDE usuarios y roles: los siete correos con ids 1..7 en el orden de la spec, cada uno con exactamente su rol vigente (sin `vence_en` ni `revocada_en`), todos activos, `password_cambiada_en` vacío y `debe_cambiar_password` sólo en `nuevo@`
- [x] 6.4b ROJO→VERDE ids de la consigna (pedido de Belén): usuarios 1 a 7 en el orden admin, admin2, recepcion, mecanico, mecanico2, cliente, nuevo; repuestos 1 FIL-001, 2 FRE-010, 3 BUJ-100, 4 ACE-530; vehículo 2 = AC456EF de Laura. Contrastado con `docs/consigna-tp.md` (los ejemplos fijan repuesto 1 FIL-001, 2 FRE-010, 4 ACE-530, vehículo AC456EF de Laura y usuario_id 3; el resto sale del orden en que la consigna los lista)
- [x] 6.5 ROJO→VERDE contraseñas: `bcrypt.checkpw` con la contraseña de prueba de `seed` da verdadero para cada usuario y falso con otra; hashes con prefijo `$2b$04$`. TRIANGULAR con `BCRYPT_COST=5` → `$2b$05$`. Test de que los hashes se calculan antes de abrir la transacción (espía sobre `bcrypt.hashpw` que registra si ya hubo alguna sentencia SQL: ninguna) y por `asyncio.to_thread`; `seed.py` no importa `app.core.security`
- [x] 6.6 ROJO→VERDE clientes y vehículos: Laura (usuario 6) con vehículos 1 y 2 (el 2 con `AC456EF`); Jorge sin usuario con el vehículo 3; datos de la tabla aprobada
- [x] 6.7 ROJO→VERDE repuestos y stock: los cuatro repuestos con ids 1..4, códigos, descripciones, precios y stocks aprobados; un único movimiento "Stock inicial" por repuesto, sin orden, con `cantidad == stock`; historial de precio único de `FIL-001` 8000.00 → 8500.00
- [x] 6.8 ROJO→VERDE órdenes: orden 1 PENDIENTE del vehículo 1 sin mecánico con sus ítems e historial (NULL→PENDIENTE); orden 2 EN_REPARACION del vehículo 3 con mecánico 4, ítem de 4 bujías con stock 2, historial NULL→PENDIENTE→EN_REPARACION; en ambas `precio_unitario == repuesto.precio` y `total == Σ cantidad × precio_unitario`; una orden nueva insertada sin `id` recibe el 3
- [x] 6.9 ROJO→VERDE evento de seguridad: una sola fila, actor `SISTEMA`, acción "Carga de los datos iniciales"
- [x] 6.10 TRIANGULAR reproducibilidad: con filas extra (un repuesto y un movimiento suyo) el seed las elimina; dos corridas seguidas dejan las 13 tablas con las mismas filas e ids; si la carga falla a mitad (monkeypatch de un dato inválido, p. ej. stock -1), la base queda con lo que tenía antes
- [x] 6.11 ROJO→VERDE `python seed.py` en subproceso con `POSTGRES_DB=taller_test` termina con código 0 y deja los datos; `seed.py` no contiene `postgresql://`, la contraseña de la base ni `JWT_SECRET_KEY`
- [x] 6.12 REFACTOR: datos como constantes legibles al principio de `seed.py` (catálogo, usuarios con contraseña, clientes, vehículos, repuestos, órdenes), comentario que dice que las contraseñas son de prueba y viven sólo acá; suite completa verde
- [x] 6.13 **[CHECKPOINT 4 — seed]** Frenar y mostrarle a Belén `seed.py` y la tabla "Datos a aprobar por Belén" de `design.md` lado a lado. Ella aprueba o cambia patentes, documentos, teléfonos, nombres, contraseñas, bujía (código, descripción, precio), fallas e ítems de la orden 1. Si cambia algo, actualizar `seed.py`, los tests y la tabla del design, y volver a correr la suite. No seguir sin su OK

## 7. `test/solo_agregado.sql` (caso C-14)

- [x] 7.1 ROJO `tests/test_solo_agregado.py::test_script_c14`: con `taller_test` recién sembrada, leer `test/solo_agregado.sql`, separar las sentencias (ignorando comentarios y metacomandos `\`) y ejecutar cada una en su propia transacción: son exactamente 7; las 6 primeras fallan con el mensaje de sólo agregado (una `UPDATE` y una `DELETE` por tabla) y la 7.ª con la FK `fk_orden_trabajo_estado_estado_orden`. Ejecutar: falla (no existe el archivo)
- [x] 7.2 VERDE: escribir `test/solo_agregado.sql` (design D11): encabezado con cómo correrlo, `\set ON_ERROR_STOP off`, cada sentencia con su `-- Esperado: ...`. Ejecutar: verde
- [x] 7.3 TRIANGULAR: después de ejecutar el script, las cantidades de filas y los valores de las filas tocadas son los mismos que antes; el archivo no tiene `BEGIN`/`COMMIT`. Ejecutar: verdes
- [x] 7.4 Si `psql` está en el PATH, correrlo una vez a mano sobre `taller_test` (`psql -U taller -d taller_test -f test/solo_agregado.sql`) y mostrarle a Belén los siete errores (la captura oficial la saca CH-09)

## 8. Integración y bitácora

- [x] 8.1 Ciclo con datos: `python seed.py` sobre `taller_test` → `alembic downgrade base` termina sin error aunque haya filas en las tablas de sólo agregado → `alembic upgrade head`. Verificar con un test en subproceso (o agregarlo a 5.6)
- [x] 8.2 Suite completa desde la raíz: todos verdes, 0 skips (salvo los que CH-01 documenta), y comparar contra la línea base de 0.1
- [x] 8.3 Verificar contra las reglas que toca el change: RN-01, RN-03, RN-15, RN-16 y RN-20 (columnas/CHECK), RN-18 (la base garantiza la unicidad, nombres fijos), RN-19 (FK al catálogo, catálogo vacío tras migrar) y C-14; y contra las reglas 1–5 y 8 de `CLAUDE.md`. Anotar en el resumen del apply cualquier desvío
- [x] 8.4 `docs/bitacora.md`, sección Belén: entrada con fecha, qué se le pidió al agente, qué corrigió a mano en cada migración y por qué, los datos del seed aprobados y las decisiones D4/D5/D6/D9. Agregar a "Pendientes para CH-09": correr Alembic y `seed.py` desde la raíz; cómo correr `solo_agregado.sql` en psql para la captura
- [x] 8.5 `git status`: confirmar que `.env` no aparece y que no hay archivos fuera del alcance del change (sólo los listados en `proposal.md` § Impact)

## 9. Propuesta de commits (sólo propuesta; los hace Belén)

- [x] 9.1 Presentarle a Belén esta división en commits chicos, en español, con el nombre del change y **sin** líneas de coautoría ni de sesión, y esperar que ella los haga:
  1. `feat(esquema-y-migraciones): convención de nombres de restricciones y hora UTC`
  2. `feat(esquema-y-migraciones): modelos de usuarios, clientes, repuestos y ordenes`
  3. `feat(esquema-y-migraciones): alembic asincrónico sin credenciales`
  4. `feat(esquema-y-migraciones): migración 1 autogenerada con índices parciales`
  5. `feat(esquema-y-migraciones): migración 2 con el disparador de sólo agregado`
  6. `feat(esquema-y-migraciones): seed.py con los datos iniciales`
  7. `test(esquema-y-migraciones): solo_agregado.sql del caso C-14`
  8. `docs(esquema-y-migraciones): bitácora y tareas marcadas`
  Cada commit lleva sus tests. Antes de cada uno: `git status` sin `.env`

## Workflow follow-up

- PR `feat/esquema-y-migraciones` → `main` con `Closes #2`, después del merge de CH-01 (#12), con revisión de un compañero (ideal: Elías, por la coordinación D13 con CH-03).
- Avisar al equipo: tabla de nombres de restricciones (design D3) para la traducción a 409; `lazy="raise"` y precarga obligatoria; ids del seed; cualquier columna nueva se pide a Belén y va en una migración nueva.
- Tras el merge: `/opsx:archive esquema-y-migraciones` y marcar CH-02 en `CHANGES.md`.
