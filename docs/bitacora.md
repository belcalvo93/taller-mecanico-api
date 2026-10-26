# Bitácora del equipo

Cada integrante anota en su sección las decisiones que tomó trabajando con el agente. Una entrada por change o sesión, con esta plantilla:

```
### YYYY-MM-DD · CH-NN <nombre-del-change>
- **Fecha:**
- **Qué le pidió al agente:**
- **Qué corrigió a mano y por qué:**
```

## Belén

### 2026-10-25 · CH-01 infra-base
- **Fecha:** 2026-10-25
- **Qué le pidió al agente:** implementar `/opsx:apply infra-base` con TDD estricto: estructura del proyecto, `requirements.txt`, configuración con `pydantic-settings` sin secretos por defecto, `env.example`, motor y sesiones async, lifespan con hash ficticio y `dispose()`, `/health/live` y `/health/ready`, y la fixture de la base de tests con Alembic. Se trabajó en un venv con Python 3.14.7 (la consigna pide 3.12 o superior).
- **Qué corrigió a mano y por qué:**
  - Exigí rojo primero desde el grupo 6, después de detectar que los tests del lifespan se escribieron después del código.
  - Pedí que el agente no haga commits ni agregue líneas de atribución; los commits los hice yo.
  - Corregí la propuesta de commits: `router.py` tenía que ir en el mismo commit que `main.py` para que el commit arranque.

**Versiones instaladas en Python 3.14** (resultado de `pip install -r requirements.txt`; `pip check` sin conflictos):

| Paquete | Versión | Piso en `requirements.txt` |
|---|---|---|
| fastapi[standard] | 0.162.0 | >=0.111 |
| sqlmodel | 0.0.48 | >=0.0.24 |
| SQLAlchemy | 2.1.6 | >=2.0 |
| asyncpg | 0.32.0 | **>=0.31** (subido, ver abajo) |
| alembic | 1.20.1 | >=1.13 |
| pydantic-settings | 2.16.1 | >=2.0 |
| bcrypt | 5.0.0 | >=4.0 |
| PyJWT | 2.15.1 | >=2.8 |
| pytest / pytest-asyncio / httpx | 9.1.1 / 1.4.1 / 0.28.1 | sin piso |

**Notas de la sesión**
- asyncpg 0.30 no tiene wheel para Python 3.14; se usa asyncpg>=0.31 (0.32.0 instalada). Es compatible con 3.12 y 3.13, así que no afecta al resto del equipo.
- En la tarea 2.6 no se pudo forzar el rojo porque que el entorno pise al .env es comportamiento nativo de pydantic-settings; se dejó el test como verificación.
- Con FastAPI 0.162 el orden de include_router es perezoso y ya no importa; el test de rutas usa app.openapi()["paths"].
- Los tests del lifespan (grupo 5) se escribieron después de `main.py`; se compensó con mutaciones (sacar `dispose()`, cambiar el semáforo y el costo de bcrypt) que hicieron fallar 5 tests, y se restauró el código. Desde el grupo 6 exigí rojo primero.
- bcrypt 5.x lanza `ValueError` con contraseñas de más de 72 bytes (la 4.x truncaba). No afecta a CH-01 (la contraseña ficticia tiene 32 bytes), pero CH-04 debe validar los 72 bytes en el contrato (regla 9).

**Decisiones no obvias del design (D1 a D9)**
- **D1:** `Settings` nunca se instancia al importar; se obtiene con `get_settings()` (con `lru_cache`) desde el lifespan. Los secretos son `SecretStr` sin default, con `min_length` (1 y 32), así un `.env` copiado de `env.example` con valores vacíos tampoco arranca. `DATABASE_URL` es un campo calculado con `URL.create` (escapa `@`, `:` y `/`).
- **D2:** `database.py` solo tiene fábricas puras (`crear_motor`, `crear_fabrica_sesiones`) y `get_session`; el motor no se crea al importar (regla 7) y el commit es del UoW (CH-03).
- **D3:** el lifespan guarda `settings`, `engine`, `session_factory`, `bcrypt_semaforo` y `hash_ficticio` en `app.state` (contrato para CH-04), no hace `SELECT 1` al arrancar y hace `dispose()` en un `finally`.
- **D4:** dos grupos de rutas (`rutas_abiertas`, `rutas_protegidas`) con un punto de inserción comentado por change.
- **D5:** `/health/ready` usa `get_session`, `SELECT 1` con `asyncio.wait_for` de 3 s y cualquier falla da 503 con cuerpo fijo; solo se registra el nombre de la clase de la excepción (SQLAlchemy envuelve el error de asyncpg, por eso aparece como `DBAPIError`).
- **D6:** `conftest.py` fija `POSTGRES_DB=taller_test` al importarse; la fixture `base_migrada` corre `alembic upgrade head` en un subproceso, se saltea sin `alembic.ini` y rechaza bases que no terminan en `_test`.
- **D7:** `requirements.txt` con pisos (`>=`), no pins, para que instale en 3.12 y 3.14.
- **D8:** `env.example` lista las 13 variables con los dos secretos vacíos; el `.env` real no se versiona y la clave JWT se genera una sola vez.
- **D9:** CH-01 no crea `migrations/` ni `alembic.ini` (`alembic init -t async` de CH-02 falla si el directorio existe).

## Elías

_(sin entradas todavía)_

## Hernán

_(sin entradas todavía)_

## Bruno

_(sin entradas todavía)_

## Joaquín

_(sin entradas todavía)_

## Pendientes para CH-09 (README)

- Cada integrante crea su propio `.env` a partir de `env.example`, su usuario de PostgreSQL y las bases `taller` y `taller_test`.
- Documentar cómo generar la clave de firma (`python -c "import secrets; print(secrets.token_urlsafe(64))"`) y que no se comparte ni se versiona.
- Avisar a Hernán (CH-04) del contrato `app.state.hash_ficticio` / `app.state.bcrypt_semaforo` y del cambio de bcrypt 5.x con más de 72 bytes.
