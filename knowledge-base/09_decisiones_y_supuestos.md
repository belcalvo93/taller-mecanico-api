# Decisiones y Supuestos

## Decisiones documentadas

### DD-01 — Driver asyncpg
**Decisión**: usar `postgresql+asyncpg` (asyncpg 0.30).
**Contexto**: la consigna acepta asyncpg o psycopg 3 async.
**Alternativas consideradas**: psycopg 3 async.
**Justificación**: `CLAUDE.md` ya lo fija y el equipo lo confirmó en el Discovery.
**Trade-offs aceptados**: ninguno relevante para el alcance del TP.

### DD-02 — PostgreSQL local, sin Docker
**Decisión**: cada integrante usa PostgreSQL 16 o superior instalado localmente (el de Belén es 17); sin Docker.
**Contexto**: el TP exige PostgreSQL 16 y los tests corren contra una base real.
**Alternativas consideradas**: Docker Compose con Postgres 16; que cada uno use lo que quiera.
**Justificación**: simplicidad; la consigna no lo pide y el alcance es "estrictamente la consigna".
**Trade-offs aceptados**: diferencias menores entre máquinas; el README debe explicar cómo crear las dos bases (desarrollo y `taller_test`).

### DD-03 — Base de tests separada, creada con Alembic
**Decisión**: los tests usan otra base del mismo servidor y la crean con `alembic upgrade head`.
**Contexto**: la consigna prohíbe `create_all` y exige que el esquema salga de las migraciones.
**Justificación**: así los tests también verifican las migraciones y el trigger.
**Trade-offs aceptados**: la suite es más lenta que con SQLite o `create_all`.

### DD-04 — Alcance estrictamente la consigna
**Decisión**: sin Docker, CI, linter ni funcionalidades extra.
**Contexto**: una semana de plazo y una demo en vivo donde cada uno explica lo suyo.
**Justificación**: priorizar lo que puntúa y poder explicar todo el código.
**Trade-offs aceptados**: sin automatización de PRs ni chequeos de estilo.

### DD-05 — Conservar los códigos RN-01..RN-20 de la consigna
**Decisión**: no renombrar las reglas al formato `RN-{DOMINIO}-{NN}`.
**Contexto**: la corrección y el flujo de trabajo citan "cada regla RN y cada caso C".
**Justificación**: trazabilidad directa con la consigna.
**Trade-offs aceptados**: las reglas se agrupan por dominio en el texto, no en el código.

### DD-06 — Reparto del equipo en 9 changes y 4 olas
**Decisión**:

| Ola | Change | Responsable |
|---|---|---|
| 1 | infra-base | Belén |
| 1 | esquema-y-migraciones | Belén |
| 1 | nucleo-repositorios-uow | Elías |
| 2 | autenticacion | Hernán |
| 2 | autorizacion-y-roles | Hernán |
| 2 | clientes-y-vehiculos | Joaquín |
| 2 | repuestos-y-stock | Bruno |
| 3 | ordenes | Elías |
| 4 | casos-y-entrega | Belén |

**Contexto**: 5 integrantes, 3 clases de trabajo (23/10, 27/10, 30/10) y entrega el 30/10/2026.
**Justificación**: paralelizar al máximo respetando dependencias; `ordenes` depende de autenticación, clientes y repuestos.
**Trade-offs aceptados**: `ordenes` queda en el camino crítico.

### DD-07 — Cierre de la entrega dentro de `casos-y-entrega`
**Decisión**: README, evidencias C-14 y C-15 y consolidación de los `.http` van en el último change; cada integrante escribe los `.http` de sus casos en su propio change.
**Justificación**: reparte la escritura de casos y concentra el cierre en una sola persona.
**Trade-offs aceptados**: la ola 4 es un cuello de botella al final.

### DD-08 — Revisión por pares obligatoria
**Decisión**: cada PR necesita la aprobación de al menos un compañero antes del merge.
**Justificación**: la demo en vivo exige evidencia de que los 5 trabajaron y revisaron.

### DD-09 — Carpeta `tests/` para pytest (APROBADA)
**Decisión**: usar `tests/` para la suite pytest, separada de `test/` (reservada por la consigna a `.http` y `solo_agregado.sql`).
**Justificación**: evitar mezclar casos manuales con tests automatizados.
**Trade-offs aceptados**: dos carpetas de nombre parecido; hay que explicarlo en el README.

### DD-10 — Nombres propios de variables de entorno no fijadas por la consigna (APROBADA)
**Decisión**: la consigna fija sólo `POSTGRES_*` y `SQL_ECHO` (o equivalente); el equipo usa `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_SECONDS`, `COOKIE_SECURE`, `BCRYPT_COST`, `BCRYPT_MAX_CONCURRENT`, `DB_POOL_SIZE`.
**Justificación**: completar la configuración exigida (costo de bcrypt y pool "declarados en la configuración") con nombres consistentes.
**Trade-offs aceptados**: si el profesor prefiere otros nombres, se renombran en `Settings` y `env.example`.

### DD-11 — CLAUDE.md manda sobre el stack, la consigna manda sobre todo lo demás
**Decisión**: ante contradicción entre `CLAUDE.md` y la consigna, manda la consigna; en el stack, `CLAUDE.md` elige entre lo que la consigna acepta.
**Justificación**: lo establece `CLAUDE.md` y el equipo lo confirmó.

### DD-12 — `nucleo-repositorios-uow` es sólo el núcleo genérico (resuelve IN-01)
**Decisión**: `nucleo-repositorios-uow` (Elías) cubre únicamente `app/core/`: `BaseRepository[T]`, `SoftDeleteRepository[T]`, `UnitOfWork` base y `paginacion.py`, probados con un modelo mínimo de test. Los repositorios y UoW concretos de cada módulo los escribe el change de ese módulo, en la ola 2 (o en la 3 para `ordenes`).
**Contexto**: los modelos los escribe sólo `esquema-y-migraciones` (Belén) y corre en la misma ola 1.
**Alternativas consideradas**: que Elías espere los modelos de Belén; que Elías escriba también los repositorios concretos.
**Justificación**: Belén y Elías trabajan en paralelo en la ola 1 sin bloquearse.
**Trade-offs aceptados**: los changes de la ola 2 asumen también la escritura de los repositorios y UoW de su módulo.

### DD-13 — `ClienteRepository` compartido entre `usuarios` y `clientes`
**Decisión**: el UoW de `usuarios` importa `ClienteRepository` desde `app/modules/clientes/repository.py` (necesario para el registro, RN-02). `ClienteRepository` básico (hereda de `BaseRepository[Cliente]`) lo crea Joaquín como PRIMERA tarea de `clientes-y-vehiculos`, y Hernán lo usa. Si Hernán llega antes, lo crea él con esa misma firma y Joaquín lo extiende.
**Contexto**: `autenticacion` (Hernán) y `clientes-y-vehiculos` (Joaquín) corren en paralelo en la ola 2.
**Justificación**: evita duplicar el repositorio y deja una firma única acordada.
**Trade-offs aceptados**: acoplamiento entre los dos changes en esa primera tarea; coordinar al arrancar la ola 2.

### DD-14 — Baja de repuesto sin 409 (resuelve IN-03)
**Decisión**: `DELETE /repuestos/{id}` no devuelve 409 aunque el repuesto esté en órdenes abiertas (como pide la tabla de endpoints). Terminar una orden busca el repuesto de cada ítem con `get_by_id_including_deleted`.
**Justificación**: respetar la tabla de la consigna sin dejar órdenes abiertas imposibles de terminar.
**Trade-offs aceptados**: se puede terminar una orden cuyo repuesto fue dado de baja.

### DD-15 — Convención de `evento_seguridad` (resuelve IN-04 / SU-06)
**Decisión**: `actor` = correo del usuario que ejecuta la acción, o `SISTEMA` en el seed. Las acciones son un conjunto fijo de códigos que define Hernán en `autorizacion-y-roles`.
**Justificación**: una convención única para todos los módulos que registran eventos.

### DD-16 — Reparto de `.http` y del seed
**Decisión**: cada integrante escribe en su change los `.http` de sus casos C; `casos-y-entrega` sólo consolida, corre todo y saca las evidencias. Los datos del seed que la consigna no fija (patentes, documentos, teléfonos, contraseñas, precio de la bujía) los define Belén en `esquema-y-migraciones`.

### DD-17 — Bitácora del equipo
**Decisión**: `docs/bitacora.md`, con una sección por integrante y, por entrada: fecha, qué le pidió al agente, qué corrigió a mano y por qué.
**Justificación**: evidencia del trabajo individual para la demo en vivo (AP-07).

### DD-18 — Calendario
**Decisión**:

| Etapa | Fechas |
|---|---|
| Fundación (discovery, KB, roadmap, skills, `CLAUDE.md`) | termina hoy, viernes 23/10 |
| Ola 1 | viernes 23 a lunes 26/10 |
| Ola 2 | lunes 26 a miércoles 28/10 |
| Ola 3 | miércoles 28 y jueves 29/10 |
| Ola 4 | jueves 29 y viernes 30/10 a la mañana |

**Contexto**: entrega el viernes 30/10/2026; clases de trabajo el 23/10, 27/10 y 30/10.
**Trade-offs aceptados**: la ola 3 (`ordenes`) y la 4 quedan al final; cualquier atraso de la ola 2 se come el margen de la entrega.

## Supuestos inferidos

### SU-01 — Las olas son sólo los changes de implementación
**Supuesto**: la fundación (discovery, knowledge-base, roadmap, skills, `CLAUDE.md`) va antes de la ola 1.
**Origen**: confirmación del usuario en el Discovery.
**Riesgo si es falso**: el calendario de 3 clases se queda corto.
**Cómo validar**: revisar con el equipo cuántas sesiones de trabajo consume la fundación.
**Estado**: CONFIRMADO. La fundación termina hoy (viernes 23/10); ver DD-18.

### SU-02 — Un intento bloqueado por 429 no se registra como fallo
**Supuesto**: el sexto intento (que recibe 429) no suma una fila fallida; en C-05 "los cinco fallos están en `intento_acceso`".
**Origen**: C-05 y RN-08 de la consigna.
**Riesgo si es falso**: el conteo y el caso C-05 quedan desfasados.
**Cómo validar**: consultar al profesor o dejar la decisión documentada en el código.
**Estado**: CONFIRMADO. El intento que recibe 429 no suma fila de fallo.

### SU-03 — Sólo MECANICO inicia una orden
**Supuesto**: `iniciar` lleva `requiere_rol(MECANICO)`; un ADMIN sin rol MECANICO no puede iniciar.
**Origen**: tabla de endpoints ("MECANICO") y RN-11 ("la inicia un mecánico, que queda asignado").
**Riesgo si es falso**: un administrador necesitaría destrabar una orden y no podría.
**Cómo validar**: confirmar con el profesor; el usuario ADMIN del seed no es mecánico.
**Estado**: CONFIRMADO. Sólo MECANICO inicia (se respeta la tabla de endpoints).

### SU-04 — `GET /clientes/{id}` y rutas de personal usan 404 para inexistentes aun siendo ajenos
**Supuesto**: los códigos de la tabla son completos; donde no figura 403 (por ejemplo `GET /clientes/{id}`) el control es sólo por rol.
**Origen**: tabla de endpoints de la consigna.
**Riesgo si es falso**: un código no previsto en un caso de prueba.
**Cómo validar**: recorrer los casos C-01..C-19 con la tabla.

### SU-05 — `/auth/yo` y `/auth/cambiar-password` están en el grupo abierto aunque exigen sesión
**Supuesto**: "Abierto" significa "sin el control del cambio obligatorio"; ambas rutas igual dan 401 sin cookie.
**Origen**: tabla de endpoints y RN-06.
**Riesgo si es falso**: un usuario con cambio pendiente no podría cambiar su contraseña.
**Cómo validar**: caso C-09.

### SU-06 — El `actor` de `evento_seguridad` es el correo del usuario (o `SISTEMA`)
**Supuesto**: la consigna sólo fija que `actor` es texto y que el seed usa `SISTEMA`; para las acciones reales se usa el correo del actor.
**Origen**: Ejercicio 5 y modelo de dominio.
**Riesgo si es falso**: inconsistencia al listar `/eventos`.
**Cómo validar**: decidirlo en el change `autorizacion-y-roles`.
**Estado**: CONFIRMADO; ver DD-15.

### SU-07 — La duración del token es 1800 s
**Supuesto**: `expira_en_segundos` del ejemplo de la consigna (1800) es el valor por defecto de la configuración.
**Origen**: respuesta de ejemplo del login.
**Riesgo si es falso**: ninguno funcional; sólo cambia la configuración.
**Cómo validar**: `env.example`.
