# Descripción General

## Stack tecnológico

Versiones mínimas, no cambiar (están fijadas en la consigna y en `CLAUDE.md`).

| Capa | Tecnología | Versión mínima |
|---|---|---|
| Lenguaje | Python | 3.12 |
| Framework web | FastAPI (`fastapi[standard]`, incluye uvicorn) | 0.111 |
| Modelos de tabla | SQLModel | 0.0.24 |
| ORM / sesión async | SQLAlchemy asincrónico | 2.0 |
| Driver | asyncpg (psycopg 3 async se acepta en la consigna; el equipo fijó asyncpg) | 0.30 |
| Base de datos | PostgreSQL | 16 o superior (en desarrollo, 17) |
| Migraciones | Alembic, plantilla asincrónica | 1.13 |
| Configuración | pydantic-settings | 2.0 |
| Hash de contraseñas | bcrypt | 4.0 |
| Token | PyJWT | 2.8 |
| Tests | pytest + pytest-asyncio + httpx.AsyncClient | (sin mínimo fijado) |

## Arquitectura general

```
HTTP ─▶ Router ─▶ Service ─▶ UnitOfWork ─▶ Repository ─▶ Model ─▶ PostgreSQL
        (rutas,    (reglas     (transacción:  (consultas,    (tablas,
        contratos, de negocio) commit/rollback, flush, carga  restricciones)
        errores)               misma sesión)   anticipada)
```

- **Router**: define rutas, construye el UnitOfWork con una dependencia, se lo pasa al servicio sin abrirlo y traduce errores a códigos HTTP.
- **Service**: contiene las reglas de negocio. Recibe el UnitOfWork y lo abre con `async with`; nunca lo construye.
- **UnitOfWork**: gestor de contexto async. Confirma al salir del bloque, revierte si sale con excepción y no cierra la sesión (no la creó). Sólo él hace commit.
- **Repository**: acceso a datos. `add`/`update` hacen `flush()`, nunca `commit()`. La precarga (carga anticipada) se declara dentro del método que la necesita.
- **Model**: modelos SQLModel con restricciones y relaciones.

Ciclo de vida (lifespan): crea el motor async (pool declarado en la configuración) y la fábrica de sesiones (`expire_on_commit=False`), los guarda en `app.state`, calcula una vez el hash ficticio del login y al apagar hace `dispose()`. Nada de esto se crea al importar un módulo.

Dos grupos de rutas en `main.py`: el **abierto** (salud y `/auth/*`) y el **protegido**, que lleva montado una sola vez el control del cambio obligatorio de contraseña (FastAPI suma dependencias y no las resta).

## Integraciones externas

| Servicio | Propósito | Tipo |
|---|---|---|
| PostgreSQL | Única persistencia | Driver async (asyncpg) |
| Aviso al cliente (simulado) | Notificar al terminar una orden: `await asyncio.sleep(0.5)` + mensaje en el registro, vía `BackgroundTasks` y sólo si la operación se confirmó | Interno, sin servicio externo |

No hay colas, Redis ni APIs de terceros.

## API REST

Fuente: tabla "Endpoints de referencia" de la consigna. "Abierto" y "Protegido" son los dos grupos de rutas de `main.py`.

### Salud y autenticación (grupo abierto)

| Método | Ruta | Quién | Códigos |
|---|---|---|---|
| GET | `/health/live` (no toca la base) | Cualquiera | 200 |
| GET | `/health/ready` (`SELECT 1`) | Cualquiera | 200, 503 |
| POST | `/auth/registro` | Cualquiera | 201, 409, 422 |
| POST | `/auth/login` | Cualquiera | 200, 401, 422, 429 |
| POST | `/auth/logout` | Cualquiera | 200 |
| GET | `/auth/yo` | Autenticado | 200, 401 |
| POST | `/auth/cambiar-password` | Autenticado | 200, 401, 422 |

### Usuarios, roles y eventos (grupo protegido)

| Método | Ruta | Quién | Códigos |
|---|---|---|---|
| POST | `/usuarios` (alta de personal, contraseña provisoria) | ADMIN | 201, 409, 422 |
| GET | `/usuarios/{id}/roles` | ADMIN | 200, 404 |
| POST | `/usuarios/{id}/roles` | ADMIN | 201, 404, 409, 422 |
| DELETE | `/usuarios/{id}/roles/{rol}` | ADMIN | 200, 404, 409 |
| GET | `/eventos` (page, size) | ADMIN | 200, 422 |

### Clientes y vehículos (grupo protegido)

| Método | Ruta | Quién | Códigos |
|---|---|---|---|
| POST | `/clientes` | RECEPCION, ADMIN | 201, 409, 422 |
| GET | `/clientes/{id}` (con sus vehículos) | RECEPCION, ADMIN | 200, 404 |
| POST | `/clientes/{id}/vehiculos` | RECEPCION, ADMIN | 201, 404, 409, 422 |
| DELETE | `/vehiculos/{id}` | RECEPCION, ADMIN | 204, 404, 409 |
| GET | `/mis-vehiculos` | Autenticado | 200 |

### Repuestos y stock (grupo protegido)

| Método | Ruta | Quién | Códigos |
|---|---|---|---|
| GET | `/repuestos` (q, page, size) | ADMIN, RECEPCION, MECANICO | 200, 422 |
| GET | `/repuestos/{id}` | ADMIN, RECEPCION, MECANICO | 200, 404 |
| POST | `/repuestos` (con `stock_inicial`) | ADMIN | 201, 409, 422 |
| PATCH | `/repuestos/{id}` (descripción y precio) | ADMIN | 200, 404, 422 |
| DELETE | `/repuestos/{id}` | ADMIN | 204, 404 |
| POST | `/repuestos/{id}/reponer` | ADMIN | 200, 404, 422 |
| GET | `/repuestos/{id}/movimientos` | ADMIN | 200, 404 |
| GET | `/repuestos/{id}/precios` | ADMIN | 200, 404 |

### Órdenes y catálogo (grupo protegido)

| Método | Ruta | Quién | Códigos |
|---|---|---|---|
| POST | `/ordenes` | RECEPCION, ADMIN | 201, 409, 422 |
| GET | `/ordenes` (estado, page, size) | RECEPCION, ADMIN, MECANICO | 200, 422 |
| GET | `/ordenes/{id}` | El personal, o el dueño del vehículo | 200, 403, 404 |
| POST | `/ordenes/{id}/iniciar` | MECANICO | 200, 404, 409 |
| POST | `/ordenes/{id}/terminar` | El mecánico asignado, o ADMIN | 200, 403, 404, 409 |
| POST | `/ordenes/{id}/cancelar` | RECEPCION, ADMIN o el dueño | 200, 403, 404, 409 |
| GET | `/estados-orden` (por posición) | Autenticado | 200 |
| GET | `/mis-ordenes` (page, size) | Autenticado | 200, 422 |

Toda ruta del grupo protegido responde además 401 sin sesión y 403 con el cambio de contraseña pendiente.

### Convenciones de respuesta

- 201 al crear, 204 al dar de baja, 404 si el recurso de la ruta no existe, 409 si choca con lo guardado, 422 si el cuerpo o los parámetros no cumplen el contrato.
- Listados: `{items, total, page, size, pages}`; `page` ≥ 1; `size` 1..100 (por defecto 20); página inexistente → 422; `total` con los mismos filtros; cero resultados = una página vacía.
- Login: el token viaja sólo en `Set-Cookie`; el cuerpo es `{"mensaje": "Sesión iniciada", "debe_cambiar_password": false, "expira_en_segundos": 1800}`.
- Orden (POST `/ordenes`): el cuerpo trae `vehiculo_id`, `falla` e `items` (`repuesto_id`, `cantidad`); nunca precio, total, estado ni fecha. La respuesta incluye `estado`, `patente`, `total`, `creada_en`, `mecanico_id`, `falla`, `cliente`, `items` (con `codigo`, `descripcion`, `precio_unitario`, `subtotal`) e `historial`.
