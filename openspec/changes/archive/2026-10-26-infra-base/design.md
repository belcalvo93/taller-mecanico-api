# Design

## Context

Repositorio greenfield: hoy sólo hay documentación (consigna, KB, roadmap), `.gitignore` (ya ignora `.env`, `.env.*` salvo `env.example`, `.venv/`) y `openspec/` sin specs previas. Motivación y alcance: ver `proposal.md`. Requisitos: ver `specs/configuracion`, `specs/ciclo-de-vida`, `specs/salud` y `specs/entorno-de-pruebas`.

Restricciones que moldean el diseño:
- Reglas 7, 8 y 17 de `CLAUDE.md`: recursos sólo en el lifespan y en `app.state`, `expire_on_commit=False`, hash ficticio una vez, `dispose()`; secretos sólo en `.env`, sin defaults, clave JWT fija; handlers `async def` sin bloqueo y `SQL_ECHO` configurable.
- Entorno de Belén: Windows + Git Bash, **Python 3.14**, PostgreSQL 17 local con el usuario `taller` y las bases `taller` (desarrollo) y `taller_test` (tests), ambas con owner `taller`.
- Este change no tiene Alembic todavía (lo trae CH-02), así que la fixture de base migrada se escribe ahora pero recién se ejercita de punta a punta con CH-02.

## Goals / Non-Goals

**Goals:**
- Fijar el contrato de `app.state` que usan los changes siguientes: `settings`, `engine`, `session_factory`, `bcrypt_semaforo`, `hash_ficticio`.
- Que la configuración sea imposible de arrancar sin secretos y que ningún secreto aparezca en logs, `repr` ni respuestas.
- Dejar `main.py` con un punto de inserción claro por módulo para minimizar conflictos de merge en la ola 2.
- Que toda la suite de este change corra con `pytest` desde la raíz, con la base `taller_test` real (sin mocks del driver para el 200 de `ready`).

**Non-Goals:**
- `alembic.ini`, `migrations/` y modelos (CH-02); repositorios, UoW y paginación (CH-03); `security.py`, JWT, verificación de contraseñas y login (CH-04); `dependencies.py` y el control del cambio obligatorio (CH-04/CH-05); README de arranque (CH-09).
- Limpieza de datos entre tests (la definen CH-02/CH-03 cuando haya tablas).
- Manejador global de excepciones: en este change sólo `ready` puede fallar contra la base y lo resuelve localmente.

## Decisions

### D1 — `Settings` con caché perezosa, nunca instanciada al importar
`app/core/config.py` define `class Settings(BaseSettings)` y `get_settings()` decorada con `functools.lru_cache`. Ningún módulo instancia `Settings` a nivel de módulo; el lifespan llama a `get_settings()` y guarda el resultado en `app.state.settings`.
- `model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`; el entorno pisa al `.env` (comportamiento nativo de pydantic-settings).
- `POSTGRES_PASSWORD: SecretStr` y `JWT_SECRET_KEY: SecretStr`, sin default, con `min_length` (1 y 32): así un `.env` copiado de `env.example` con valores vacíos también impide arrancar, y `repr()` muestra `**********`.
- `POSTGRES_USER` y `POSTGRES_DB` obligatorias; `POSTGRES_HOST="localhost"`, `POSTGRES_PORT=5432`; resto con los defaults de DD-10 y validaciones `Field(ge=..., le=...)` (`BCRYPT_COST` 4..31, `BCRYPT_MAX_CONCURRENT ≥ 1`, `DB_POOL_SIZE ≥ 1`, `ACCESS_TOKEN_EXPIRE_SECONDS > 0`).
- `DATABASE_URL` como `@computed_field(repr=False)` + `@property`, construida con `sqlalchemy.engine.URL.create("postgresql+asyncpg", ...)` y `render_as_string(hide_password=False)`: escapa `@`, `:` y `/` de la contraseña sin concatenar a mano (regla 17).
- **Alternativa descartada**: `settings = Settings()` global. Rompe la regla 7 (se lee al importar) y hace que cualquier `import` falle sin `.env`, incluido pytest al recolectar.
- Los tests construyen `Settings(_env_file=None)` con `monkeypatch` para aislarse del `.env` real; un fixture autouse limpia `get_settings.cache_clear()` antes y después de cada test.

### D2 — `database.py` sólo con fábricas puras y `get_session`
- `crear_motor(settings) -> AsyncEngine`: `create_async_engine(settings.DATABASE_URL, pool_size=settings.DB_POOL_SIZE, echo=settings.SQL_ECHO, pool_pre_ping=True)`. No conecta (los motores de SQLAlchemy son perezosos).
- `crear_fabrica_sesiones(engine) -> async_sessionmaker`: `async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`, con `AsyncSession` de `sqlmodel.ext.asyncio.session` para que los changes siguientes puedan usar `session.exec(...)`.
- `async def get_session(request: Request)`: `async with request.app.state.session_factory() as session: yield session` (el `async with` cierra la sesión aunque la petición falle). No hace commit: eso es del UoW (CH-03).
- **Alternativa descartada**: motor global en `database.py`. Prohibido por la consigna (se crea antes de que exista el bucle de eventos).

### D3 — Lifespan y contrato de `app.state`
`main.py` define `@asynccontextmanager async def lifespan(app)`:
1. `settings = get_settings()` → si faltan secretos, `ValidationError` y la app no arranca (US-001).
2. `engine = crear_motor(settings)`; `session_factory = crear_fabrica_sesiones(engine)`.
3. `bcrypt_semaforo = asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENT)` (creado dentro del bucle, igual que el motor).
4. `hash_ficticio`: bajo el semáforo, `await asyncio.to_thread(bcrypt.hashpw, secrets.token_bytes(32), bcrypt.gensalt(rounds=settings.BCRYPT_COST))`. La contraseña ficticia es aleatoria y se descarta: nadie conoce su texto. Se llama a `bcrypt.hashpw` a través del módulo (no `from bcrypt import hashpw`) para que el test pueda contar las llamadas.
5. Guarda los cinco en `app.state`, `yield`, y en un `finally` hace `await engine.dispose()`.
- El arranque **no** hace `SELECT 1`: si la base está caída la app igual arranca y `/health/ready` informa 503. Así `live` sirve aunque la base no esté.
- El cálculo del hash ficticio queda en un helper privado de `main.py` (`_calcular_hash_ficticio`). CH-04 puede moverlo a `app/core/security.py` reutilizando `app.state.bcrypt_semaforo`, **sin cambiar el contrato** `app.state.hash_ficticio` (bytes, hash bcrypt con el costo de la config).
- **Alternativa descartada**: crear el semáforo en `security.py` a nivel de módulo. Aunque desde 3.10 `asyncio.Semaphore` no se ata al loop al construirse, se mantiene la regla única "todo recurso compartido nace en el lifespan".

### D4 — Dos grupos de rutas con punto de inserción por módulo
`main.py` declara `rutas_abiertas = APIRouter()` y `rutas_protegidas = APIRouter()` (sin dependencias; CH-05 le agrega una sola vez `dependencies=[Depends(control_cambio_obligatorio)]`). Debajo, un bloque comentado con una línea por change (`# CH-04: rutas_abiertas.include_router(auth_router)`, `# CH-05: ...`, `# CH-06: rutas_protegidas.include_router(clientes_router)`, etc.) y recién después `app.include_router(rutas_abiertas)` y `app.include_router(rutas_protegidas)`. Importa el orden: `include_router` copia las rutas en el momento de incluirlas, así que los módulos se agregan a cada grupo **antes** de incluir el grupo en la app (queda comentado en el código).
- `app = FastAPI(title="Taller mecánico API", lifespan=lifespan)` se construye al importar: un objeto `FastAPI` no es un recurso (no abre conexiones ni lee el entorno).

### D5 — Salud: `ready` con sesión, límite de espera y respuesta fija
`app/modules/health/router.py` (único archivo del módulo, como exige la consigna):
- `GET /health/live` → `{"estado": "ok"}`; no declara la dependencia de sesión.
- `GET /health/ready` → recibe `session = Depends(get_session)` y hace `await asyncio.wait_for(session.execute(text("SELECT 1")), timeout=TIEMPO_MAXIMO_READY_SEGUNDOS)` (constante del router, 3 s). Éxito → 200 `{"estado": "ok", "base": "ok"}`. Cualquier excepción (conexión rechazada, `InvalidPasswordError`, base inexistente, `TimeoutError`, errores de SQLAlchemy) → 503 con `JSONResponse({"estado": "no disponible", "base": "no disponible"})` y un `logger.warning` que registra **sólo el nombre de la clase** de la excepción (sin el mensaje, que puede incluir host/usuario).
- Se captura `Exception` a propósito: es una sonda; RN-18 exige que nunca salga un 500 ni texto interno, y cualquier falla de la base significa "no listo".
- Usa `get_session` (y no el motor directo) para ejercitar el mismo camino que el resto de la app.
- **Alternativa descartada**: `connect_args={"timeout": ...}` de asyncpg solamente. No cubre una base que acepta TCP y no contesta; `wait_for` acota todo el chequeo.

### D6 — Arnés de tests
- `pytest.ini`: `testpaths = tests`, `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`. `test/` nunca se recolecta.
- `tests/conftest.py`, al importarse, fija `os.environ["POSTGRES_DB"] = "taller_test"` (constante `BASE_DE_TESTS`): el resto de las credenciales sale del `.env` de cada integrante. Es código de test, no de la app, así que no viola la regla 7.
- Fixture `client`: `async with app.router.lifespan_context(app):` y adentro `httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test")`. `ASGITransport` no ejecuta el lifespan por sí mismo; así no hace falta agregar `asgi-lifespan` como dependencia.
- Fixture `base_migrada` (scope `session`, **sincrónica**): si no existe `alembic.ini` → `pytest.skip("se ejercita cuando CH-02 agregue las migraciones")`; si `POSTGRES_DB` no termina en `_test` → falla sin migrar; si no, `subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env={..., "POSTGRES_DB": "taller_test"}, check=True)`. Subproceso para no anidar el `asyncio.run` del `env.py` async de Alembic dentro del bucle de pytest-asyncio. Ningún test de CH-01 depende de esta fixture (ninguno necesita tablas); se verifica sólo el skip y la guarda `_test`.
- Contrato con CH-02: el `env.py` de Alembic toma la URL de `get_settings().DATABASE_URL` (nunca de `alembic.ini`), así la variable `POSTGRES_DB` del subproceso decide la base.
- "Nada al importar" se prueba en un **subproceso** (`sys.executable -c "import main; ..."`) con `cwd` en un directorio temporal (sin `.env`), `PYTHONPATH` en la raíz del repo y sin `POSTGRES_PASSWORD`/`JWT_SECRET_KEY` en el entorno: si la importación leyera la config o creara el motor, fallaría.
- Los tests de `ready` 200 y 503-por-credenciales usan la base `taller_test` real; el 503-por-base-caída arranca la app con `POSTGRES_PORT` apuntando a un puerto cerrado. En Windows un `connect` a un puerto local cerrado puede tardar ~2 s (reintentos de SYN); el límite de 3 s lo acota igual.

### D7 — `requirements.txt` y Python 3.14
- Formato `paquete>=mínimo`, sin pins exactos, para que instale tanto en 3.12 (resto del equipo) como en 3.14 (Belén): `fastapi[standard]`, `sqlmodel`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic-settings`, `bcrypt`, `PyJWT`, `pytest`, `pytest-asyncio`, `httpx`.
- Piso = el mayor entre el mínimo de `CLAUDE.md` y la primera versión que se verifique instalable en 3.14 durante el apply. Si el mínimo de `CLAUDE.md` no tiene soporte para 3.14 (candidatos: `asyncpg` 0.30, `sqlalchemy`/`greenlet` antiguos, `pydantic-core` transitivo, `pytest-asyncio` antiguos), se sube el piso a la versión que efectivamente instaló y se anota en la bitácora con el motivo. Nunca se baja de los mínimos de `CLAUDE.md`.
- Se instala en `.venv/` (ya ignorado) con `py -3.14 -m venv .venv` y se verifica con un import de cada paquete y `pip check`.
- `bcrypt` 5.x lanza `ValueError` con contraseñas de más de 72 bytes (4.x truncaba): no afecta a CH-01 (la contraseña ficticia tiene 32 bytes), pero se avisa a CH-04, que de todas formas valida 72 bytes en el contrato (regla 9).
- **Driver**: asyncpg es decisión cerrada (DD-01). Si no instala en 3.14 (sin wheel para Windows y la compilación desde fuente falla), **no se cambia de driver**: el apply se detiene y avisa a Belén.

### D8 — `env.example`, `.env` y clave de firma
- `env.example` lista las 13 variables de `Settings` en el orden de la tabla de `08_arquitectura_propuesta.md`; `POSTGRES_PASSWORD=` y `JWT_SECRET_KEY=` vacías (con un comentario que dice cómo generar la clave: `python -c "import secrets; print(secrets.token_urlsafe(64))"`); el resto con los valores de ejemplo no secretos (`SQL_ECHO=true` para desarrollo, AP-05).
- `.env` (no versionado) lo crea el apply copiando `env.example` y completando: `POSTGRES_USER=taller`, `POSTGRES_DB=taller`, `POSTGRES_HOST=localhost`, `POSTGRES_PORT=5432`, `JWT_SECRET_KEY` generada **una sola vez** con `secrets.token_urlsafe(64)` y escrita directamente en el archivo (sin mostrarla en el chat ni en logs), y `POSTGRES_PASSWORD` con la contraseña local que provee Belén (el agente no la escribe en ningún archivo versionado ni la repite).
- La clave queda fija en `.env`: el código nunca la genera al arrancar (AP-03).

### D9 — `migrations/` no se crea en este change
CHANGES.md lista `migrations/` en la estructura de CH-01, pero `alembic init -t async migrations` (CH-02) falla si el directorio existe y no está vacío, y git no versiona directorios vacíos (habría que poner un `.gitkeep`, que justamente lo dejaría no vacío). Por eso CH-01 **no** crea `migrations/` ni `alembic.ini`; los crea CH-02 con `alembic init`. `test/` sí se crea, con `.gitkeep` (CH-02 agrega `solo_agregado.sql`).

## Risks / Trade-offs

- [asyncpg sin wheel para Python 3.14 en Windows] → El apply instala primero en un venv limpio y, si falla, se detiene y avisa a Belén sin cambiar de driver. Opciones que decide ella: esperar/usar una versión de asyncpg con wheel `cp314`, o crear el venv con un Python 3.12/3.13 instalado en paralelo (`py -3.13 -m venv .venv`). El resto del equipo con 3.12 no está afectado.
- [Otras dependencias con extensiones C (`greenlet`, `pydantic-core`, `bcrypt`) sin soporte en 3.14] → mismo procedimiento: subir el piso a la primera versión con wheel `cp314` y anotarlo; si no existe, parar y avisar.
- [`pytest-asyncio` y deprecaciones de políticas de event loop en 3.14] → usar la versión más reciente; si aparecen `DeprecationWarning` del propio plugin, no se silencian en la config, se anotan.
- [Tests que dependen de la base real (`ready` 200/503 por credenciales)] → fallan si PostgreSQL no está levantado. Es intencional (DD-03); el mensaje del fallo indica levantar Postgres y revisar `.env`.
- [`.env` con la contraseña real en disco] → cubierto por `.gitignore`; el apply verifica con `git check-ignore .env` y `git status` antes de cada commit.
- [Fijar `POSTGRES_DB=taller_test` en `conftest.py`] → un integrante con otra base de tests debe usar ese nombre (DD-02 ya lo prevé). La guarda `_test` evita migrar la base de desarrollo por error.
- [Test de "grupo protegido vacío"] → es un invariante de CH-01; CH-04/CH-05 lo actualizan al agregar rutas/dependencias.
- [Hash ficticio en `main.py` y no en `security.py`] → CH-04 puede moverlo sin romper a nadie porque el contrato es `app.state.hash_ficticio`.

## Migration Plan

No hay despliegue: es el primer código del repositorio. Se integra por PR de `feat/infra-base` a `main` con revisión de un compañero (`Closes #1`). Rollback: revertir el merge. Cada integrante, después del merge: crear `.venv`, `pip install -r requirements.txt`, copiar `env.example` a `.env` y completarlo, y correr `pytest`.

## Open Questions

- Si la fixture `base_migrada` debe hacer `downgrade base` + `upgrade head` por sesión o sólo `upgrade head` (se decide en CH-02/CH-03, cuando haya tablas y datos que limpiar; no cambia las tareas de CH-01).
