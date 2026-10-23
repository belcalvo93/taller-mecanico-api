# Taller mecánico — API (Programación III, UTN)

Proyecto: API asincrónica para un taller mecánico (órdenes de trabajo, stock, acceso).
Fuente de verdad del enunciado: `docs/consigna-tp.md` (TP Unidades 1 a 6). Si algo de este archivo contradice la consigna, manda la consigna.

## Stack (versiones mínimas, no cambiar)
Python 3.12 · FastAPI 0.111 (`fastapi[standard]`) · SQLModel 0.0.24 · SQLAlchemy 2.0 async · asyncpg 0.30 · PostgreSQL 16 o superior · Alembic 1.13 (plantilla async) · pydantic-settings 2.0 · bcrypt 4.0 · PyJWT 2.8.
Tests de TDD: pytest + pytest-asyncio + httpx.AsyncClient contra una base PostgreSQL de prueba creada con `alembic upgrade head` (nunca `create_all`).

## Arquitectura obligatoria
Router → Service → UoW → Repository → Model. Cada capa sabe lo suyo y nada más.

```
main.py              app, lifespan, grupo abierto y grupo protegido
seed.py              vacía tablas y carga datos iniciales (catálogo primero)
app/core/            config, database, security, dependencies, repository,
                     paginacion, unit_of_work
app/modules/<mod>/   models, schemas, repository, unit_of_work, service, router
migrations/          Alembic (2 versiones: autogenerate + trigger a mano)
test/                *.http (C-01..C-19) + solo_agregado.sql
```
Módulos: `health` (sólo router.py), `usuarios` (Usuario, AsignacionRol, IntentoAcceso, EventoSeguridad), `clientes` (Cliente, Vehiculo), `repuestos` (Repuesto, MovimientoStock, HistorialPrecio), `ordenes` (EstadoOrden, OrdenTrabajo, ItemOrden, HistorialEstadoOrden).

## Reglas que NUNCA se rompen
1. Nombres de tablas y columnas exactamente como la consigna. Se pueden agregar columnas, no quitar ni renombrar.
2. Todas las fechas `timestamptz`. Dinero `NUMERIC` / `Decimal`, nunca `float`. Cada FK con su índice.
3. Esquema sólo con Alembic. Migración 1 con `--autogenerate`; migración 2 escrita a mano con el trigger de sólo agregado. Cada migración lleva un comentario que diga que se leyó antes de aplicarla. `upgrade head` → `downgrade base` → `upgrade head` tiene que andar.
4. `estado_orden` es catálogo (PK `codigo`), la migración la crea vacía y la llena `seed.py`. Funciona como un enum: sin endpoints de crear, editar ni borrar. Los estados de órdenes e historial son FK, nunca CHECK con lista.
5. Índices únicos parciales (`postgresql_where`): `asignacion_rol(usuario_id, rol) WHERE revocada_en IS NULL`, `vehiculo(patente) WHERE borrado_en IS NULL`, `repuesto(codigo) WHERE borrado_en IS NULL`.
6. La unicidad la garantiza la base: no se verifica con consulta previa; se traduce el `IntegrityError` a 409 con mensaje propio. Nunca se devuelve texto de la base ni trazas. Ninguna entrada inválida termina en 500.
7. Motor y fábrica de sesiones se crean en el lifespan y viven en `app.state`; nunca al importar un módulo. `expire_on_commit=False`. El lifespan calcula una vez el hash ficticio y hace `dispose()` al apagar.
8. Sin secretos en el código, ni como default, ni en `alembic.ini`. Si falta la clave de firma o la contraseña de la base, la app no arranca. La clave de firma del JWT es FIJA y vive en el `.env`: nunca se genera al arrancar. `env.example` sin secretos; `.env` no se versiona.
9. bcrypt siempre con `asyncio.to_thread` + semáforo, costo desde la config, y ANTES de abrir la transacción. Todo campo que va a bcrypt: máximo 72 **bytes** validado en el contrato (422).
10. Token JWT (`sub`, `iat` con fracciones de segundo, `exp`, roles) sólo en cookie `access_token` HttpOnly, SameSite=Lax, Max-Age = duración, Secure configurable. Nunca en el cuerpo, nunca leído de `Authorization`.
11. Login en este orden: límite de intentos (429 + Retry-After, sin hash) → verificación contra hash real o ficticio. Mismo mensaje y tiempo exista o no el correo. `intento_acceso` se escribe en sesión y transacción PROPIAS (comentado en el código, con su costo).
12. Permisos con roles vigentes consultados en la base en cada petición (no los del token). 401 = no autenticado; 403 = sin permiso. Dos grupos de rutas en `main.py`; el control del cambio obligatorio se monta una sola vez en el protegido.
13. Repositorios: `add`/`update` hacen `flush()`, nunca `commit()`. `BaseRepository[T]` recibe sesión y clase del modelo. `SoftDeleteRepository[T]` hereda y suma `get_by_id_including_deleted` y `soft_delete`. El catálogo tiene repo de sólo lectura que NO hereda de BaseRepository. Precarga declarada dentro del método que la usa; carga perezosa prohibida.
14. UnitOfWork: gestor de contexto async, commit al salir, rollback con excepción, no cierra la sesión. Sólo el UoW hace commit. El router lo construye (dependencia), el servicio lo abre con `async with` y nunca lo construye. RN-02, RN-13 y RN-20 en un solo bloque cada una. El stock se escribe en un único punto.
15. Las tablas appendOnly (historial_estado_orden, movimiento_stock, historial_precio_repuesto) no tienen endpoint propio de alta: se escriben dentro del service de la operación que las genera.
16. Contratos de entrada con `extra="forbid"`. PATCH con `exclude_unset`. Ninguna respuesta con `password_hash`. Listados con `{items, total, page, size, pages}`, page ≥ 1, size 1..100 (20 por defecto), página inexistente → 422, total con los mismos filtros, cero resultados = una página vacía.
17. SQL nunca armado por concatenación. Todos los handlers `async def`, sin llamadas bloqueantes. `SQL_ECHO=true` configurable para ver las consultas.

## Forma de trabajo (SDD)
- Un change por vez, en el orden del roadmap. No se implementa nada que no esté en la spec del change activo.
- TDD estricto: primero el test que falla (rojo), después el código mínimo (verde), después refactor. Cada escenario de la spec tiene al menos un test.
- Antes de archivar un change: correr toda la suite y verificar contra cada regla RN y cada caso C que el change toca.
- Commits chicos y en español, con el nombre del change.
- Equipo de 5 (Belén, Elías, Hernán, Bruno, Joaquín): una rama por change `feat/<change>`, PR a main con revisión de un compañero. Los modelos los escribe sólo el change esquema-y-migraciones.
