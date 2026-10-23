# Arquitectura Propuesta

## Patrones aplicados

| Patrón | Dónde se usa | Por qué |
|---|---|---|
| Arquitectura en capas (Router → Service → UoW → Repository → Model) | Todos los módulos | Cada capa sabe lo suyo y nada más (objetivo 1 de la consigna) |
| Repository genérico (`BaseRepository[T]`, `SoftDeleteRepository[T]`) | `app/core/repository.py` | Evita repetir CRUD; recibe sesión y clase del modelo porque los genéricos se borran en runtime |
| Repositorio de sólo lectura (sin herencia de Base) | `EstadoOrden` | Su PK es `codigo` y desde la API no se escribe |
| Unit of Work | `app/core/unit_of_work.py` + uno por módulo | Una sola transacción por operación; sólo el UoW confirma |
| Inyección de dependencias de FastAPI | `get_session`, UoW por módulo, `get_usuario_actual`, `requiere_rol` | El router construye el UoW; el servicio lo abre y nunca lo construye |
| Borrado lógico + índice único parcial | `vehiculo`, `repuesto` | Reutilizar patente/código tras una baja sin perder el historial |
| Catálogo con FK + enum en código | `estado_orden` | La base rechaza estados inexistentes; el enum fija el contrato de la API |
| Tabla de sólo agregado (trigger) | historial de estados, movimientos de stock, historial de precios | Inmutabilidad garantizada por la base (RN-15) |
| Sesión/transacción propia | `intento_acceso` | El fallo que se cuenta es el mismo que revierte el login (su costo se declara en un comentario) |
| Punto único de escritura de stock | Módulo `repuestos` | Lo usan la reposición y la terminación de órdenes (RN-14) |
| Dos grupos de rutas | `main.py` | FastAPI suma dependencias y no las resta; el control del cambio obligatorio se monta una sola vez |
| Carga anticipada declarada en el repositorio | Todos los repositorios que devuelven relaciones | Número fijo de consultas, sin N+1 ni carga perezosa |
| Tareas en segundo plano | Aviso al terminar una orden | Corre después de la respuesta y sólo si se confirmó (`BackgroundTasks`) |

## Estructura de directorios

```
taller-mecanico-api/
├── main.py                 # app, lifespan, grupo abierto y grupo protegido
├── seed.py                 # vacía tablas y carga datos iniciales (catálogo primero)
├── requirements.txt
├── env.example             # todas las variables, ningún secreto
├── alembic.ini             # sin credenciales
├── app/
│   ├── core/
│   │   ├── config.py       # Settings (pydantic-settings), @computed_field para la URL
│   │   ├── database.py     # crear motor/fábrica (los llama el lifespan), get_session
│   │   ├── security.py     # bcrypt fuera del bucle (to_thread + semáforo), JWT
│   │   ├── dependencies.py # usuario actual, roles vigentes, control de cambio obligatorio, requiere_rol
│   │   ├── repository.py   # BaseRepository[T], SoftDeleteRepository[T]
│   │   ├── paginacion.py   # envoltorio {items,total,page,size,pages}
│   │   └── unit_of_work.py # UnitOfWork base
│   └── modules/
│       ├── health/         # sólo router.py
│       ├── usuarios/       # models, schemas, repository, unit_of_work, service, router
│       ├── clientes/       # idem
│       ├── repuestos/      # idem
│       └── ordenes/        # idem
├── migrations/             # Alembic (plantilla async): 2 versiones
│   └── versions/           # 1) autogenerate  2) trigger a mano
├── test/                   # *.http (C-01..C-19) + solo_agregado.sql
└── tests/ (propuesto)      # pytest de TDD (ver más abajo)
```

La carpeta de pytest no está fijada por la consigna; se propone `tests/` (distinta de `test/`, que la consigna reserva para `.http` y SQL). Ver DD-09.

## Seguridad

- **Autenticación**: contraseñas con bcrypt (costo desde la configuración), toda llamada con `asyncio.to_thread` + semáforo y ANTES de abrir la transacción. Token JWT (PyJWT) con `sub`, `iat` con fracciones, `exp` y roles; sólo en la cookie `access_token` (HttpOnly, SameSite=Lax, Max-Age = duración, Secure configurable); nunca en el cuerpo ni leído de `Authorization`.
- **Límite de intentos**: 5 fallos por (correo, IP) en 60 s → 429 + `Retry-After`, sin calcular hash; el login correcto reinicia el conteo.
- **Anti-enumeración**: mismo mensaje y mismo tiempo exista o no el correo (hash ficticio calculado una vez en el lifespan).
- **Autorización**: roles vigentes consultados en la base en cada petición; 401 = no autenticado, 403 = sin permiso. Lo propio sólo pide autenticación.
- **Validación de input**: contratos Pydantic con `extra="forbid"`; PATCH con `exclude_unset`; todo campo que va a bcrypt, máximo 72 bytes (422); ninguna respuesta con `password_hash`.
- **Integridad**: unicidad por la base (UNIQUE e índices parciales), traducción de `IntegrityError` a 409 con mensaje propio; nunca texto de la base ni trazas; trigger de sólo agregado.
- **SQL**: nunca por concatenación; parámetros ligados (por ejemplo en la búsqueda `q` de repuestos).
- **Secrets management**: nada en el código ni como default ni en `alembic.ini`; la clave de firma es FIJA y vive en el `.env` (que no se versiona); si falta la clave o la contraseña de la base, la app no arranca.

## Variables de entorno

La consigna fija sólo las cinco `POSTGRES_*`; el resto de los nombres los aprobó el equipo (ver DD-10) y deben listarse en `env.example`.

| Variable | Descripción | Ejemplo | Sensible |
|---|---|---|---|
| `POSTGRES_USER` | Usuario de la base | `taller` | N |
| `POSTGRES_PASSWORD` | Contraseña de la base (sin default; si falta, no arranca) | (a definir por cada uno) | Y |
| `POSTGRES_DB` | Nombre de la base (la de tests es otra, p. ej. `taller_test`) | `taller` | N |
| `POSTGRES_HOST` | Host | `localhost` | N |
| `POSTGRES_PORT` | Puerto | `5432` | N |
| `JWT_SECRET_KEY` (propuesta) | Clave de firma FIJA del JWT (sin default) | (generada una vez, ver README) | Y |
| `JWT_ALGORITHM` (propuesta) | Algoritmo de firma | `HS256` | N |
| `ACCESS_TOKEN_EXPIRE_SECONDS` (propuesta) | Duración del token y Max-Age de la cookie | `1800` | N |
| `COOKIE_SECURE` (propuesta) | Marca `Secure` de la cookie | `false` en desarrollo | N |
| `BCRYPT_COST` (propuesta) | Costo (rounds) de bcrypt | `12` | N |
| `BCRYPT_MAX_CONCURRENT` (propuesta) | Tamaño del semáforo de bcrypt | `4` | N |
| `DB_POOL_SIZE` (propuesta) | Tamaño del pool del motor | `5` | N |
| `SQL_ECHO` | Mostrar las consultas en consola | `true` | N |

## Estrategia de pruebas (TDD estricto)

- pytest + pytest-asyncio + httpx.AsyncClient contra una base PostgreSQL de prueba separada, creada con `alembic upgrade head` (nunca `create_all`).
- Rojo → verde → refactor; cada escenario de la spec tiene al menos un test.
- Los `.http` de `test/` (C-01..C-19) son los casos de aceptación manuales, con la respuesta esperada en un comentario; se corre `python seed.py` antes de cada archivo.

## Flujo de trabajo del equipo

- Un change por vez según el roadmap; ramas `feat/<change>`; PR a `main` con aprobación de al menos un compañero antes del merge.
- Commits chicos y en español con el nombre del change.
- Los modelos los escribe sólo el change `esquema-y-migraciones`.
- Bitácora y PRs con revisión como evidencia para la demo en vivo.
