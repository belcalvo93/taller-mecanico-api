# Proposal

> CH-01 `infra-base` · issue #1 · Responsable: Belén · Ola 1 · Governance: ALTO (configuración con secretos y conexión a la base).

## Why

El repositorio todavía no tiene una sola línea ejecutable: sin un esqueleto que arranque, lea la configuración sin secretos y administre el motor de la base en el lifespan, ningún otro change (CH-02 esquema, CH-03 núcleo) puede empezar. Además, el Ejercicio 1 de la consigna (8 %) evalúa exactamente esto, y "un proyecto que no levanta o que contiene credenciales reales en el repositorio NO SE CORRIGE".

## What Changes

- Estructura obligatoria del proyecto: `main.py`, `app/core/`, `app/modules/{health,usuarios,clientes,repuestos,ordenes}/` (paquetes vacíos salvo `health/router.py`), `test/` (reservada a `.http` y `solo_agregado.sql`), `tests/` (pytest) y `docs/`.
- `app/core/config.py`: `Settings` con pydantic-settings que lee el entorno o un `.env` no versionado; URL de la base con `@computed_field` y driver `postgresql+asyncpg`; `POSTGRES_PASSWORD` y `JWT_SECRET_KEY` sin valor por defecto (si faltan o están vacías, la app no arranca); pool, bcrypt, `SQL_ECHO`, `COOKIE_SECURE`, algoritmo y duración del token desde la configuración (DD-10).
- `app/core/database.py`: funciones que crean el motor async y la fábrica de sesiones (`expire_on_commit=False`), invocadas sólo por el lifespan; `get_session` toma la fábrica de `app.state`.
- Lifespan en `main.py`: motor, fábrica, semáforo de bcrypt y hash ficticio del login (calculado una sola vez) en `app.state`; `dispose()` al apagar. Nada se crea al importar un módulo.
- `main.py` con los dos grupos de rutas (abierto y protegido), vacíos salvo salud, con el lugar marcado para el `include_router` de cada módulo.
- `GET /health/live` (200, sin tocar la base) y `GET /health/ready` (`SELECT 1`; 503 con mensaje propio si la base no contesta, sin filtrar texto interno — RN-18).
- `env.example` con todas las variables y ningún secreto; `.env` local (no versionado) creado durante el apply con una `JWT_SECRET_KEY` fija generada una sola vez (AP-03).
- `requirements.txt` con las dependencias del stack en versiones mayores o iguales a los mínimos de `CLAUDE.md` y compatibles con Python 3.14 (entorno de Belén); `pytest.ini`.
- `tests/conftest.py` con el cliente `httpx.AsyncClient` contra la app y la fixture de la base `taller_test` creada con `alembic upgrade head` (nunca `create_all`); la fixture queda escrita y se ejercita de punta a punta recién cuando CH-02 mergee las migraciones.
- `docs/bitacora.md` con una sección por integrante (Belén, Elías, Hernán, Bruno, Joaquín).

Fuera de alcance (lo hacen otros changes): modelos, `alembic.ini` y `migrations/` (CH-02), repositorios, UoW y paginación (CH-03), `security.py`, JWT y login (CH-04), dependencias de usuario/roles y el control del cambio obligatorio (CH-04/CH-05), README de arranque (CH-09). Sin Docker, CI ni linter (DD-04).

## Capabilities

### New Capabilities
- `configuracion`: lectura de la configuración desde el entorno/`.env`, URL de la base computada, variables obligatorias sin default, parámetros operativos (pool, bcrypt, `SQL_ECHO`, cookie, token) y el contrato de `env.example` sin secretos.
- `ciclo-de-vida`: creación del motor y la fábrica de sesiones en el lifespan (`app.state`), `get_session` por petición, hash ficticio calculado una vez, `dispose()` al apagar, nada creado al importar, y los dos grupos de rutas de `main.py`.
- `salud`: endpoints `GET /health/live` y `GET /health/ready`, con su comportamiento ante base caída y sin filtrar detalles internos.
- `entorno-de-pruebas`: estructura de carpetas del proyecto, dependencias instalables, configuración de pytest y la fixture de la base de tests creada con Alembic.

### Modified Capabilities
<!-- No hay specs previas en openspec/specs/: este es el primer change. -->
- (ninguna)

## Impact

- **Código nuevo**: `main.py`, `app/__init__.py`, `app/core/{__init__,config,database}.py`, `app/modules/**/__init__.py`, `app/modules/health/router.py`, `tests/conftest.py` y los tests de este change, `pytest.ini`, `requirements.txt`, `env.example`, `docs/bitacora.md`, `test/` (vacía, con `.gitkeep`).
- **Archivos locales no versionados**: `.env` (ya cubierto por el `.gitignore` existente) y el entorno virtual `.venv/`.
- **API**: aparecen `GET /health/live` y `GET /health/ready` en el grupo abierto.
- **Dependencias**: FastAPI (`fastapi[standard]`), SQLModel, SQLAlchemy async, asyncpg, Alembic, pydantic-settings, bcrypt, PyJWT, pytest, pytest-asyncio, httpx. Riesgo: compatibilidad de asyncpg (y en menor medida greenlet/pydantic-core) con Python 3.14 — ver design.
- **Otros changes**: CH-02 y CH-03 arrancan sobre esta estructura; cada change posterior agrega sólo su línea de `include_router` en el grupo que le toca de `main.py`. CH-04 reutiliza `app.state.hash_ficticio` y `app.state.bcrypt_semaforo`.
- **Base de datos**: sólo se conecta (`SELECT 1`); no crea ni modifica esquema.
