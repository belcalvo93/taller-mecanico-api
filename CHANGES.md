# CHANGES — Secuencia de Implementación

> Índice canónico de todos los changes del proyecto **taller-mecanico-api** (TP integrador de Programación III, UTN: API asincrónica de taller mecánico con FastAPI + SQLModel + PostgreSQL + Alembic).
> Cada change es atómico: una persona (con su agente) lo implementa en una sesión de trabajo de ~4-6 horas.
> **Leer este archivo antes de ejecutar cualquier `/opsx:propose`.**
> Fuente de verdad del contenido: `docs/consigna-tp.md`. Reglas duras del proyecto: `CLAUDE.md`. Reparto, olas y calendario: `knowledge-base/09_decisiones_y_supuestos.md` (DD-06, DD-12..DD-18).

**Nota sobre los identificadores**: en este proyecto `C-01..C-19` son los **casos de prueba** de la consigna (y `RN-01..RN-20` las reglas de negocio). Para no mezclarlos, los changes se numeran `CH-01..CH-09` (el nombre kebab-case es el que se usa en `openspec` y en las ramas `feat/<change>`).

**Número de issue**: **CH-NN = número del issue de GitHub** del change. Los issues se crean en el orden de DD-06 (01 `infra-base`, 02 `esquema-y-migraciones`, 03 `nucleo-repositorios-uow`, 04 `autenticacion`, 05 `autorizacion-y-roles`, 06 `clientes-y-vehiculos`, 07 `repuestos-y-stock`, 08 `ordenes`, 09 `casos-y-entrega`), de modo que el issue #4 es CH-04, etc. Los PRs referencian ese número (`Closes #NN`).

**IMPORTANTE — fuente de verdad de los issues**: el cuerpo de cada issue sale de este archivo (CH-NN = issue #NN). Se copia de acá el scope, las tareas, los casos C, las RN y las dependencias de cada change. Si una tabla resumen (la de abajo, o cualquier otra que se use para crear los issues) difiere de este archivo, **manda CHANGES.md**. Ejemplos: C-01 es de #4, C-06 es de #8 y C-14 es de #2.

---

## Cómo usar este documento

1. Identificar el change a implementar (su número CH-NN es el del issue de GitHub) y verificar que sus dependencias están **mergeadas a `main`** (PR aprobado por al menos un compañero) y archivadas en `openspec/changes/archive/`. Algunas dependencias son **puntuales** (una sola tarea de otro change, ver Árbol): alcanza con que esa tarea esté en `main`.
2. Leer los docs de la `knowledge-base/` indicados en "Leer antes" (más `CLAUDE.md`).
3. Crear la rama `feat/<nombre-del-change>` y ejecutar `/opsx:propose <nombre-del-change>`; después `/opsx:apply <nombre-del-change>` (TDD estricto: rojo → verde → triangular → refactor).
4. Al terminar: abrir PR a `main`, conseguir la aprobación de al menos un compañero, mergear y archivar con `/opsx:archive <nombre-del-change>`.
5. Marcar el checkbox `[x]` en el campo **Estado** del change en este archivo y anotar la entrada en la bitácora.

### Reglas transversales de proceso (valen para TODOS los changes)

- **Ramas y PRs (DD-08, DD-17)**: una rama `feat/<change>` por change; PR a `main`; no se mergea sin la aprobación de **al menos un compañero**. Commits chicos y en español con el nombre del change. La fundación ya está en main (commit f01d452); cada change arranca su rama feat/<change> desde main actualizado.
- **Bitácora (DD-17, AP-07)**: `docs/bitacora.md` (la crea `infra-base`) con **una sección por integrante**; por cada entrada: **fecha, qué le pidió al agente, qué corrigió a mano y por qué**. Cada uno la completa en el PR de su change; `casos-y-entrega` la revisa al final. Es la evidencia para la demo en vivo (los 5 trabajaron y revisaron).
- **Un solo dueño de los modelos**: sólo `esquema-y-migraciones` escribe `app/modules/<mod>/models.py` y las migraciones. Los demás changes **no tocan modelos**; si necesitan una columna, se pide a Belén y se agrega ahí (se pueden agregar columnas, no quitar ni renombrar).
- **Cada módulo escribe lo suyo (DD-12)**: `repository.py`, `unit_of_work.py`, `schemas.py`, `service.py`, `router.py` y los `.http` de sus casos los escribe el change de ese módulo.
- **`.http` por change (DD-16, AP-06)**: cada integrante escribe en `test/` los `.http` de sus casos C (un archivo por caso, propuesta de nombre `test/C-NN_<tema>.http`, con la respuesta esperada en un comentario). `casos-y-entrega` sólo consolida, corre todo y saca las evidencias. Antes de cada archivo se corre `python seed.py`. Para varias sesiones a la vez: `# @name` en cada login y `# @no-cookie-jar` + encabezado `Cookie` en los pedidos (ver la consigna).
- **Carpeta `tests/` vs `test/` (DD-09)**: `tests/` = pytest; `test/` = `.http` y `solo_agregado.sql` (reservada por la consigna).
- **Reglas duras de arquitectura**: commit sólo en el UoW (service y repos usan `flush`); el router construye el UoW y el servicio lo abre con `async with`; unicidad por la base (`IntegrityError` → 409 con mensaje propio, RN-18); `extra="forbid"`; PATCH con `exclude_unset`; nada de carga perezosa; secretos sólo en `.env`; bcrypt con `to_thread` + semáforo y antes de abrir la transacción; token sólo en cookie `access_token`.
- **`main.py` y conflictos**: `infra-base` deja en `main.py` los dos grupos de rutas con un lugar claro para `include_router` de cada módulo; cada change agrega **sólo su línea** en el grupo que le toca (abierto/protegido) para minimizar conflictos de merge.
- **Alcance**: estrictamente la consigna (DD-04): sin Docker, CI, linter ni extras.

### Convención de governance

| Nivel | Qué significa para el equipo |
|---|---|
| **CRITICO** | Auth, seguridad, auditoría, modelos que todo referencia. Proponer (`/opsx:propose`) y esperar revisión de un compañero **antes** de implementar; revisión más estricta del PR. |
| **ALTO** | Transacciones multi-tabla, stock, configuración con secretos. Implementar con checkpoints y mostrar las decisiones no obvias en el PR. |
| **MEDIO** | Lógica de negocio y adaptadores de dominio. Implementar por pasos; dejar las decisiones no obvias en la bitácora. |
| **BAJO** | Scaffolding, consolidación, documentación. Autonomía plena si los tests pasan. |

---

## Árbol de dependencias

```
CH-01 infra-base                                   (Belén · ola 1)
  ├── CH-02 esquema-y-migraciones                  (Belén · ola 1)   ← bloquea a TODA la ola 2
  └── CH-03 nucleo-repositorios-uow                (Elías · ola 1)   ← paralelo con CH-02 (DD-12)
        │
        └── (CH-02 + CH-03 ✓)  ══════════ GATE 2: se abre la ola 2 ══════════
              │
              ├── CH-04 autenticacion              (Hernán · ola 2)
              │     │
              │     ├── [T1 de CH-04] requiere_rol + get_usuario_actual PROVISORIOS en app/core/dependencies.py
              │     │         │            (PRIMERA tarea; PR chico a main el lunes 26)
              │     │         │
              │     │         ╞═ GATE "dependencias provisorias en main" ═╗   (dentro de la ola 2)
              │     │                                                      ║
              │     │         ┌────────────────────────────────────────────╨──┐
              │     │         ▼                                               ▼
              │     │   CH-06 clientes-y-vehiculos (Joaquín)      CH-07 repuestos-y-stock (Bruno)
              │     │     depende SÓLO de T1 de CH-04               depende SÓLO de T1 de CH-04
              │     │         │
              │     │         └─ [T1 de CH-06] ClienteRepository básico (DD-13) ──► lo usa CH-04 (registro, RN-02)
              │     │                                                              dependencia PUNTUAL, no del change completo
              │     │
              │     └── (CH-04 completo ✓)
              │           └── CH-05 autorizacion-y-roles (Hernán · ola 2)
              │                 reemplaza/completa las dependencias provisorias con la versión real
              │
              └── (CH-04 ✓ + CH-05 ✓ + CH-06 ✓ + CH-07 ✓)   ← CH-08 depende de CH-04 y CH-05 COMPLETOS
                    │
                    └── CH-08 ordenes                (Elías · ola 3)
                          └── CH-09 casos-y-entrega  (Belén · ola 4)
```

**Dependencias provisorias (gate dentro de la ola 2)**: la **primera tarea de CH-04** sube a `main` `get_usuario_actual` y `requiere_rol(*roles)` **provisorios** en `app/core/dependencies.py`, con las **firmas definitivas**: `get_usuario_actual` devuelve el usuario autenticado a partir de la cookie `access_token`; `requiere_rol(*roles)` devuelve una dependencia que valida el rol. CH-06 y CH-07 dependen **sólo de esa tarea**, no de CH-04 completo: la importan para cablear los permisos de sus rutas (nada de `dependency_overrides` como solución final; los tests pueden usarlos para aislar). **CH-05 `autorizacion-y-roles` reemplaza/completa esas dependencias con la versión real** (roles vigentes leídos de la base en cada petición, 401/403 por todas las causas, control del cambio obligatorio de contraseña) **sin cambiar las firmas**, así que CH-06 y CH-07 no se tocan. **CH-08 depende de CH-04 y CH-05 completos** (necesita la versión real de `requiere_rol` y el 401/403 verdaderos).

**Dependencia puntual inversa (DD-13)**: el registro de CH-04 (`POST /auth/registro`, RN-02) usa `ClienteRepository`, que es la **primera tarea de CH-06**. CH-04 no depende del change CH-06 completo, sólo de esa tarea; si Hernán llega antes, la crea con la misma firma y Joaquín la extiende.

### Resumen

| Change | Ola | Responsable | Governance | Depende de | Fechas (DD-18) |
|---|---|---|---|---|---|
| CH-01 `infra-base` | 1 | Belén | ALTO | — | vie 23/10 |
| CH-02 `esquema-y-migraciones` | 1 | Belén | CRITICO | CH-01 | vie 23 – lun 26/10 |
| CH-03 `nucleo-repositorios-uow` | 1 | Elías | ALTO | CH-01 | vie 23 – lun 26/10 |
| CH-04 `autenticacion` | 2 | Hernán | CRITICO | CH-01, CH-02, CH-03; puntual: `ClienteRepository` (T1 de CH-06) para el registro | lun 26 – mié 28/10 |
| CH-05 `autorizacion-y-roles` | 2 | Hernán | CRITICO | CH-04 completo (+ CH-02, CH-03) | lun 26 – mié 28/10 |
| CH-06 `clientes-y-vehiculos` | 2 | Joaquín | MEDIO | CH-01, CH-02, CH-03 + **sólo T1 de CH-04** (dependencias provisorias) | lun 26 – mié 28/10 |
| CH-07 `repuestos-y-stock` | 2 | Bruno | ALTO | CH-01, CH-02, CH-03 + **sólo T1 de CH-04** (dependencias provisorias) | lun 26 – mié 28/10 |
| CH-08 `ordenes` | 3 | Elías | ALTO | CH-04 y CH-05 completos, CH-06, CH-07 | mié 28 – jue 29/10 |
| CH-09 `casos-y-entrega` | 4 | Belén | BAJO | CH-08 (y todo lo anterior) | jue 29 – vie 30/10 mañana |

### Cobertura de casos de prueba (C-01..C-19) por change

| Caso | Change que lo escribe | Observación |
|---|---|---|
| C-01 | CH-04 `autenticacion` | Transversal: lo cumplen todas las rutas con `{id}` (CH-05, CH-06, CH-07, CH-08); cada change con rutas `{id}` lo verifica en sus tests |
| C-02, C-03, C-04, C-05 | CH-04 `autenticacion` | |
| C-06 | CH-08 `ordenes` (completo) | Necesita los endpoints de órdenes para probar que el cliente ve su orden (200) y no la ajena (403); en el mismo `.http` van el 401 contra 403 y lo propio sin rol. CH-05 aporta el mecanismo (`requiere_rol`, 401/403) pero **no** escribe C-06 |
| C-07, C-08, C-09 | CH-05 `autorizacion-y-roles` | C-09 usa `cambiar-password` de CH-04 |
| C-10, C-11, C-12, C-13, C-17 | CH-08 `ordenes` | |
| C-14 | CH-02 `esquema-y-migraciones` | Escribe **y prueba** el trigger y la FK al catálogo con `test/solo_agregado.sql`. CH-09 sólo saca la captura de psql como evidencia |
| C-15 | CH-08 `ordenes` | Evidencia de consola en CH-09 |
| C-16, C-18 | CH-07 `repuestos-y-stock` | |
| C-19 | CH-06 `clientes-y-vehiculos` | |

Todos los casos se consolidan y corren en CH-09.

### Paralelismo por fase

> "✓" significa **PR mergeado a `main` con aprobación de al menos un compañero**. La fundación (discovery, KB, roadmap, skills, `CLAUDE.md`) termina hoy, viernes 23/10 (DD-18). Entrega: viernes 30/10/2026.

```
GATE 0: ninguna                                         (vie 23/10)
  → CH-01 infra-base                          [Belén]

GATE 1: CH-01 ✓                                         ← FORK de la ola 1 (vie 23 – lun 26)
  → CH-02 esquema-y-migraciones               [Belén]
  → CH-03 nucleo-repositorios-uow             [Elías]   (núcleo genérico de app/core/ con modelo mínimo de test: no espera los modelos de Belén)

GATE 2: CH-02 ✓ + CH-03 ✓                               ← FORK de la ola 2 (lun 26 – mié 28)
  → CH-04 autenticacion                       [Hernán]  (1ª tarea T1: requiere_rol y get_usuario_actual provisorios en main)
  → CH-06 clientes-y-vehiculos                [Joaquín] (1ª tarea T1: ClienteRepository básico, DD-13; el resto espera el gate 2b)

GATE 2b: dependencias provisorias en main (T1 de CH-04 ✓)   ← DENTRO de la ola 2 (lun 26)
  → CH-06 clientes-y-vehiculos (resto)        [Joaquín] (cablea permisos con las firmas provisorias)
  → CH-07 repuestos-y-stock                   [Bruno]   (arranca acá; en lo que llega T1 puede leer KB y hacer /opsx:propose)
  → CH-05 autorizacion-y-roles                [Hernán — cuando CH-04 esté ✓ completo (security.py/JWT); reemplaza las provisorias por la versión real, mismas firmas]

GATE 3: CH-04 ✓ + CH-05 ✓ (completos) + CH-06 ✓ + CH-07 ✓   (mié 28 – jue 29)
  → CH-08 ordenes                             [Elías]

GATE 4: CH-08 ✓                                         (jue 29 – vie 30 a la mañana)
  → CH-09 casos-y-entrega                     [Belén]
```

**Coordinación obligatoria dentro de la ola 2 (dos dependencias puntuales cruzadas)**:

1. **`ClienteRepository` (DD-13)**: el UoW de `usuarios` importa `ClienteRepository` desde `app/modules/clientes/repository.py` para el registro (RN-02). Joaquín crea el `ClienteRepository` básico (hereda de `BaseRepository[Cliente]`) como **primera tarea** de CH-06 y lo mergea en un PR chico el lunes 26; Hernán lo usa en CH-04. Si Hernán llega antes, lo crea él **con la misma firma** y Joaquín lo extiende. Se acuerda la firma al arrancar la ola 2. CH-04 depende sólo de esa tarea, no de CH-06 completo.
2. **Dependencias provisorias (gate 2b)**: Hernán sube `requiere_rol` y `get_usuario_actual` provisorios (firmas definitivas) en `app/core/dependencies.py` como **primera tarea** de CH-04, en un PR chico el lunes 26. CH-06 y CH-07 dependen sólo de esa tarea. CH-05 los reemplaza por la versión real sin cambiar las firmas.

### Camino crítico (ola 1 → ola 2 → ola 3 → ola 4)

```
CH-01 → (CH-02 ∥ CH-03) → ola 2 { CH-04[T1 → resto] → CH-05*, ∥ CH-06 y CH-07 (arrancan tras T1 de CH-04) } → CH-08 ordenes → CH-09 casos-y-entrega
```

\* CH-04, CH-05, CH-06 y CH-07 gatean `ordenes`. La **primera tarea de CH-04** (dependencias provisorias) es el cuello de botella de arranque de CH-06 y CH-07: tiene que estar en `main` el lunes 26 a la mañana. Atención al ramal de Hernán: CH-05 `autorizacion-y-roles` también es requisito de CH-08 (`requiere_rol` real, permisos de cancelar/terminar, 401/403 verdaderos) y se hace **después** de CH-04 con la misma persona, así que en la práctica `CH-04 → CH-05` es la cadena más larga de la ola 2 y la que más riesgo tiene de comerse el margen de la entrega (DD-18). Cualquier atraso de la ola 2 se come el margen de la ola 3.

### Plan óptimo por persona (5 integrantes, cada uno con su agente)

El skill pide 3 agentes; acá son 5 personas con sus agentes y el reparto fijo de DD-06.

```
Paso (fechas)        │ Belén                      │ Elías                       │ Hernán                     │ Joaquín                   │ Bruno
─────────────────────┼────────────────────────────┼─────────────────────────────┼────────────────────────────┼───────────────────────────┼──────────────────────────
1 · vie 23           │ CH-01 infra-base           │ lee KB; prepara CH-03       │ —                          │ —                         │ —
2 · vie 23 – lun 26  │ CH-02 esquema-y-migraciones│ CH-03 nucleo-repos-uow      │ revisa PRs de ola 1        │ revisa PRs de ola 1       │ revisa PRs de ola 1
3 · lun 26 – mié 28  │ revisa PRs; borrador README│ explora CH-08 (/opsx:explore)│ CH-04 (T1 provisorias 1º)  │ CH-06 (T1 ClienteRepo 1º) │ CH-07 (arranca tras T1
                     │                            │                             │   → CH-04 resto → CH-05    │   luego cablea permisos   │   de CH-04)
4 · mié 28 – jue 29  │ revisa PRs                 │ CH-08 ordenes               │ revisa/apoya CH-08         │ revisa/apoya CH-08        │ revisa/apoya CH-08
5 · jue 29 – vie 30  │ CH-09 casos-y-entrega      │ corrige hallazgos de CH-08  │ corre sus .http, bitácora  │ corre sus .http, bitácora │ corre sus .http, bitácora
```

Los pasos 1-2 y 2-3 se solapan a propósito (el traspaso de ola es "PR mergeado", no "día cumplido"). Los tiempos de revisión de PR son parte del plan: ningún PR espera más de medio día.

---

## FASE 1 — Cimientos: proyecto, esquema y núcleo (Ola 1 · vie 23 – lun 26/10)

> Dos frentes en paralelo después de CH-01: Belén con el esquema (CH-02) y Elías con el núcleo genérico (CH-03). No se bloquean porque el núcleo se prueba con un modelo mínimo de test (DD-12).

### [CH-01] `infra-base`
- **Estado**: `[ ]` pendiente
- **Responsable / Ola**: Belén · ola 1 (vie 23/10)
- **Scope**: esqueleto ejecutable del proyecto, sin lógica de negocio
  - Estructura del proyecto según `08_arquitectura_propuesta.md`: `main.py`, `app/core/`, `app/modules/{health,usuarios,clientes,repuestos,ordenes}/`, `migrations/`, `test/`, `tests/`, `docs/`
  - `app/core/config.py`: `Settings` (pydantic-settings) leyendo entorno/`.env`; URL de la base con `@computed_field` desde `POSTGRES_USER/PASSWORD/DB/HOST/PORT` con driver `postgresql+asyncpg`; `POSTGRES_PASSWORD` y `JWT_SECRET_KEY` **sin default** (si faltan, la app no arranca); `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_SECONDS` (1800), `COOKIE_SECURE`, `BCRYPT_COST`, `BCRYPT_MAX_CONCURRENT`, `DB_POOL_SIZE`, `SQL_ECHO` (DD-10)
  - `app/core/database.py`: creación de motor async y fábrica de sesiones (`expire_on_commit=False`) que invoca el lifespan; `get_session` toma la fábrica de `app.state`
  - Lifespan en `main.py`: motor y fábrica en `app.state`, hash ficticio del login calculado una vez, `dispose()` al apagar; nada se crea al importar un módulo
  - `app/modules/health/router.py`: `GET /health/live` (200, sin tocar la base), `GET /health/ready` (`SELECT 1`; 503 si la base no contesta)
  - `main.py` con los **dos grupos de rutas** (abierto: salud + `/auth/*`; protegido: reservado para el control del cambio obligatorio que monta CH-05), vacíos y con el lugar de `include_router` de cada módulo
  - `env.example` con todas las variables y ningún secreto (cómo generar la clave de firma queda en el README de CH-09); `.env` en `.gitignore`; `requirements.txt` con las versiones mínimas del stack (Python 3.12, FastAPI 0.111, SQLModel 0.0.24, SQLAlchemy 2.0, asyncpg 0.30, Alembic 1.13, pydantic-settings 2.0, bcrypt 4.0, PyJWT 2.8, pytest + pytest-asyncio + httpx)
  - pytest/`conftest.py` (en `tests/`): fixture de la base de tests `taller_test` creada con `alembic upgrade head` (nunca `create_all`), `httpx.AsyncClient` contra la app; la fixture queda lista y se ejercita de punta a punta cuando CH-02 mergea las migraciones
  - `docs/bitacora.md` con una sección por integrante (Belén, Elías, Hernán, Bruno, Joaquín)
  - Tests: `Settings` falla sin `POSTGRES_PASSWORD`/`JWT_SECRET_KEY`; `/health/live` sin base; `/health/ready` 200 y 503
- **Dependencias**: ninguna
- **Governance**: ALTO (configuración con secretos y conexión a la base)
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` §Estructura de directorios, §Variables de entorno, §Estrategia de pruebas
  - `knowledge-base/02_descripcion_general.md` §Stack tecnológico, §Arquitectura general (lifespan)
  - `knowledge-base/06_funcionalidades.md` Épica 1
  - `knowledge-base/09_decisiones_y_supuestos.md` DD-01, DD-02, DD-03, DD-09, DD-10, DD-17
  - `knowledge-base/05_reglas_de_negocio.md` §Reglas técnicas transversales (Secretos), AP-03, AP-05
- **RN que cubre**: RN-18 (transversal: ningún error devuelve texto interno de la base; acá, que `/health/ready` y el arranque no filtren detalles). Reglas técnicas: Secretos, `SQL_ECHO`, driver asyncpg, lifespan
- **Casos C que cubre**: ninguno directo (soporte de todos)
- **Historias / criterios**: US-001 (config sin secretos por defecto), US-002 (motor y sesiones en el lifespan), US-003 (salud `live`/`ready`). Criterios clave: URL computada con driver async; clave y contraseña sin default; `env.example` sin secretos; pool, bcrypt, `SQL_ECHO` y `Secure` desde la configuración; `get_session` con `expire_on_commit=False`; `ready` 503 si la base no contesta
- **`.http` que le corresponden**: ninguno

---

### [CH-02] `esquema-y-migraciones`
- **Estado**: `[ ]` pendiente
- **Responsable / Ola**: Belén · ola 1 (vie 23 – lun 26/10)
- **Scope**: **único change que escribe los modelos y las migraciones**
  - Los **13 modelos** SQLModel en `app/modules/<mod>/models.py`: `usuarios` → `Usuario`, `AsignacionRol`, `IntentoAcceso`, `EventoSeguridad`; `clientes` → `Cliente`, `Vehiculo`; `repuestos` → `Repuesto`, `MovimientoStock`, `HistorialPrecio`; `ordenes` → `EstadoOrden`, `OrdenTrabajo`, `ItemOrden`, `HistorialEstadoOrden`. Nombres de tablas y columnas **exactos** (los usan los casos y la corrección)
  - Restricciones: `usuario.email` UNIQUE; `cliente.documento` y `cliente.usuario_id` UNIQUE; CHECK `asignacion_rol.rol IN (ADMIN, RECEPCION, MECANICO, CLIENTE)`; CHECK `vehiculo.anio BETWEEN 1950 AND 2100`; CHECKs `repuesto.precio > 0` y `stock >= 0`; `orden_trabajo.estado` y los dos estados del historial como **FK a `estado_orden.codigo`** (no CHECK con lista); CHECK `total >= 0`; `item_orden` UNIQUE `(orden_id, repuesto_id)`, CHECK `cantidad > 0` y `precio_unitario > 0`; CHECK `movimiento_stock.cantidad <> 0`; CHECKs `historial_precio_repuesto.precio_nuevo > 0` y `precio_nuevo <> precio_anterior`
  - Los **tres índices únicos parciales** con `postgresql_where`: `asignacion_rol (usuario_id, rol) WHERE revocada_en IS NULL`, `vehiculo (patente) WHERE borrado_en IS NULL`, `repuesto (codigo) WHERE borrado_en IS NULL`; índice `intento_acceso (email, ip, cuando)`
  - `timestamptz` en todas las fechas; `NUMERIC`/`Decimal` en dinero (`precio` 10,2; `total` 12,2); **índice en cada FK**; relaciones declaradas en los dos extremos de lo que se lee (`Usuario.cliente` devuelve un objeto, no una lista)
  - **Migración 1**: `alembic revision --autogenerate` con todas las tablas (`estado_orden` se crea **vacía**); **Migración 2**: escrita a mano, función + trigger que rechaza `UPDATE`/`DELETE` sobre `historial_estado_orden`, `movimiento_stock` e `historial_precio_repuesto` (RN-15). Cada migración lleva el comentario de que se leyó antes de aplicarla
  - Alembic con plantilla async, `alembic.ini` **sin credenciales** (la URL sale de `Settings`); ciclo `upgrade head` → `downgrade base` → `upgrade head` funcionando
  - `seed.py`: vacía las tablas y carga el **catálogo de estados primero** (PENDIENTE 1, EN_REPARACION 2, TERMINADA 3 final, CANCELADA 4 final), usuarios (`admin@`, `admin2@`, `recepcion@`, `mecanico@`, `mecanico2@`, `cliente@`, `nuevo@example.com` con cambio obligatorio), clientes (Laura con 2 vehículos y usuario; Jorge con 1 sin usuario), repuestos con su movimiento "Stock inicial" (`FIL-001` stock 10 / 8500.00, `FRE-010` stock 4 / 32000.00, bujía stock 2, `ACE-530` stock 20 / 12000.00), orden 1 PENDIENTE y orden 2 EN_REPARACION con **4 bujías cuando hay 2** (para C-11), historial de precio del filtro (8000 → 8500) y evento de seguridad con actor `SISTEMA` ("Carga de los datos iniciales")
  - Belén **define acá** los datos del seed que la consigna no fija (DD-16): patentes, documentos, teléfonos, contraseñas, precio de la bujía. Para no depender de CH-04, `seed.py` calcula los hashes con `bcrypt` directamente
  - **C-14 vive acá**: `test/solo_agregado.sql` con los UPDATE/DELETE de C-14 (seis rechazos del trigger + el de la FK de estado inexistente). CH-02 escribe **y prueba** el trigger y la FK al catálogo (corre el script contra la base migrada y verifica que cada sentencia es rechazada); CH-09 **sólo saca la captura de psql** como evidencia, no escribe ni prueba el trigger
  - Tests: `alembic upgrade head` sobre base vacía; ciclo up/down/up; índices parciales (misma patente/código vigente → error, tras la baja → permitido); el trigger rechaza UPDATE y DELETE sobre las tres tablas (C-14, seis rechazos); FK rechaza un estado fuera del catálogo (C-14, el séptimo rechazo); la base de tests `taller_test` se crea con `alembic upgrade head`
- **Dependencias**: CH-01
- **Governance**: CRITICO (modelos que todo referencia + trigger de inmutabilidad; si `alembic upgrade head` falla, el profesor no corrige)
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` (completo: 13 entidades, ERD, migraciones, seed data)
  - `knowledge-base/05_reglas_de_negocio.md` §Unicidad e integridad (RN-01, RN-15, RN-18), §Reglas técnicas transversales (Esquema, Tipos, Catálogo)
  - `knowledge-base/06_funcionalidades.md` Épica 2
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones (borrado lógico + índice parcial, catálogo con FK, tabla de sólo agregado)
  - `knowledge-base/09_decisiones_y_supuestos.md` DD-03, DD-12, DD-16
- **RN que cubre**: RN-01 (UNIQUE e índices parciales), RN-03 (índice único parcial de `asignacion_rol`), RN-15 (trigger), RN-19 (FK al catálogo `estado_orden`), RN-16 y RN-20 (columnas `borrado_en` y CHECK `precio_nuevo <> precio_anterior`: la lógica la hacen CH-06/CH-07), RN-18 (soporte: la base es quien garantiza la unicidad)
- **Casos C que cubre**: **C-14 completo** (escribe `test/solo_agregado.sql` y prueba el trigger de sólo agregado y la FK de estado; CH-09 sólo saca la captura de psql como evidencia). Soporte de C-02, C-10, C-17, C-18, C-19 (restricciones e índices)
- **Historias / criterios**: US-004 (modelos con restricciones e índices parciales), US-005 (dos migraciones y ciclo up/down/up). Criterios clave: tres índices parciales con `postgresql_where`; estados como FK, no CHECK; navegación en los dos extremos; cada FK con su índice; migración 1 autogenerate con `estado_orden` vacía; migración 2 a mano con el trigger; comentario de lectura previa; `upgrade → downgrade → upgrade`; la base de tests con `alembic upgrade head`
- **`.http` que le corresponden**: `test/solo_agregado.sql` (script del caso C-14; US-023 lo lista bajo CH-09, pero lo escribe y prueba quien escribe el trigger, y CH-09 sólo lo corre en psql y saca la captura). No tiene `.http` porque el trigger no se ejerce por HTTP

---

### [CH-03] `nucleo-repositorios-uow`
- **Estado**: `[ ]` pendiente
- **Responsable / Ola**: Elías · ola 1 (vie 23 – lun 26/10)
- **Scope**: **SÓLO el núcleo genérico de `app/core/`** (DD-12); los repositorios y UoW concretos de cada módulo los escribe el change de ese módulo (ola 2; `ordenes` en ola 3)
  - `app/core/repository.py`: `BaseRepository[T]` (recibe sesión y clase del modelo; `get_by_id`, `get_all`, `count`, `add`, `update`, `delete`; `add`/`update` hacen `flush()`, **nunca** `commit()`) y `SoftDeleteRepository[T]` (hereda; filtra los dados de baja por `borrado_en`; suma `get_by_id_including_deleted` y `soft_delete`)
  - `app/core/unit_of_work.py`: `UnitOfWork` base como gestor de contexto async: confirma al salir del bloque, revierte si sale con excepción, **no cierra la sesión**, único lugar con `commit`; documentar el patrón para los UoW concretos (misma sesión para todos los repositorios del módulo) y la dependencia con la que el router lo construye
  - `app/core/paginacion.py`: utilidades de paginación y envoltorio `{items, total, page, size, pages}` (`page` ≥ 1, `size` 1..100 con 20 por defecto, página inexistente → 422, cero resultados = una página vacía)
  - Convención de precarga: cada método de repositorio declara su propia carga anticipada; la carga perezosa está prohibida
  - Se **prueba con un modelo mínimo de test** definido en `tests/` (no es un modelo de la app; los 13 modelos son de CH-02): add/update con flush sin commit, rollback ante excepción, commit al salir, soft delete (filtra, `get_by_id_including_deleted`), paginación (total, pages, página vacía, 422). Acordar con Belén cómo se crea la tabla efímera del test sin violar la regla de "nunca `create_all`" para el esquema real
  - Tests: `get_by_id` inexistente; `delete` real vs `soft_delete`; el UoW revierte tras una excepción y deja la sesión abierta; `pages` con 0, 1 y N resultados
- **Dependencias**: CH-01 (estructura y pytest). Corre en paralelo con CH-02
- **Governance**: ALTO (de este núcleo dependen todos los módulos; fija dónde se hace el commit)
- **Leer antes**:
  - `knowledge-base/08_arquitectura_propuesta.md` §Patrones aplicados (Repository genérico, Unit of Work, Inyección de dependencias)
  - `knowledge-base/06_funcionalidades.md` Épica 3
  - `knowledge-base/05_reglas_de_negocio.md` §Reglas técnicas transversales (Repos / UoW), AP-04
  - `knowledge-base/09_decisiones_y_supuestos.md` DD-12, DD-13
  - `knowledge-base/07_flujos_principales.md` Flujo 9 (diagrama de secuencia del UoW)
- **RN que cubre**: soporte transversal de RN-02, RN-13, RN-20 (una sola transacción) y RN-16 (borrado lógico); regla técnica AP-04 (el commit sólo lo hace el UoW) y reglas CLAUDE.md #13, #14
- **Casos C que cubre**: ninguno directo (el núcleo no expone endpoints)
- **Historias / criterios**: US-006 (repositorios genéricos), US-007 (Unit of Work). Criterios clave: `add`/`update` con `flush` y sin `commit`; `SoftDeleteRepository` con `get_by_id_including_deleted` y `soft_delete`; el catálogo de estados NO hereda de `BaseRepository` (lo escribe CH-08); UoW confirma/revierte/no cierra la sesión; el router lo construye y el servicio lo abre; paginación con envoltorio estándar
- **`.http` que le corresponden**: ninguno

---

## FASE 2 — Acceso y dominio base: autenticación, roles, clientes y repuestos (Ola 2 · lun 26 – mié 28/10)

> Cuatro changes en paralelo con tres personas: Hernán hace CH-04 y después CH-05; Joaquín CH-06; Bruno CH-07. Cada change escribe **sus** `repository.py`, `unit_of_work.py`, `schemas.py`, `service.py`, `router.py` y sus `.http`. Coordinar el lunes 26: (1) firma de `ClienteRepository` (DD-13), primera tarea de CH-06; (2) firmas de `get_usuario_actual` y `requiere_rol` en `app/core/dependencies.py`, que Hernán sube provisorias como primera tarea de CH-04 (CH-06 y CH-07 dependen sólo de esa tarea; CH-05 las reemplaza por la versión real).

### [CH-04] `autenticacion`
- **Estado**: `[ ]` pendiente
- **Responsable / Ola**: Hernán · ola 2 (lun 26 – mié 28/10)
- **Scope**: registro, login con cookie, logout, identidad y cambio de contraseña
  - **PRIMERA tarea (T1, gate "dependencias provisorias en main")**: subir `get_usuario_actual` y `requiere_rol(*roles)` **provisorios** en `app/core/dependencies.py`, con las firmas definitivas, en un PR chico mergeado el lunes 26 a la mañana. **CH-06 y CH-07 dependen sólo de esta tarea**, no de CH-04 completo. CH-05 los reemplaza/completa con la versión real (roles vigentes en la base, 401/403, cambio obligatorio) sin cambiar las firmas
  - `app/core/security.py`: bcrypt con `asyncio.to_thread` + semáforo (`BCRYPT_MAX_CONCURRENT`), costo desde la config, siempre **antes** de abrir la transacción; emisión y decodificación de JWT (PyJWT) con `sub`, `iat` con fracciones de segundo, `exp` y roles vigentes; clave de firma FIJA desde el `.env`
  - `app/modules/usuarios/{repository,unit_of_work,schemas,service,router}.py` (la parte de autenticación): `UsuarioRepository`, `AsignacionRolRepository`, `IntentoAccesoRepository`; el UoW de `usuarios` importa `ClienteRepository` de `app/modules/clientes/repository.py` (DD-13; dependencia puntual de la 1ª tarea de CH-06, ver Dependencias)
  - `POST /auth/registro` → 201: crea `usuario` + `asignacion_rol` (CLIENTE) + `cliente` en un solo UoW (o las tres filas o ninguna); correo o documento repetido → 409 con mensaje propio (traduciendo el `IntegrityError`), sin filas sueltas; documento que ya es de un cliente del taller → 409 sin apropiarse de la ficha; contrato con `extra="forbid"` (nadie se registra con un rol) y contraseña ≤ 72 **bytes** (422)
  - `POST /auth/login`: primero límite de intentos (5 fallos del par correo+IP en 60 s desde el último éxito → 429 + `Retry-After`, **sin calcular hash**), luego verificación contra el hash real o el ficticio del lifespan (401 con el mismo cuerpo y tiempo parecido exista o no el correo); el JWT viaja sólo en `Set-Cookie: access_token` (HttpOnly, SameSite=Lax, `Max-Age` = duración, `Secure` configurable); cuerpo `{"mensaje": "Sesión iniciada", "debe_cambiar_password": false, "expira_en_segundos": 1800}` sin token; el intento que recibe 429 no suma fila de fallo (SU-02)
  - `intento_acceso` escrito desde una **sesión y transacción PROPIAS** que se confirman siempre, con comentario en el código que declara su costo (deja filas aunque la petición falle); un login correcto reinicia la cuenta (los fallos anteriores siguen en la tabla pero dejan de contar)
  - `POST /auth/logout` → 200: borra la cookie. `GET /auth/yo`: usuario, roles vigentes (de la base) y los que dice el token. `POST /auth/cambiar-password`: verifica la actual, hash nuevo antes de la transacción, en un UoW actualiza `password_hash`, `password_cambiada_en`, `debe_cambiar_password=false` y deja el evento en `evento_seguridad`; emite un token **nuevo** posterior al cambio; contraseñas actual/nueva ≤ 72 bytes (422)
  - Cambio de contraseña: las sesiones anteriores quedan inválidas aunque sean del mismo segundo (comparar `iat` con `password_cambiada_en` **sin truncar**; la validación en cada petición la hace CH-05)
  - Rutas en el grupo abierto de `main.py` (`/auth/*`); ninguna respuesta incluye `password_hash`
  - Tests: registro atómico (rollback si falla el cliente), 409 por correo y por documento, 422 por campo extra y por >72 bytes; login 200 con cookie correcta y sin token en el cuerpo; 401 idéntico (cuerpo) para correo existente/inexistente; sexto intento 429 con `Retry-After`; fallos persistidos en `intento_acceso`; cambio de contraseña con token nuevo válido y anterior inválido
- **Dependencias**: CH-01, CH-02, CH-03. **Dependencia puntual de CH-06** (DD-13), sin depender del change completo: el registro (RN-02) necesita `ClienteRepository` básico, que es la primera tarea de Joaquín; si Hernán llega antes, lo crea con la misma firma y Joaquín lo extiende. **Habilita a otros**: su T1 (dependencias provisorias) es lo único que necesitan CH-06 y CH-07; CH-05 y CH-08 dependen de CH-04 completo
- **Governance**: CRITICO (autenticación, credenciales y sesiones)
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` §Rutas públicas, §Reglas de decisión
  - `knowledge-base/05_reglas_de_negocio.md` §Registro, usuarios y roles (RN-02), §Sesión y contraseñas (RN-07, RN-08, RN-09), §Excepciones globales
  - `knowledge-base/07_flujos_principales.md` Flujo 1 (registro), Flujo 2 (login), Flujo 4 (cambio obligatorio)
  - `knowledge-base/08_arquitectura_propuesta.md` §Seguridad
  - `knowledge-base/09_decisiones_y_supuestos.md` DD-13, SU-02, SU-07
- **RN que cubre**: RN-01 (correo único), RN-02, RN-07 (emisión del token posterior al cambio), RN-08, RN-09, RN-18
- **Casos C que cubre**: C-02, C-03, C-04, C-05; C-01 (transversal: parámetro de ruta no entero con sesión iniciada → 422 sin ejecutar el handler; Hernán escribe el `.http` usando su login, y cada change con rutas `{id}` lo cumple por el contrato de FastAPI); C-09 (parcial: `POST /auth/cambiar-password` y el token nuevo; el caso completo, con el bloqueo 403, lo cierra CH-05)
- **Historias / criterios**: US-008 (registro de cliente), US-009 (login con cookie), US-010 (logout, `/auth/yo` y cambio de contraseña). Criterios clave: tres filas o ninguna; 409 por correo/documento sin filas sueltas; `extra="forbid"` y 72 bytes; hash antes de la transacción; JWT con `sub`/`iat` fraccionario/`exp`/roles; cookie HttpOnly+SameSite=Lax+Max-Age+Secure configurable; 429 sin hash tras 5 fallos; mismo 401 con tiempo parecido; `intento_acceso` en sesión propia; bcrypt con `to_thread` + semáforo; el cambio de contraseña deja evento e invalida sesiones anteriores
- **`.http` que le corresponden** (C-02..C-05 y C-01; C-06 es de CH-08): `test/C-01_*.http`, `test/C-02_*.http`, `test/C-03_*.http`, `test/C-04_*.http`, `test/C-05_*.http`

---

### [CH-05] `autorizacion-y-roles`
- **Estado**: `[ ]` pendiente
- **Responsable / Ola**: Hernán · ola 2 (después de CH-04; lun 26 – mié 28/10)
- **Scope**: usuario actual, roles vigentes, administración de personal y de roles, eventos y control del cambio obligatorio
  - **Reemplaza/completa las dependencias provisorias de CH-04 (T1)** con la versión real, **sin cambiar las firmas** (CH-06 y CH-07 ya las importan): roles vigentes leídos de la base en cada petición, 401/403 por todas las causas y control del cambio obligatorio de contraseña
  - `app/core/dependencies.py`: `get_usuario_actual` (lee **sólo** `request.cookies["access_token"]`, nunca `Authorization`; 401 por cookie ausente, token inválido o vencido, usuario inexistente o inactivo, o `iat` anterior al último `password_cambiada_en`, sin truncar), `requiere_rol(*roles)` (403; consulta `asignacion_rol` vigente —no revocada y sin vencer— en la base **en cada petición**; los roles del token son informativos) y el control del cambio obligatorio de contraseña (`debe_cambiar_password` → 403)
  - `main.py`: el control del cambio obligatorio se monta **UNA sola vez** en el grupo protegido (FastAPI suma dependencias y no las resta); el grupo abierto lleva salud y `/auth/*`. Tras el cambio, la cookie nueva vale y la anterior da 401 sin esperar entre el login y el cambio
  - `POST /usuarios` → 201 (ADMIN): alta de personal con contraseña provisoria y `debe_cambiar_password=true`; 409 correo repetido; 422
  - `GET /usuarios/{id}/roles` → 200/404; `POST /usuarios/{id}/roles` → 201/404/409/422: `vence_en` opcional, debe llegar **con zona horaria y en el futuro** (si no, 422, no 409); reasignar un rol vencido cierra la fila anterior y abre una nueva (índice parcial: una abierta por rol, 409 si ya existe); `DELETE /usuarios/{id}/roles/{rol}` → 200/404/409: escribe `revocada_en`, **no borra la fila**
  - Autoprotección (RN-05): un ADMIN no revoca su propio rol ADMIN y el sistema nunca queda sin administradores vigentes → 409
  - `GET /eventos` (ADMIN, `page`, `size`): historial de `evento_seguridad` paginado. **Hernán define el conjunto fijo de códigos de acción** de `evento_seguridad` (alta de usuario, asignación/revocación de rol, cambio de contraseña, carga inicial…) como constantes/enum que usan CH-04 y el seed; `actor` = **correo del usuario** que ejecuta la acción, o `SISTEMA` (DD-15)
  - Lo propio (`/mis-*`, `/auth/yo`) sólo pide estar autenticado
  - Tests: 401 vs 403 en cada causa; revocar un rol con la sesión abierta → misma cookie, 403 en la petición siguiente; `/auth/yo` muestra roles de la base vs. del token; fila revocada sigue en la tabla; `vence_en` pasado o sin zona → 422; autoprotección 409 (ADMIN solo y último ADMIN); con cambio pendiente el grupo protegido da 403 y `/auth/*` pasa; cookie anterior al cambio → 401
- **Dependencias**: CH-04 **completo** (usa `security.py`/JWT; parte de las dependencias provisorias de su T1); además CH-02, CH-03. CH-06 y CH-07 no esperan a CH-05: usan las provisorias de CH-04 T1, que CH-05 reemplaza con las mismas firmas. **CH-08 depende de CH-04 y CH-05 completos**
- **Governance**: CRITICO (control de acceso, roles y auditoría de seguridad)
- **Leer antes**:
  - `knowledge-base/03_actores_y_roles.md` (completo: matriz RBAC, reglas 401/403)
  - `knowledge-base/05_reglas_de_negocio.md` §Registro, usuarios y roles (RN-03, RN-04, RN-05), §Sesión y contraseñas (RN-06, RN-07), §Acceso a lo propio (RN-17), §Excepciones globales
  - `knowledge-base/07_flujos_principales.md` Flujo 3 (petición autorizada), Flujo 4 (cambio obligatorio), Flujo 5 (asignar y revocar rol)
  - `knowledge-base/06_funcionalidades.md` Épica 5
  - `knowledge-base/09_decisiones_y_supuestos.md` DD-15, SU-05, SU-06
- **RN que cubre**: RN-03, RN-04, RN-05, RN-06, RN-07 (validación en cada petición), RN-17 (parcial: lo propio sólo pide autenticación), RN-01 (correo de personal único), RN-18
- **Casos C que cubre**: C-07, C-08, C-09 (cierre: bloqueo 403 con el cambio pendiente; cookie nueva vale y anterior da 401). **C-06 ya no es de este change**: lo escribe CH-08 (necesita los endpoints de órdenes); CH-05 aporta el mecanismo 401/403 que C-06 ejercita
- **Historias / criterios**: US-011 (usuario actual y `requiere_rol`), US-012 (administración de personal y roles), US-013 (cambio obligatorio con dos grupos de rutas). Criterios clave: la cookie y nunca `Authorization`; 401 por las cuatro causas; 403 consultando la base; alta con contraseña provisoria; `vence_en` con zona y futuro (422); revocar escribe `revocada_en`; reasignar cierra la fila vencida; autoprotección 409; `/eventos` paginado con actor `SISTEMA` para los datos iniciales; control montado una sola vez en el grupo protegido
- **`.http` que le corresponden**: `test/C-07_*.http` (requiere dos sesiones: `# @name` + `# @no-cookie-jar`), `test/C-08_*.http`, `test/C-09_*.http`

---

### [CH-06] `clientes-y-vehiculos`
- **Estado**: `[ ]` pendiente
- **Responsable / Ola**: Joaquín · ola 2 (lun 26 – mié 28/10)
- **Scope**: clientes y vehículos con borrado lógico
  - **PRIMERA tarea (T1, DD-13)**: `ClienteRepository` básico en `app/modules/clientes/repository.py` (hereda de `BaseRepository[Cliente]`), en un PR chico mergeado el lunes 26 para que CH-04 lo importe desde el UoW de `usuarios` (registro, RN-02); firma acordada con Hernán. Si Hernán llega antes y lo crea con la misma firma, Joaquín lo extiende. CH-04 depende sólo de esta tarea, no de CH-06 completo
  - `app/modules/clientes/{repository,unit_of_work,schemas,service,router}.py`: `ClienteRepository` (extendido: `GET` con vehículos y carga anticipada declarada en el método), `VehiculoRepository(SoftDeleteRepository[Vehiculo])` con consulta de "órdenes abiertas" (estado no final según `estado_orden.es_final`, consultando los modelos de CH-02 sin depender del módulo `ordenes`), UoW de `clientes`
  - `POST /clientes` → 201 (RECEPCION, ADMIN); documento repetido → 409 con mensaje propio; contrato con `extra="forbid"`; 422
  - `GET /clientes/{id}` → 200 con el cliente y sus vehículos vigentes; inexistente → 404
  - `POST /clientes/{id}/vehiculos` → 201; patente vigente repetida → 409 (por el `IntegrityError` del índice parcial, sin consulta previa); cliente inexistente → 404; `anio` fuera de 1950..2100 → 422
  - `DELETE /vehiculos/{id}` → 204 (borrado lógico con `borrado_en`); vehículo con órdenes abiertas → 409; inexistente → 404; tras la baja deja de aparecer, no se usa en órdenes nuevas y su patente se puede registrar para otro cliente (201); una segunda patente vigente igual → 409
  - `GET /mis-vehiculos` → 200: sólo los vehículos del cliente vinculado al usuario autenticado (sólo pide autenticación; RN-17)
  - Cablear `requiere_rol(RECEPCION, ADMIN)` y `get_usuario_actual` con las **dependencias provisorias de CH-04 (T1)** ya en `main`; CH-05 las reemplaza con la versión real sin cambiar las firmas, así que no hace falta retocar nada. Sus routers van en el grupo protegido de `main.py`
  - Tests: documento duplicado 409; patente duplicada 409; baja + reuso de patente (C-19); baja con orden abierta 409 (órdenes insertadas directo en `taller_test`); `anio` 1949/2101 → 422; `/mis-vehiculos` sólo devuelve lo propio; id no entero → 422 (C-01)
- **Dependencias**: CH-01, CH-02, CH-03 y **sólo la T1 de CH-04** (dependencias provisorias `requiere_rol` / `get_usuario_actual` en `main`; no espera a CH-04 completo ni a CH-05). **Habilita a CH-04** con su propia T1 (`ClienteRepository`, DD-13), también como dependencia puntual
- **Governance**: MEDIO (lógica de dominio con borrado lógico y unicidad parcial)
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §cliente, §vehiculo
  - `knowledge-base/05_reglas_de_negocio.md` §Unicidad e integridad (RN-01, RN-18), §Repuestos, vehículos y stock (RN-16), §Acceso a lo propio (RN-17)
  - `knowledge-base/07_flujos_principales.md` Flujo 6 (alta/baja de vehículo)
  - `knowledge-base/06_funcionalidades.md` Épica 6
  - `knowledge-base/09_decisiones_y_supuestos.md` DD-13, SU-04
- **RN que cubre**: RN-01 (documento y patente), RN-16 (vehículo), RN-17 (`/mis-vehiculos`), RN-18
- **Casos C que cubre**: C-19; C-01 (parte: sus rutas `{id}` rechazan un id no entero con 422)
- **Historias / criterios**: US-014 (alta y consulta de clientes), US-015 (alta y baja de vehículos), US-016 (mis vehículos). Criterios clave: 201/409/404/422 según la tabla; `GET /clientes/{id}` con vehículos y precarga declarada; baja lógica con 409 si hay órdenes abiertas; misma patente reutilizable tras la baja; vehículo dado de baja no aparece ni se usa en órdenes; `/mis-vehiculos` sólo lo propio
- **`.http` que le corresponden**: `test/C-19_*.http`

---

### [CH-07] `repuestos-y-stock`
- **Estado**: `[ ]` pendiente
- **Responsable / Ola**: Bruno · ola 2 (lun 26 – mié 28/10)
- **Scope**: catálogo de repuestos, reposición y trazabilidad de stock y de precios
  - `app/modules/repuestos/{repository,unit_of_work,schemas,service,router}.py`: `RepuestoRepository(SoftDeleteRepository[Repuesto])` (búsqueda `q` por descripción con **parámetros ligados**, nunca concatenación), repositorios de `MovimientoStock` e `HistorialPrecio` (sólo agregan; sin endpoint de alta propio, AP-01), UoW de `repuestos`
  - **Punto único de escritura de stock (DD-14, RN-14)**: una única función/método del módulo (p. ej. en el servicio de repuestos o su repositorio) que suma o descuenta stock y escribe el `movimiento_stock` en la misma transacción; lo usan alta con `stock_inicial`, `reponer` y, en CH-08, terminar orden. El stock **no** se edita por PATCH
  - `POST /repuestos` (ADMIN) → 201 con `stock_inicial` y un movimiento "Stock inicial"; código vigente repetido → 409; 422
  - `GET /repuestos` (ADMIN, RECEPCION, MECANICO; `q`, `page`, `size`) → envoltorio `{items,total,page,size,pages}`: `' OR '1'='1` → lista vacía con total 0; `q=freno&size=1` → total 1, pages 1; `page=2` → 422; `size=500` → 422. `GET /repuestos/{id}` → 200/404
  - `PATCH /repuestos/{id}` (ADMIN) → 200/404/422: sólo `descripcion` y `precio` con `exclude_unset`; enviar `stock` → 422 (`extra="forbid"`); un cambio de precio escribe una línea en `historial_precio_repuesto` (precio anterior y nuevo) **en la misma transacción**; un PATCH que no cambia el precio no deja línea
  - `DELETE /repuestos/{id}` → 204/404 (borrado lógico). **Sin 409** aunque el repuesto esté en órdenes abiertas (DD-14); el repuesto dado de baja deja de listarse y no se usa en órdenes nuevas, pero conserva sus datos y expone `get_by_id_including_deleted` (heredado de CH-03) para que terminar una orden lo encuentre
  - `POST /repuestos/{id}/reponer` (ADMIN) → 200/404/422: suma stock y deja un movimiento por el punto único de escritura
  - `GET /repuestos/{id}/movimientos` y `GET /repuestos/{id}/precios` (ADMIN; la recepción recibe 403) → 200/404
  - Cablear `requiere_rol` con las **dependencias provisorias de CH-04 (T1)** ya en `main`; CH-05 las reemplaza con la versión real sin cambiar las firmas
  - Tests: alta con movimiento inicial; código duplicado 409; baja + código reutilizable; PATCH de stock 422; PATCH sólo descripción no deja historial; PATCH de precio deja exactamente una línea; reposición suma y registra; inyección SQL como dato; paginación límites; baja sin 409
- **Dependencias**: CH-01, CH-02, CH-03 y **sólo la T1 de CH-04** (dependencias provisorias `requiere_rol` / `get_usuario_actual` en `main`; no espera a CH-04 completo ni a CH-05)
- **Governance**: ALTO (integridad del stock y de las tablas de sólo agregado)
- **Leer antes**:
  - `knowledge-base/04_modelo_de_datos.md` §repuesto, §movimiento_stock, §historial_precio_repuesto
  - `knowledge-base/05_reglas_de_negocio.md` §Repuestos, vehículos y stock (RN-14, RN-16, RN-20), §Unicidad e integridad (RN-01, RN-15), AP-01
  - `knowledge-base/07_flujos_principales.md` Flujo 11 (reponer y cambiar precio)
  - `knowledge-base/06_funcionalidades.md` Épica 7
  - `knowledge-base/09_decisiones_y_supuestos.md` DD-14
- **RN que cubre**: RN-01 (código de repuesto), RN-14, RN-15 (las tablas se escriben sólo agregando), RN-16 (repuesto), RN-18, RN-20
- **Casos C que cubre**: C-16, C-18; C-01 (parte: sus rutas `{id}` rechazan un id no entero con 422)
- **Historias / criterios**: US-017 (catálogo de repuestos), US-018 (búsqueda y listado), US-019 (reposición y trazabilidad de stock). Criterios clave: alta con movimiento "Stock inicial"; PATCH parcial con `exclude_unset` y 422 por `stock`; línea de historial de precio sólo si cambia el precio, misma transacción; baja lógica sin 409; búsqueda con parámetros ligados y paginación con 422 fuera de rango; reposición y consultas de ADMIN; ningún alta propia de movimientos ni de historial
- **`.http` que le corresponden**: `test/C-16_*.http`, `test/C-18_*.http` (C-18 usa sesión de ADMIN y de RECEPCION: `# @name` + `# @no-cookie-jar`)

---

## FASE 3 — Núcleo de negocio: órdenes de trabajo (Ola 3 · mié 28 – jue 29/10)

> Un solo change, y está en el camino crítico. Elías prepara desde la ola 2 (`/opsx:explore`, lectura de los flujos 7-10 y 12) pero no mergea hasta que CH-04 y CH-05 (completos), CH-06 y CH-07 estén en `main`.

### [CH-08] `ordenes`
- **Estado**: `[ ]` pendiente
- **Responsable / Ola**: Elías · ola 3 (mié 28 – jue 29/10)
- **Scope**: ciclo de vida de la orden de trabajo, catálogo de estados y consultas sin N+1
  - `app/modules/ordenes/{repository,unit_of_work,schemas,service,router}.py`: `OrdenRepository` (detalle con **carga anticipada declarada dentro del método**: vehículo, cliente, ítems, repuesto de cada ítem e historial con `selectinload`/`joinedload`; número de consultas fijo, igual con 2 que con 4 ítems), `HistorialEstadoOrdenRepository` (sólo agrega), `EstadoOrdenRepository` **de sólo lectura que NO hereda de `BaseRepository`** (PK `codigo`), UoW de `ordenes` que reúne esos repositorios y los de stock/vehículos que necesite con la misma sesión
  - `POST /ordenes` (RECEPCION, ADMIN) → 201: nace PENDIENTE con ≥ 1 ítem y sin repuestos repetidos; precio copiado del repuesto vigente y total calculado por el servidor en `Decimal`; escribe orden, ítems y primera línea de historial (`desde_estado` nulo → PENDIENTE) en un solo bloque; vehículo dado de baja o repuesto inexistente/dado de baja → 409 y la orden no queda creada; catálogo vacío → 409 con mensaje propio; el cuerpo no acepta precio, total, estado ni fecha (422, `extra="forbid"`); respuesta con `estado`, `patente`, `total`, `creada_en`, `mecanico_id`, `falla`, `cliente`, `items` (`codigo`, `descripcion`, `precio_unitario`, `subtotal`) e `historial`
  - `GET /ordenes` (RECEPCION, ADMIN, MECANICO; `estado`, `page`, `size`): `estado` declarado como enum (uno no declarado → 422); `GET /ordenes/{id}`: personal o dueño del vehículo (cliente ajeno → 403, inexistente → 404); `GET /mis-ordenes` paginado (sólo pide autenticación; órdenes de los vehículos del cliente, RN-17); `GET /estados-orden` (autenticado) devuelve los cuatro estados por posición con TERMINADA y CANCELADA finales — **sin endpoints de crear, editar ni borrar** estados (AP-02); el enum del código coincide con el catálogo
  - `POST /ordenes/{id}/iniciar` → 200/404/409: **sólo MECANICO** (`requiere_rol(MECANICO)`; un ADMIN sin ese rol no inicia, SU-03); PENDIENTE → EN_REPARACION, queda asignado como `mecanico_id`; otro estado → 409
  - `POST /ordenes/{id}/terminar` → 200/403/404/409: el mecánico asignado o un ADMIN (el permiso se decide **antes** que el estado). En **UN solo UoW**: descuenta stock por el punto único de escritura de CH-07 (una escritura por ítem), un `movimiento_stock` por cada salida, pasa a TERMINADA y agrega la línea de historial; **busca el repuesto de cada ítem con `get_by_id_including_deleted`** (DD-14: se puede terminar una orden cuyo repuesto fue dado de baja); si un repuesto no alcanza → 409 con rollback total (estado, stock, movimientos e historial como estaban); agenda con `BackgroundTasks` el aviso simulado (`await asyncio.sleep(0.5)` + mensaje en el registro) que corre **después** de la respuesta y **sólo si** se confirmó
  - `POST /ordenes/{id}/cancelar` → 200/403/404/409: RECEPCION, ADMIN o el dueño del vehículo; la ruta **no** lleva `requiere_rol` (decide el servicio); el permiso (403) se evalúa **antes** que el estado (409); sólo PENDIENTE → CANCELADA; terminada → 409; agrega línea de historial
  - Cablear `requiere_rol`/`get_usuario_actual` **reales** de CH-05 (ya en `main`, con CH-04 completo); routers en el grupo protegido
  - **C-06 completo vive acá** (necesita estos endpoints): sin cookie → 401; con sesión pero sin el rol → 403 (401 contra 403); lo propio sin rol (`/mis-ordenes`, `/auth/yo`) → 200; el cliente ve su orden (`GET /ordenes/{id}` → 200) y no la ajena (→ 403)
  - Tests: crear con dos ítems (precios copiados, total, historial) y con repuesto inexistente (409, nada creado); iniciar sólo MECANICO y estado inválido 409; terminar con stock insuficiente (la orden 2 del seed pide 4 bujías con 2 en stock → 409 y nada cambia), reponer y terminar OK, aviso agendado sólo tras commit, repuesto dado de baja igual se termina; cancelar por dueño/recepción/ADMIN, ajena 403, terminada 409 (403 antes que 409); detalle con 2 vs 4 ítems ⇒ misma cantidad de consultas; filtro `estado` inválido 422; `/estados-orden` por posición; C-06 (401 sin cookie, 403 sin rol, cliente 200 en su orden y 403 en la ajena, `/mis-ordenes` sin rol 200)
- **Dependencias**: **CH-04 y CH-05 completos**, CH-06, CH-07 (y la ola 1 completa)
- **Governance**: ALTO (máquina de estados y transacción multi-tabla que toca stock)
- **Leer antes**:
  - `knowledge-base/07_flujos_principales.md` Flujos 7, 8, 9, 10 y 12 (crear, iniciar, terminar, cancelar, detalle sin N+1)
  - `knowledge-base/05_reglas_de_negocio.md` §Órdenes de trabajo (RN-10, RN-11, RN-12, RN-13, RN-19), RN-14, RN-17
  - `knowledge-base/03_actores_y_roles.md` §RBAC — Matriz de permisos, §Reglas de decisión
  - `knowledge-base/06_funcionalidades.md` Épica 8
  - `knowledge-base/09_decisiones_y_supuestos.md` DD-14, SU-03
- **RN que cubre**: RN-10, RN-11, RN-12, RN-13, RN-19; usa RN-14 (punto único de stock), RN-15 (historial y movimientos sólo se agregan), RN-16 (vehículo/repuesto de baja no se usan en órdenes nuevas), RN-17 (dueño del vehículo), RN-18
- **Casos C que cubre**: C-10, C-11, C-12, C-13, C-15 (el `.http` y las consultas; la evidencia de consola la saca CH-09), C-17, **C-06 completo** (401 contra 403, lo propio sin rol, el cliente ve su orden y no la ajena); C-01 (parte: sus rutas `{id}` rechazan un id no entero con 422)
- **Historias / criterios**: US-020 (crear una orden), US-021 (iniciar, terminar y cancelar), US-022 (consultar órdenes sin N+1). Criterios clave: nace PENDIENTE sin repetidos, precio copiado y total del servidor; un solo bloque con 409 sin dejar la orden; catálogo vacío 409; solo MECANICO inicia; terminar descuenta stock, un movimiento por ítem y una línea de historial en un UoW, 409 con rollback total, `BackgroundTasks` después de la respuesta y sólo si se confirmó; cancelar con 403 antes que 409; detalle con consultas fijas (2 ítems = 4 ítems); `estado` inválido 422; `/mis-ordenes` paginado; `/estados-orden` por posición
- **`.http` que le corresponden**: `test/C-10_*.http`, `test/C-11_*.http`, `test/C-12_*.http`, `test/C-13_*.http`, `test/C-15_*.http`, `test/C-17_*.http` y `test/C-06_*.http` completo (401 contra 403, lo propio, cliente ve su orden / no la ajena; requiere dos sesiones: `# @name` + `# @no-cookie-jar`)

---

## FASE 4 — Cierre: consolidación, evidencias y entrega (Ola 4 · jue 29 – vie 30/10 a la mañana)

### [CH-09] `casos-y-entrega`
- **Estado**: `[ ]` pendiente
- **Responsable / Ola**: Belén · ola 4 (jue 29 – vie 30/10 a la mañana)
- **Scope**: **SÓLO consolida, corre todo y saca las evidencias** (DD-07, DD-16); cada integrante ya escribió los `.http` de sus casos en su propio change
  - Consolidar `test/` y verificar que existe un `.http` por cada caso **C-01..C-19**, cada uno con la respuesta esperada en un comentario; correr `python seed.py` antes de cada archivo y ejecutar los 19 contra el servidor; reportar a su dueño cualquier caso que falle (no reescribirlos)
  - **Evidencia C-14** (el script, el trigger y la FK los escribe y prueba CH-02; acá **sólo se saca la captura de psql**, no se escribe ni se prueba el trigger): ejecutar `test/solo_agregado.sql` en psql y capturar los **seis rechazos del trigger** (UPDATE y DELETE sobre `historial_estado_orden`, `movimiento_stock`, `historial_precio_repuesto`) y el rechazo de la **clave foránea** del estado inexistente
  - **Evidencia C-15**: con `SQL_ECHO=true`, capturar la consola con las consultas del detalle de una orden con **2 ítems** y de otra con **4 ítems** (misma cantidad)
  - `README.md` con los pasos de arranque desde cero: venv, `pip install -r requirements.txt`, crear las dos bases (desarrollo y `taller_test`) en el PostgreSQL 16+ local (sin Docker), copiar `env.example` a `.env` con cómo generar la clave de firma FIJA, `alembic upgrade head` (y verificar `downgrade base` + `upgrade head`), `python seed.py`, levantar el servidor, `SQL_ECHO=true`; explicar `tests/` (pytest) vs `test/` (`.http` y SQL) y cómo correr los tests
  - Verificar que están `requirements.txt`, `env.example`, `alembic.ini` (sin credenciales), `migrations/` (2 versiones) y `test/`; que desde un clon limpio todo levanta con esos pasos
  - Revisar `docs/bitacora.md`: una sección por integrante con fecha, qué pidió al agente, qué corrigió a mano y por qué; revisar que cada PR tiene su aprobación (evidencia para la demo en vivo, AP-07); recorrer las RN-01..RN-20 contra el código como lista de verificación final
  - Tests: correr toda la suite `pytest` (verde) sobre `taller_test` creada con `alembic upgrade head`
- **Dependencias**: CH-08 (y por transitividad todo lo anterior)
- **Governance**: BAJO (consolidación y documentación; no escribe lógica nueva)
- **Leer antes**:
  - `knowledge-base/06_funcionalidades.md` Épica 9 (US-023)
  - `knowledge-base/07_flujos_principales.md` Flujo 13 (puesta en marcha desde cero)
  - `knowledge-base/09_decisiones_y_supuestos.md` DD-07, DD-08, DD-16, DD-17, DD-18
  - `knowledge-base/01_vision_y_objetivos.md` §criterios de evaluación
  - `knowledge-base/05_reglas_de_negocio.md` AP-06, AP-07
- **RN que cubre**: ninguna nueva; verifica **RN-01..RN-20** de punta a punta (RN-15 con la evidencia de C-14; RN-19 y el diseño sin N+1 con la evidencia de C-15)
- **Casos C que cubre**: consolida y ejecuta **C-01..C-19**; saca las evidencias de **C-14** (sólo la captura de psql; el caso es de CH-02) y **C-15** (consola; el caso es de CH-08)
- **Historias / criterios**: US-023 (seed, casos .http y evidencias). Criterios clave: `seed.py` vacía y carga con el catálogo primero; `.http` para C-01..C-19 con la respuesta esperada en comentario; `test/solo_agregado.sql` (de CH-02) con la captura de psql como evidencia (seis rechazos + la FK); evidencia de C-15 con 2 y 4 ítems; `requirements.txt`, `env.example`, `alembic.ini`, `migrations/`, `test/` y README con pasos de arranque desde cero; bitácora y PRs con revisión como evidencia del trabajo de los 5
- **`.http` que le corresponden**: ninguno propio (sólo consolida los de CH-04..CH-08 y `test/solo_agregado.sql` de CH-02)
