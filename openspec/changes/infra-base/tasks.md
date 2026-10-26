# Tasks

> TDD estricto: en cada grupo, rojo (el test falla por la razón esperada, ejecutado) → verde (código mínimo, ejecutado) → triangulación (otro caso con datos distintos) → refactor (tests verdes tras cada paso). Safety net: no aplica (todos los archivos son nuevos; no hay tests previos).
> Cada grupo numerado termina en **un commit** chico, en español, con el nombre del change, p. ej. `feat(infra-base): ...`. Sin líneas `Co-Authored-By`, `Claude-Session` ni "Generated with Claude Code". Antes de cada commit: `git status` y confirmar que `.env` no aparece.
> Governance ALTO: los puntos marcados **[checkpoint]** se muestran a Belén y se espera su OK antes de seguir.
> No escribir ninguna contraseña ni clave en archivos versionados, en el chat ni en logs.

## 1. Estructura, dependencias y pytest (commit `chore(infra-base): estructura del proyecto, requirements y pytest`)

- [x] 1.1 Crear la estructura: `app/__init__.py`, `app/core/__init__.py`, `app/modules/__init__.py`, `app/modules/{health,usuarios,clientes,repuestos,ordenes}/__init__.py`, `tests/__init__.py` (vacío) y `test/.gitkeep`. NO crear `migrations/` ni `alembic.ini` (design D9). Verificar con `ls -R app tests test` que están todos y nada más
- [x] 1.2 Escribir `requirements.txt` con `paquete>=mínimo` (design D7): `fastapi[standard]>=0.111`, `sqlmodel>=0.0.24`, `sqlalchemy[asyncio]>=2.0`, `asyncpg>=0.30`, `alembic>=1.13`, `pydantic-settings>=2.0`, `bcrypt>=4.0`, `PyJWT>=2.8`, `pytest`, `pytest-asyncio`, `httpx`. Verificar que ningún piso es menor que el de `CLAUDE.md`
- [x] 1.3 Crear el venv con Python 3.14 (`py -3.14 -m venv .venv`) e instalar (`.venv/Scripts/python -m pip install -r requirements.txt`). Verificar: la instalación termina sin errores, `pip check` sin conflictos y `python -c "import fastapi, sqlmodel, sqlalchemy, asyncpg, alembic, pydantic_settings, bcrypt, jwt, pytest, pytest_asyncio, httpx"` funciona. **Si asyncpg no instala en 3.14: PARAR y avisar a Belén; NO cambiar de driver** (DD-01). Si otra dependencia necesita un piso mayor para 3.14, subirlo en `requirements.txt` a la versión que instaló y anotarlo para la bitácora
- [x] 1.4 Registrar las versiones instaladas (`pip freeze` de los paquetes directos) para la bitácora (tarea 8.2) y verificar que `.venv/` no aparece en `git status`
- [x] 1.5 Crear `pytest.ini` (`testpaths = tests`, `asyncio_mode = auto`, `asyncio_default_fixture_loop_scope = function`). Verificar con `.venv/Scripts/python -m pytest` que corre sin errores de configuración (0 tests recolectados, sin advertencias del plugin asyncio)
- [x] 1.6 Commit del grupo 1 tras `git status` limpio de `.env` y `.venv/`

## 2. Configuración sin secretos por defecto (commit `feat(infra-base): Settings con pydantic-settings sin secretos por defecto`)

- [x] 2.1 ROJO: `tests/test_config.py` con fixture autouse que limpia `get_settings.cache_clear()` y un helper que construye `Settings(_env_file=None)` sobre un entorno controlado con `monkeypatch`. Tests: falla sin `POSTGRES_PASSWORD` (el error menciona la variable); falla sin `JWT_SECRET_KEY`. Ejecutar y verificar que fallan porque `app.core.config` no existe
- [x] 2.2 VERDE: `app/core/config.py` con `Settings` (`SecretStr` sin default para ambos secretos, `extra="ignore"`, `env_file=".env"`) y `get_settings()` con `lru_cache`, sin instanciar nada a nivel de módulo. Ejecutar: verdes
- [x] 2.3 TRIANGULAR secretos: secreto vacío (`POSTGRES_PASSWORD=""` y `JWT_SECRET_KEY=""`) falla igual; `JWT_SECRET_KEY` de 31 caracteres falla y de 32 pasa; `repr(settings)` y `str(settings)` no contienen ninguno de los dos valores. Ejecutar: rojo → ajustar (`min_length`) → verde
- [x] 2.4 ROJO→VERDE URL: con los cinco `POSTGRES_*` la `DATABASE_URL` es `postgresql+asyncpg://taller:<pwd>@localhost:5432/taller`; TRIANGULAR con `db.local:5433/taller_test` y con una contraseña con `@`, `:` y `/` (al parsearla con `sqlalchemy.engine.make_url` se recuperan host, puerto y contraseña originales). Implementar con `@computed_field(repr=False)` y `URL.create(...)` (design D1). Ejecutar: verdes
- [x] 2.5 ROJO→VERDE parámetros operativos: defaults (`ACCESS_TOKEN_EXPIRE_SECONDS=1800`, `COOKIE_SECURE=False`, `BCRYPT_COST=12`, `BCRYPT_MAX_CONCURRENT=4`, `DB_POOL_SIZE=5`, `SQL_ECHO=False`, `JWT_ALGORITHM="HS256"`, `POSTGRES_HOST="localhost"`, `POSTGRES_PORT=5432`); TRIANGULAR con valores del entorno (`SQL_ECHO=true`, `COOKIE_SECURE=true`, `BCRYPT_COST=4`, `DB_POOL_SIZE=2` con sus tipos), fuera de rango (`BCRYPT_COST=3`, `DB_POOL_SIZE=0` fallan) y `POSTGRES_DB` faltante falla. Ejecutar: verdes
- [x] 2.6 ROJO→VERDE prioridad: con un `.env` temporal (`tmp_path`) que dice `POSTGRES_DB=taller` y el entorno con `taller_test`, gana `taller_test`; con sólo el `.env` temporal, se toman sus valores. Ejecutar: verdes
- [x] 2.7 REFACTOR: agrupar campos por tema con comentarios breves, extraer constantes de límites; ejecutar `pytest tests/test_config.py` tras cada cambio: verdes
- [x] 2.8 **[checkpoint]** Mostrar a Belén `config.py` y los tests; tras su OK, commit del grupo 2

## 3. env.example y .env local (commit `feat(infra-base): env.example con todas las variables y sin secretos`)

- [x] 3.1 ROJO: `tests/test_env_example.py`: las claves de `env.example` son exactamente los 13 campos de `Settings` (sin `DATABASE_URL`, sin claves de más); `POSTGRES_PASSWORD` y `JWT_SECRET_KEY` tienen valor vacío. Ejecutar: falla porque el archivo no existe
- [x] 3.2 VERDE: escribir `env.example` (orden de `08_arquitectura_propuesta.md`, valores de ejemplo no secretos, `SQL_ECHO=true`, comentario con el comando para generar la clave: `python -c "import secrets; print(secrets.token_urlsafe(64))"`). Ejecutar: verde
- [x] 3.3 TRIANGULAR: los valores no secretos de `env.example` son válidos para `Settings` (construir `Settings(_env_file=None)` con esos valores más secretos de prueba generados en el test) y, con los secretos tal como vienen en `env.example` (vacíos), la construcción falla. Ejecutar: verdes
- [x] 3.4 Crear `.env` (NO versionado) copiando `env.example` con `POSTGRES_USER=taller`, `POSTGRES_DB=taller`, `POSTGRES_HOST=localhost`, `POSTGRES_PORT=5432`; generar `JWT_SECRET_KEY` UNA sola vez con `secrets.token_urlsafe(64)` escribiéndola directo en el archivo (sin imprimirla); `POSTGRES_PASSWORD`: pedírsela a Belén o que ella la escriba en el `.env` (no repetirla en el chat). Verificar con `.venv/Scripts/python -c "from app.core.config import get_settings; get_settings()"` que la config carga (sin imprimir secretos)
- [x] 3.5 Verificar que `.env` no se commitea: `git check-ignore .env` lo devuelve y `git status --porcelain` no lo lista
- [x] 3.6 Commit del grupo 3 (sólo `env.example` y el test)

## 4. Motor, fábrica de sesiones y get_session (commit `feat(infra-base): motor async, fábrica de sesiones y get_session`)

- [x] 4.1 ROJO: `tests/test_database.py`: `crear_motor(settings)` con `DB_POOL_SIZE=2` y `SQL_ECHO=True` devuelve un motor con `engine.pool.size() == 2`, `engine.echo is True` y dialecto/driver `postgresql`/`asyncpg`, sin conectarse. Ejecutar: falla porque `app.core.database` no existe
- [x] 4.2 VERDE: `app/core/database.py` con `crear_motor` (design D2). Ejecutar: verde. TRIANGULAR con `DB_POOL_SIZE=5` y `SQL_ECHO=False`: verde
- [x] 4.3 ROJO→VERDE fábrica: `crear_fabrica_sesiones(engine)` crea sesiones `AsyncSession` (de SQLModel) con `sync_session.expire_on_commit is False`; dos llamadas a la fábrica dan sesiones distintas. Ejecutar: verdes
- [x] 4.4 ROJO→VERDE `get_session`: con una app mínima de test cuyo `app.state.session_factory` es una fábrica real, una ruta que usa `Depends(get_session)` recibe una sesión de esa fábrica; tras la respuesta la sesión está cerrada. TRIANGULAR: una ruta que lanza una excepción también deja la sesión cerrada, y dos peticiones reciben sesiones distintas. Ejecutar: verdes
- [x] 4.5 REFACTOR (tipos y docstrings cortos que citan la regla 7); `pytest tests/test_database.py` verde tras cada paso
- [x] 4.6 Commit del grupo 4

## 5. Lifespan, main.py y nada al importar (commit `feat(infra-base): lifespan con motor en app.state, hash ficticio y dispose`)

- [x] 5.1 ROJO: `tests/test_importacion.py`: en un subproceso (`sys.executable -c`) con `cwd=tmp_path` (sin `.env`), `PYTHONPATH` = raíz del repo y sin `POSTGRES_PASSWORD`/`JWT_SECRET_KEY` en el entorno, `import main` termina con código 0 y `main.app.state` no tiene `engine`, `session_factory` ni `hash_ficticio`. Ejecutar: falla porque `main.py` no existe
- [x] 5.2 VERDE: `main.py` con `lifespan` (design D3), `app = FastAPI(..., lifespan=lifespan)`, sin leer config al importar. Ejecutar: verde. TRIANGULAR: el mismo subproceso importando `app.core.config` y `app.core.database` termina con código 0 (en el grupo 6 se agrega `app.modules.health.router` a este test)
- [x] 5.3 ROJO→VERDE `tests/test_lifespan.py`: dentro de `async with app.router.lifespan_context(app)` (entorno con secretos de prueba, `BCRYPT_COST=4`) el estado tiene `settings`, `engine`, `session_factory`, `bcrypt_semaforo` y `hash_ficticio`; el hash empieza con `$2b$04$` y `bcrypt.checkpw` contra una contraseña cualquiera da `False`. TRIANGULAR con `BCRYPT_COST=5` → `$2b$05$`, y `BCRYPT_MAX_CONCURRENT=2` → el semáforo admite exactamente 2 `acquire` sin bloquear. Ejecutar: verdes
- [x] 5.4 ROJO→VERDE una sola vez: con `monkeypatch` sobre `bcrypt.hashpw` (contador que delega en el original), arrancar la app y hacer varias peticiones a `/health/live` vía cliente → el contador vale 1. Ejecutar: verde
- [x] 5.5 ROJO→VERDE `dispose()`: con un espía sobre `AsyncEngine.dispose`, al salir del lifespan se llamó una vez; TRIANGULAR: si el cuerpo del `async with` lanza una excepción, `dispose()` igual se llamó una vez. Ejecutar: verdes
- [x] 5.6 ROJO→VERDE arranque sin secretos: con `JWT_SECRET_KEY` ausente (y `_env_file` apuntando a un `.env` temporal sin la clave, o `cwd` temporal), entrar al lifespan lanza `ValidationError` antes del `yield`. TRIANGULAR: arranque con `POSTGRES_PORT` de un puerto cerrado termina sin error (el lifespan no conecta). Ejecutar: verdes
- [x] 5.7 ROJO→VERDE grupos de rutas: `rutas_abiertas` y `rutas_protegidas` existen en `main`, `rutas_protegidas` no tiene rutas ni dependencias, y las rutas propias de la app (sin `/docs`, `/redoc`, `/openapi.json`) son sólo las de salud (este test lo actualizan CH-04/CH-05). Dejar el bloque comentado con una línea de `include_router` por change y el comentario sobre el orden (design D4). Ejecutar: verde (hasta el grupo 6 el conjunto esperado de rutas propias es vacío; 6.2 lo cambia a las dos de salud)
- [x] 5.8 `tests/conftest.py` inicial: al importarse fija `os.environ["POSTGRES_DB"] = "taller_test"`; fixture autouse que limpia `get_settings.cache_clear()`; fixture `client` (`lifespan_context` + `httpx.AsyncClient(transport=ASGITransport(app=app))`). Verificar con un test que `client` arranca la app (el estado tiene `engine`) y que `get_settings().POSTGRES_DB == "taller_test"` aunque el `.env` diga `taller`
- [x] 5.9 REFACTOR: helper privado `_calcular_hash_ficticio` en `main.py`, comentarios que citan la regla 7 y el contrato de `app.state`; toda la suite verde tras cada paso
- [x] 5.10 **[checkpoint]** Mostrar a Belén `main.py` y `database.py`; tras su OK, commit del grupo 5

## 6. Salud live y ready (commit `feat(infra-base): endpoints /health/live y /health/ready`)

- [x] 6.1 ROJO: `tests/test_health.py`: `GET /health/live` → 200 `{"estado": "ok"}`. Ejecutar: falla con 404
- [x] 6.2 VERDE: `app/modules/health/router.py` con `live` e incluirlo en `rutas_abiertas` de `main.py`; actualizar el test 5.7 (rutas propias = las dos de salud). Ejecutar: verdes
- [x] 6.3 TRIANGULAR live: con la app arrancada contra un puerto cerrado (`POSTGRES_PORT` sin servidor), `live` sigue dando 200, y un espía sobre `session_factory` confirma que no se creó ninguna sesión. Ejecutar: verde
- [x] 6.4 ROJO→VERDE ready OK: contra la base real `taller_test` (credenciales del `.env`), `GET /health/ready` → 200 `{"estado": "ok", "base": "ok"}`; con `SQL_ECHO=true` se ve el `SELECT 1` en la salida capturada. Implementar con `Depends(get_session)`, `text("SELECT 1")` y `asyncio.wait_for` (design D5). Ejecutar: verde
- [x] 6.5 ROJO→VERDE ready 503 base caída: app arrancada con `POSTGRES_PORT` de un puerto cerrado → 503 con exactamente `{"estado": "no disponible", "base": "no disponible"}`, en menos de ~4 s. Ejecutar: verde
- [x] 6.6 TRIANGULAR 503: contraseña incorrecta contra la base real → 503 con el mismo cuerpo; base inexistente (`POSTGRES_DB=no_existe_test`) → 503; y un caso de demora (monkeypatch de la constante de límite a un valor mínimo con una ejecución que no termina) → 503. En los tres, el cuerpo no contiene `asyncpg`, `Traceback`, `password`, el host ni la contraseña usada. Ejecutar: verdes
- [x] 6.7 REFACTOR: constante `TIEMPO_MAXIMO_READY_SEGUNDOS`, cuerpos como constantes del router, `logger.warning` con sólo el nombre de la clase de la excepción; suite completa verde
- [ ] 6.8 Commit del grupo 6

## 7. Base de tests con Alembic (commit `test(infra-base): fixture de la base taller_test con alembic upgrade head`)

- [x] 7.1 ROJO: `tests/test_entorno_de_pruebas.py`: (a) con `alembic.ini` ausente, un test que pide `base_migrada` termina como *skipped* con el motivo "se ejercita cuando CH-02 agregue las migraciones" (verificar con `pytester` o con `pytest -rs` y el texto del motivo); (b) la guarda rechaza una base que no termina en `_test` sin ejecutar ningún subproceso (espía sobre `subprocess.run`). Ejecutar: fallan porque la fixture no existe
- [x] 7.2 VERDE: fixture `base_migrada` en `tests/conftest.py` (scope `session`, sincrónica; guarda `_test`; skip sin `alembic.ini`; `subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], env=..., check=True)`; nunca `create_all`), con un comentario que dice que se ejercita de punta a punta con CH-02 y que el `env.py` de Alembic debe tomar la URL de `get_settings()` (design D6). Ejecutar: verdes
- [x] 7.3 TRIANGULAR estructura: `app.core` y los cinco `app.modules.<módulo>` se importan; `app/modules/health/` sólo tiene `__init__.py` y `router.py`; `pytest --collect-only -q` no recolecta nada de `test/`. Ejecutar: verdes
- [x] 7.4 REFACTOR de `conftest.py` (constante `BASE_DE_TESTS`, orden de fixtures); suite completa verde
- [ ] 7.5 Commit del grupo 7

## 8. Bitácora (commit `docs(infra-base): bitácora del equipo`)

- [x] 8.1 Crear `docs/bitacora.md` con una sección por integrante (Belén, Elías, Hernán, Bruno, Joaquín) y la plantilla de entrada (fecha, qué le pidió al agente, qué corrigió a mano y por qué). Verificar que están las cinco secciones y los cuatro campos
- [x] 8.2 Redactar el borrador de la entrada de Belén para CH-01 (fecha, pedido al agente, versiones instaladas en 3.14 y cualquier piso de `requirements.txt` que se haya subido, decisiones D1–D9 no obvias) para que ella la revise y complete lo que corrigió a mano
- [ ] 8.3 Commit del grupo 8

## 9. Verificación integral (sin commit)

- [x] 9.1 Correr toda la suite (`.venv/Scripts/python -m pytest -rs`): todo verde salvo los skips explícitos de `base_migrada`; anotar el total
- [x] 9.2 Levantar el servidor (`.venv/Scripts/fastapi dev main.py` o `uvicorn main:app`) y verificar a mano: `curl -i localhost:8000/health/live` → 200; `/health/ready` → 200 y el `SELECT 1` en consola con `SQL_ECHO=true`; con PostgreSQL detenido (o `POSTGRES_PORT` cambiado en el entorno), `/health/ready` → 503 con el cuerpo fijo; al cortar el servidor no hay errores de apagado
- [x] 9.3 Arrancar con `JWT_SECRET_KEY=` vacía en el entorno y verificar que el servidor no levanta y el error nombra la variable sin mostrar valores
- [x] 9.4 Revisar contra las reglas 7, 8 y 17 de `CLAUDE.md` y RN-18: `grep` de `create_async_engine`, `Settings(` y `get_settings(` fuera de funciones; ningún secreto en archivos versionados (un script lee la contraseña y la clave del `.env` sin imprimirlas y corre `git grep -F` con cada una: sin coincidencias); todos los handlers `async def`
- [ ] 9.5 Confirmar el alcance: no hay modelos, `alembic.ini`, `migrations/`, repositorios, UoW, `security.py` ni `dependencies.py`; `git check-ignore .env` OK y `git status` limpio

## Workflow follow-up

- Pendiente para CH-09 (README): cada integrante crea su propio `.env` a partir de `env.example`, su usuario de PostgreSQL y las bases `taller` y `taller_test` (anotado también en `docs/bitacora.md`).
- Abrir PR de `feat/infra-base` a `main` con `Closes #1`, mostrando las decisiones no obvias (governance ALTO) y con la entrada de la bitácora; conseguir la aprobación de un compañero.
- Tras el merge: `/opsx:archive infra-base` y marcar `[x]` el estado de CH-01 en `CHANGES.md`.
- Avisar a Elías (CH-03) y a Belén (CH-02) que la ola 1 puede arrancar; avisar a Hernán (CH-04) del contrato `app.state.hash_ficticio` / `app.state.bcrypt_semaforo` y del cambio de bcrypt 5.x con más de 72 bytes.
