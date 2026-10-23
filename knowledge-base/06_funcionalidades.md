# Funcionalidades

Organizadas por **épica** y luego por historia de usuario (US-NNN). Cada épica corresponde a un change del roadmap, con su responsable y su ola (reparto decidido en el Discovery). Los criterios de aceptación salen de los ejercicios, las RN y los casos C de la consigna.

| Épica | Change | Responsable | Ola |
|---|---|---|---|
| 1 | infra-base | Belén | 1 |
| 2 | esquema-y-migraciones | Belén | 1 |
| 3 | nucleo-repositorios-uow | Elías | 1 |
| 4 | autenticacion | Hernán | 2 |
| 5 | autorizacion-y-roles | Hernán | 2 |
| 6 | clientes-y-vehiculos | Joaquín | 2 |
| 7 | repuestos-y-stock | Bruno | 2 |
| 8 | ordenes | Elías | 3 |
| 9 | casos-y-entrega | Belén | 4 |

## Épica 1: Proyecto, configuración y ciclo de vida (Ejercicio 1 — 8 %)

### US-001 — Configuración sin secretos por defecto
**Como** integrante del equipo
**Quiero** que `Settings` (pydantic-settings) lea el entorno o un `.env` no versionado
**Para** no tener credenciales en el repositorio

**Criterios de aceptación**:
- [ ] La URL de la base se arma con `@computed_field` desde `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT` con driver async
- [ ] La clave de firma y la contraseña de la base no tienen valor por defecto: si faltan, la app no arranca
- [ ] Existe `env.example` con todas las variables y ningún secreto; `.env` no se versiona
- [ ] Pool, costo de bcrypt, `SQL_ECHO` y `Secure` de la cookie salen de la configuración

**Reglas relacionadas**: AP-03, AP-05, CLAUDE.md #8

### US-002 — Motor y sesiones en el lifespan
**Como** desarrollador
**Quiero** que motor y fábrica de sesiones se creen en el lifespan y vivan en `app.state`
**Para** no crear recursos al importar un módulo

**Criterios de aceptación**:
- [ ] `get_session` toma la fábrica de `app.state`, entrega una sesión por petición con `expire_on_commit=False` y la cierra al terminar
- [ ] El lifespan calcula una vez el hash ficticio del login y hace `dispose()` al apagar

### US-003 — Salud
**Como** operador
**Quiero** `GET /health/live` y `GET /health/ready`
**Para** saber si el proceso y la base responden

**Criterios de aceptación**:
- [ ] `live` responde 200 sin tocar la base
- [ ] `ready` ejecuta `SELECT 1` y responde 503 si la base no contesta

## Épica 2: Modelos, relaciones y migraciones (Ejercicio 2 — 14 %)

### US-004 — Modelos con restricciones e índices parciales
**Como** equipo
**Quiero** los 13 modelos con sus nombres y restricciones exactos
**Para** que los casos de prueba y la corrección funcionen

**Criterios de aceptación**:
- [ ] Los tres índices únicos parciales usan `postgresql_where` (asignacion_rol, vehiculo.patente, repuesto.codigo)
- [ ] El estado de la orden y los del historial son FK al catálogo, no CHECK con lista
- [ ] Navegación declarada en los dos extremos de cada relación que se lea; `Usuario.cliente` devuelve un objeto
- [ ] Cada FK con su índice; timestamptz y NUMERIC en todos los lugares que corresponde

**Reglas relacionadas**: RN-01, RN-03, RN-19

### US-005 — Dos migraciones y ciclo up/down/up
**Como** equipo
**Quiero** una migración autogenerada y una escrita a mano con el trigger
**Para** que `alembic upgrade head` cree el esquema completo sobre una base vacía

**Criterios de aceptación**:
- [ ] Migración 1 con `--autogenerate` y todas las tablas, con `estado_orden` vacía
- [ ] Migración 2 a mano con el trigger de sólo agregado sobre las tres tablas
- [ ] Cada migración lleva el comentario de que se leyó antes de aplicarla
- [ ] `upgrade head` → `downgrade base` → `upgrade head` funciona
- [ ] La base de tests se crea con `alembic upgrade head` (nunca `create_all`)

**Reglas relacionadas**: RN-15

## Épica 3: Repositorios y Unit of Work (Ejercicio 6 — 20 %)

### US-006 — Repositorios genéricos
**Como** desarrollador
**Quiero** `BaseRepository[T]` y `SoftDeleteRepository[T]`
**Para** reutilizar el acceso a datos en todos los módulos

**Criterios de aceptación**:
- [ ] `BaseRepository[T]` recibe sesión y clase del modelo; ofrece `get_by_id`, `get_all`, `count`, `add`, `update`, `delete`
- [ ] `add` y `update` hacen `flush()`, nunca `commit()`
- [ ] `SoftDeleteRepository[T]` hereda, filtra los dados de baja y suma `get_by_id_including_deleted` y `soft_delete`
- [ ] El repositorio del catálogo es de sólo lectura y NO hereda de `BaseRepository`
- [ ] Cada método declara su propia precarga; la carga perezosa está prohibida

### US-007 — Unit of Work
**Como** desarrollador
**Quiero** un `UnitOfWork` base como gestor de contexto async
**Para** que sólo él confirme o revierta la transacción

**Criterios de aceptación**:
- [ ] Confirma al salir del bloque, revierte si sale con excepción, no cierra la sesión
- [ ] Alcance de este change: sólo el núcleo genérico de `app/core/`, probado con un modelo mínimo de test (DD-12); el UoW concreto de cada módulo, con sus repositorios y la misma sesión, lo escribe el change de ese módulo
- [ ] El router lo construye con una dependencia; el servicio lo abre con `async with` y nunca lo construye
- [ ] Utilidades de paginación (`app/core/paginacion.py`) con el envoltorio `{items, total, page, size, pages}`

**Reglas relacionadas**: AP-04, CLAUDE.md #13, #14

## Épica 4: Autenticación (Ejercicio 4 — 16 %)

### US-008 — Registro de cliente
**Como** cliente
**Quiero** registrarme yo mismo
**Para** consultar mis vehículos y órdenes

**Criterios de aceptación**:
- [ ] Crea usuario, rol CLIENTE y ficha de cliente en un solo UoW; o quedan las tres filas o ninguna
- [ ] Correo o documento repetido → 409 con mensaje propio y sin filas sueltas
- [ ] Documento ya perteneciente a un cliente del taller → 409; no se apropia de la ficha
- [ ] El contrato rechaza campos no declarados (nadie se registra con un rol) y limita la contraseña a 72 bytes (422)
- [ ] El hash se calcula antes de abrir la transacción

**Reglas relacionadas**: RN-01, RN-02, RN-18 — casos C-02

### US-009 — Login con cookie
**Como** usuario
**Quiero** iniciar sesión
**Para** operar según mis roles

**Criterios de aceptación**:
- [ ] El JWT lleva `sub`, `iat` con fracciones de segundo, `exp` y los roles vigentes
- [ ] Viaja sólo en `Set-Cookie` `access_token` con HttpOnly, SameSite=Lax, Max-Age = duración y Secure configurable; el cuerpo no trae el token
- [ ] Orden: límite de intentos (429 + Retry-After, sin hash) → verificación contra hash real o ficticio
- [ ] Correo existente con mala contraseña y correo inexistente → 401 con el mismo cuerpo y tiempo parecido
- [ ] Seis fallos seguidos → el sexto es 429 en pocos milisegundos; los cinco fallos quedan en `intento_acceso`
- [ ] `intento_acceso` se escribe en sesión y transacción PROPIAS, con comentario que declare su costo
- [ ] bcrypt con `asyncio.to_thread` + semáforo, costo desde la config

**Reglas relacionadas**: RN-08, RN-09 — casos C-03, C-04, C-05

### US-010 — Logout, `/auth/yo` y cambio de contraseña
**Como** usuario
**Quiero** cerrar sesión, ver mi identidad y cambiar mi contraseña
**Para** controlar mi sesión

**Criterios de aceptación**:
- [ ] Logout borra la cookie
- [ ] `GET /auth/yo` devuelve usuario, roles vigentes y los que dice el token
- [ ] El cambio de contraseña anota `password_cambiada_en`, emite un token nuevo que vale y deja inválidas las sesiones anteriores, aunque sean del mismo segundo
- [ ] Contraseña actual y nueva limitadas a 72 bytes (422)
- [ ] El cambio queda registrado en `evento_seguridad`

**Reglas relacionadas**: RN-07 — caso C-09

## Épica 5: Autorización y roles (Ejercicio 5 — 14 %)

### US-011 — Usuario actual y `requiere_rol`
**Como** sistema
**Quiero** distinguir 401 de 403 consultando la base en cada petición
**Para** que revocar un rol surta efecto de inmediato

**Criterios de aceptación**:
- [ ] `get_usuario_actual` lee la cookie (nunca `Authorization`) y da 401 por cookie ausente, token inválido/vencido, usuario inexistente o inactivo, o token anterior al último cambio de contraseña
- [ ] `requiere_rol` da 403 y consulta `asignacion_rol` vigente en la base
- [ ] Lo propio (`/mis-*`, `/auth/yo`) sólo pide estar autenticado

**Reglas relacionadas**: RN-04, RN-07, RN-17 — casos C-06, C-07

### US-012 — Administración de personal y roles
**Como** administrador
**Quiero** dar de alta personal y asignar y revocar roles con vigencia
**Para** controlar quién puede qué

**Criterios de aceptación**:
- [ ] `POST /usuarios` da de alta personal con contraseña provisoria y cambio obligatorio
- [ ] Asignar rol con vencimiento opcional; el vencimiento debe llegar con zona horaria y en el futuro (422 si no)
- [ ] Revocar escribe `revocada_en` y no borra la fila; reasignar un rol vencido cierra la fila anterior y abre una nueva
- [ ] Autoprotección: un ADMIN no se revoca su propio ADMIN y nunca queda el sistema sin administradores (409)
- [ ] `GET /eventos` lista el historial de seguridad paginado; se registran altas, cambios de rol y de contraseña, y los datos iniciales con actor `SISTEMA`

**Reglas relacionadas**: RN-03, RN-05 — casos C-07, C-08

### US-013 — Cambio obligatorio de contraseña con dos grupos de rutas
**Como** personal con contraseña provisoria
**Quiero** que se me bloquee todo salvo `/auth` y salud hasta cambiarla
**Para** no operar con credenciales provisorias

**Criterios de aceptación**:
- [ ] `main.py` monta un grupo abierto y un grupo protegido; el control se monta UNA sola vez en el protegido
- [ ] Con el cambio pendiente, el grupo protegido responde 403
- [ ] Tras el cambio, la cookie nueva vale y la anterior da 401, sin esperar entre el login y el cambio

**Reglas relacionadas**: RN-06, RN-07 — caso C-09

## Épica 6: Clientes y vehículos (parte del Ejercicio 3)

### US-014 — Alta y consulta de clientes
**Como** recepción
**Quiero** dar de alta clientes y ver un cliente con sus vehículos
**Para** registrar a quien trae un vehículo

**Criterios de aceptación**:
- [ ] `POST /clientes` → 201; documento repetido → 409; contrato con `extra="forbid"`
- [ ] `GET /clientes/{id}` devuelve el cliente con sus vehículos (precarga declarada en el repositorio); inexistente → 404

**Reglas relacionadas**: RN-01

### US-015 — Alta y baja de vehículos
**Como** recepción
**Quiero** registrar y dar de baja vehículos
**Para** que un vehículo vendido pueda ser registrado por su nuevo dueño

**Criterios de aceptación**:
- [ ] `POST /clientes/{id}/vehiculos` → 201; patente vigente repetida → 409; cliente inexistente → 404; año fuera de 1950..2100 → 422
- [ ] `DELETE /vehiculos/{id}` → 204 (borrado lógico); con órdenes abiertas → 409
- [ ] Tras la baja, la misma patente se puede registrar para otro cliente (201); una segunda patente vigente igual → 409
- [ ] Un vehículo dado de baja deja de aparecer y no se usa en órdenes nuevas

**Reglas relacionadas**: RN-01, RN-16 — caso C-19

### US-016 — Mis vehículos
**Como** cliente
**Quiero** ver mis vehículos
**Para** conocer lo que tengo registrado

**Criterios de aceptación**:
- [ ] `GET /mis-vehiculos` devuelve sólo los vehículos del cliente vinculado al usuario autenticado

**Reglas relacionadas**: RN-17

## Épica 7: Repuestos y stock (parte de los Ejercicios 3 y 6)

### US-017 — Catálogo de repuestos
**Como** administrador
**Quiero** crear, editar y dar de baja repuestos
**Para** mantener el catálogo

**Criterios de aceptación**:
- [ ] `POST /repuestos` con `stock_inicial` → 201 y un movimiento "Stock inicial"; código vigente repetido → 409
- [ ] `PATCH /repuestos/{id}` cambia sólo descripción y precio (`exclude_unset`); enviar `stock` → 422 por `extra="forbid"`
- [ ] Un cambio de precio deja una línea en `historial_precio_repuesto` en la misma transacción; un PATCH sin cambio de precio no deja línea
- [ ] `DELETE /repuestos/{id}` → 204 (borrado lógico); un repuesto dado de baja no se usa en órdenes nuevas

**Reglas relacionadas**: RN-01, RN-14, RN-16, RN-20 — casos C-16, C-18

### US-018 — Búsqueda y listado de repuestos
**Como** personal (ADMIN, RECEPCION, MECANICO)
**Quiero** buscar repuestos por descripción con paginación
**Para** encontrar lo que necesito

**Criterios de aceptación**:
- [ ] `GET /repuestos?q=&page=&size=` usa parámetros ligados (`' OR '1'='1` → lista vacía con total 0)
- [ ] Con `q=freno&size=1`: total 1, pages 1; `page=2` → 422; `size=500` → 422
- [ ] `GET /repuestos/{id}` → 200 o 404

**Reglas relacionadas**: CLAUDE.md #16, #17 — caso C-16

### US-019 — Reposición y trazabilidad de stock
**Como** administrador
**Quiero** reponer stock y consultar movimientos y precios
**Para** controlar el inventario

**Criterios de aceptación**:
- [ ] `POST /repuestos/{id}/reponer` suma stock y deja un movimiento, por el punto único de escritura de stock
- [ ] `GET /repuestos/{id}/movimientos` y `GET /repuestos/{id}/precios` son de ADMIN; la recepción recibe 403
- [ ] Ningún endpoint de alta propio para movimientos ni historial de precios

**Reglas relacionadas**: RN-14, AP-01 — caso C-18

## Épica 8: Órdenes de trabajo (parte del Ejercicio 3, 6 y 8)

### US-020 — Crear una orden
**Como** recepción
**Quiero** abrir una orden con sus ítems
**Para** registrar el ingreso de un vehículo

**Criterios de aceptación**:
- [ ] Nace PENDIENTE con al menos un ítem y sin repuestos repetidos; el precio se copia del repuesto y el total lo calcula el servidor
- [ ] La orden, sus ítems y la primera línea de historial se escriben en un solo bloque; repuesto inexistente → 409 y la orden no queda creada
- [ ] Catálogo vacío → 409 con mensaje propio
- [ ] El cuerpo no acepta precio, total, estado ni fecha (422)

**Reglas relacionadas**: RN-10, RN-16, RN-19 — caso C-10

### US-021 — Iniciar, terminar y cancelar
**Como** mecánico / administrador / recepción / dueño del vehículo
**Quiero** mover la orden por sus estados
**Para** reflejar el trabajo real

**Criterios de aceptación**:
- [ ] Iniciar: PENDIENTE → EN_REPARACION; sólo MECANICO; queda asignado; otro estado → 409
- [ ] Terminar: EN_REPARACION → TERMINADA por el mecánico asignado o un ADMIN (403 si no); descuenta stock, deja un movimiento por ítem y una línea de historial en un solo UoW
- [ ] Si un repuesto no alcanza → 409 y estado, stock, movimientos e historial quedan como estaban
- [ ] Terminar agenda con `BackgroundTasks` el aviso simulado, después de la respuesta y sólo si se confirmó
- [ ] Cancelar: PENDIENTE → CANCELADA por recepción, ADMIN o el dueño; ajena → 403 antes que 409; terminada → 409

**Reglas relacionadas**: RN-11, RN-12, RN-13, RN-14 — casos C-11, C-12, C-13

### US-022 — Consultar órdenes sin N+1
**Como** personal o dueño
**Quiero** ver el detalle y los listados de órdenes
**Para** seguir el estado de cada vehículo

**Criterios de aceptación**:
- [ ] El detalle (vehículo, cliente, ítems, repuesto de cada ítem, historial) se resuelve con un número FIJO de consultas (2 ítems = 4 ítems)
- [ ] `GET /ordenes?estado=` filtra por un estado declarado en el enum; uno no declarado → 422
- [ ] El cliente ve su orden (200) y no la ajena (403); `GET /mis-ordenes` con paginación
- [ ] `GET /estados-orden` devuelve los cuatro estados por posición con TERMINADA y CANCELADA finales

**Reglas relacionadas**: RN-17, RN-19 — casos C-06, C-15, C-17

## Épica 9: Casos de prueba y entrega

### US-023 — Seed, casos .http y evidencias
**Como** equipo
**Quiero** consolidar `seed.py`, los `.http`, las evidencias y el README
**Para** la demo y la corrección

**Criterios de aceptación**:
- [ ] `seed.py` vacía las tablas y carga los datos iniciales (catálogo primero), y es parte de la puesta en marcha
- [ ] Archivos `.http` en `test/` para C-01..C-19 con la respuesta esperada en un comentario; cada integrante escribe los de sus casos en su change y este change los consolida
- [ ] `test/solo_agregado.sql` para C-14, con evidencia de psql (seis rechazos del trigger y el de la FK)
- [ ] Evidencia de C-15 (consola con las consultas del detalle con 2 y 4 ítems)
- [ ] `requirements.txt`, `env.example`, `alembic.ini`, `migrations/`, `test/` y README con pasos de arranque desde cero (venv, dependencias, `.env` con cómo generar la clave de firma, creación de las dos bases, `alembic upgrade head`, `python seed.py`, servidor)
- [ ] Bitácora y PRs con revisión como evidencia del trabajo de los 5

**Reglas relacionadas**: AP-06, AP-07
