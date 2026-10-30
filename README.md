# Taller Mecánico API

API asincrónica para un taller mecánico: órdenes de trabajo, stock de repuestos y control de acceso por roles. Trabajo práctico integrador de Programación III (UTN).

- Consigna: [docs/consigna-tp.md](docs/consigna-tp.md)
- Roadmap de changes: [CHANGES.md](CHANGES.md)
- Base de conocimiento: [knowledge-base/](knowledge-base/)
- Bitácora del equipo: [docs/bitacora.md](docs/bitacora.md)
- Evidencias de entrega: [docs/evidencias/](docs/evidencias/)

**Stack:** Python 3.12 o superior, FastAPI, SQLModel, SQLAlchemy 2.0 asincrónico, asyncpg, PostgreSQL 16 o superior (instalado en la máquina, sin Docker), Alembic, pydantic-settings, bcrypt y PyJWT.

> Todos los comandos de este README se corren **desde la raíz del repositorio**. El `.env` se lee relativo al directorio actual: desde otra carpeta, Alembic y `seed.py` no lo encuentran y fallan con un error de configuración (no dejan un esquema a medias).

## 1. Puesta en marcha desde cero

### 1.1 Entorno virtual y dependencias

En Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

En Linux o macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Con el entorno activado, los comandos de abajo usan `python`, `alembic`, `uvicorn` y `pytest` a secas. (Probado con Python 3.14; la consigna pide 3.12 o superior. `asyncpg>=0.31` porque la 0.30 no tiene versión precompilada para Python 3.14 y es compatible con 3.12 y 3.13.)

### 1.2 Usuario y bases en PostgreSQL

Hacen falta **dos bases**: `taller` (desarrollo) y `taller_test` (la usa la suite de pytest). Conectate como superusuario (por ejemplo `psql -U postgres`) y corré, **eligiendo vos la contraseña**:

```sql
CREATE USER taller WITH PASSWORD '<elegí-una-contraseña>';
CREATE DATABASE taller OWNER taller;
CREATE DATABASE taller_test OWNER taller;
```

Cada integrante usa su propio usuario y su propia contraseña: no se comparten ni se suben al repositorio.

### 1.3 Variables de entorno (`.env`)

```bash
cp env.example .env
```

(en PowerShell: `Copy-Item env.example .env`). Después editá `.env` y completá:

| Variable | Qué es | Por defecto en `env.example` |
|---|---|---|
| `POSTGRES_USER` | usuario de la base | `taller` |
| `POSTGRES_PASSWORD` | contraseña de la base. **Obligatoria**: sin ella la app no arranca | vacía |
| `POSTGRES_DB` | base de desarrollo | `taller` |
| `POSTGRES_HOST`, `POSTGRES_PORT` | dónde escucha PostgreSQL | `localhost`, `5432` |
| `JWT_SECRET_KEY` | clave de firma del token. **Obligatoria**, mínimo 32 caracteres | vacía |
| `JWT_ALGORITHM` | algoritmo de firma | `HS256` |
| `ACCESS_TOKEN_EXPIRE_SECONDS` | duración de la sesión (es también el `Max-Age` de la cookie) | `1800` |
| `COOKIE_SECURE` | `true` sólo si se sirve por HTTPS | `false` |
| `BCRYPT_COST` | costo de bcrypt | `12` |
| `BCRYPT_MAX_CONCURRENT` | hashes de bcrypt a la vez (semáforo) | `4` |
| `DB_POOL_SIZE` | tamaño del pool de conexiones | `5` |
| `SQL_ECHO` | `true` muestra las consultas SQL en la consola | `true` |

**Cómo generar la clave de firma (`JWT_SECRET_KEY`)**: se genera **una sola vez** y se pega en `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

La clave es FIJA: no se genera al arrancar la app, no se vuelve a generar en cada arranque (si cambia, todas las sesiones abiertas dejan de valer), no se comparte y no se versiona. `.env` está en `.gitignore`; `env.example` no lleva ningún secreto. Si falta la clave o la contraseña de la base, la aplicación no arranca.

### 1.4 Esquema de la base (Alembic)

El esquema se crea **sólo con Alembic** (la aplicación nunca usa `create_all`). Hay dos versiones en `migrations/versions/`: la primera autogenerada y la segunda escrita a mano con el disparador de sólo agregado.

```bash
alembic upgrade head
```

Verificá que las migraciones son reversibles:

```bash
alembic downgrade base
alembic upgrade head
alembic current
```

El último comando tiene que mostrar `0002 (head)`.

### 1.5 Datos iniciales (`seed.py`)

```bash
python seed.py
```

`seed.py` **vacía las tablas** y carga los datos iniciales (el catálogo de estados primero). Es parte de la puesta en marcha. Vuelve a dejar la base en el mismo punto cada vez que se corre.

| Qué | Contenido |
|---|---|
| Estados de orden | `PENDIENTE` (1), `EN_REPARACION` (2), `TERMINADA` (3, final), `CANCELADA` (4, final) |
| Usuarios | `admin@example.com` y `admin2@example.com` (ADMIN), `recepcion@example.com` (RECEPCION), `mecanico@example.com` y `mecanico2@example.com` (MECANICO), `cliente@example.com` (CLIENTE), `nuevo@example.com` (MECANICO con cambio de contraseña obligatorio) |
| Clientes | Laura (con usuario y dos vehículos) y Jorge (sin usuario, con un vehículo) |
| Repuestos | filtro de aceite (stock 10), pastillas de freno (4), bujía (2), aceite por litro (20) |
| Órdenes | la 1 `PENDIENTE` y la 2 `EN_REPARACION` (con 4 bujías cuando hay 2, a propósito para C-11) |

Las contraseñas de estos usuarios son de prueba y viven sólo en `seed.py`.

### 1.6 Levantar el servidor

```bash
uvicorn main:app --reload
```

- API en `http://localhost:8000` (documentación interactiva en `/docs`).
- Comprobación: `GET http://localhost:8000/health/live` responde `200` con `{"estado":"ok"}`.

### 1.7 Ver las consultas SQL (`SQL_ECHO`)

Con `SQL_ECHO=true` en `.env` (es el valor de `env.example`), cada consulta se imprime en la consola donde corre el servidor. Es lo que se usa para la evidencia de C-15. Para apagarlo, poné `SQL_ECHO=false` y reiniciá. También se puede activar sólo para una corrida, porque una variable del entorno pisa al `.env`:

```bash
SQL_ECHO=true uvicorn main:app
```

(PowerShell: `$env:SQL_ECHO="true"; uvicorn main:app`.)

## 2. Pruebas: `tests/` y `test/`

| Carpeta | Qué tiene | Cómo se usa |
|---|---|---|
| `tests/` | la suite automatizada **pytest** (pytest, pytest-asyncio y httpx) | `pytest` |
| `test/` | los casos de prueba de la consigna: archivos **`.http`** (C-01 a C-19, uno por caso, cada uno con la respuesta esperada en un comentario) y `solo_agregado.sql` (C-14) | REST Client / `psql` |

### 2.1 Suite pytest

La suite corre contra **`taller_test`** (nunca toca `taller`: fuerza `POSTGRES_DB=taller_test`) y migra esa base con `alembic upgrade head` al empezar. Tiene que estar creada (paso 1.2); el resto de las credenciales sale de tu `.env`.

```bash
pytest
```

- La suite deja `taller_test` **vacía** al terminar. Si sembraste `taller_test` a mano con `seed.py`, vaciala antes de volver a correr la suite (o `alembic downgrade base` + `alembic upgrade head` sobre esa base).
- `pytest` sólo recolecta `tests/`: nunca ejecuta nada de `test/`.

### 2.2 Casos `.http` (C-01 a C-19)

Se corren con la extensión **REST Client** de VS Code, con el servidor levantado y **corriendo `python seed.py` antes de cada archivo** (cada caso parte de los mismos datos):

```bash
python seed.py
```

Cuando un archivo necesita varias sesiones a la vez (por ejemplo C-07), cada login lleva `# @name` y los pedidos de esa sesión llevan `# @no-cookie-jar` y el encabezado `Cookie: {{loginAdmin.response.headers.Set-Cookie}}`.

| Caso | Tema |
|---|---|
| C-01 | parámetro de ruta no entero, 422 |
| C-02 | registro de cliente, 409 con mensaje propio |
| C-03 | login con cookie HttpOnly; sin cookie o con `Authorization: Bearer`, 401 |
| C-04 | mismo 401 exista o no el correo |
| C-05 | seis intentos fallidos, el sexto es 429 con `Retry-After` |
| C-06 | 401 contra 403; el cliente ve su orden y no la ajena |
| C-07 | revocación de un rol con la sesión abierta; vencimientos inválidos |
| C-08 | autoprotección del administrador |
| C-09 | cambio de contraseña obligatorio |
| C-10 a C-13 | órdenes: alta con ítems, terminar sin stock, reponer y terminar, cancelar |
| C-14 | `solo_agregado.sql`: UPDATE y DELETE rechazados por el disparador y la clave foránea (ver abajo) |
| C-15 | detalle de una orden con 2 y con 4 ítems: la misma cantidad de consultas (ver abajo) |
| C-16 | búsqueda con comillas, paginación con filtro, PATCH parcial |
| C-17 | catálogo de estados y filtro de órdenes |
| C-18 | historial de precios y permiso |
| C-19 | baja de un vehículo y reutilización de la patente |

Los `.http` de C-06, C-10 a C-13, C-15 y C-17 y la evidencia de C-15 (`docs/evidencias/C-15_consola.txt`) llegan con CH-08 (órdenes).

### 2.3 C-14: sólo agregado (psql)

Con la base migrada y sembrada:

```bash
psql -U taller -d taller -f test/solo_agregado.sql
```

Tienen que salir **siete errores**: seis del disparador de sólo agregado (UPDATE y DELETE sobre `historial_estado_orden`, `movimiento_stock` e `historial_precio_repuesto`) y uno de la clave foránea `fk_orden_trabajo_estado_estado_orden` (estado inexistente). El idioma del texto de los errores depende del servidor; el nombre de la restricción no. Salida de referencia: [docs/evidencias/C-14_salida_psql.txt](docs/evidencias/C-14_salida_psql.txt).

Captura de psql con los siete errores: [docs/evidencias/C-14_psql.png](docs/evidencias/C-14_psql.png). Los acentos salen mal en la captura por la codificación de la consola de Windows (psql + Git Bash/PowerShell); la salida con los acentos correctos está en [docs/evidencias/C-14_salida_psql.txt](docs/evidencias/C-14_salida_psql.txt).

### 2.4 C-15: consultas del detalle de una orden

Con `SQL_ECHO=true`, pedir el detalle de una orden con 2 ítems y el de otra con 4 y comparar la cantidad de consultas que aparecen en la consola del servidor: tiene que ser la misma. El fragmento de consola queda en `docs/evidencias/C-15_consola.txt`.

## 3. Estructura del proyecto

```
main.py              app, lifespan, grupo de rutas abierto y grupo protegido
seed.py              vacía las tablas y carga los datos iniciales
app/core/            configuración, base, seguridad, dependencias, repositorio base,
                     paginación y unit of work
app/modules/         health, usuarios, clientes, repuestos y ordenes
                     (router → service → unit of work → repository → model)
migrations/          Alembic (dos versiones)
tests/               suite pytest
test/                casos .http y solo_agregado.sql
docs/                consigna, bitácora y evidencias
```

## 4. Notas

- Motor y fábrica de sesiones se crean en el lifespan y viven en `app.state`; el lifespan calcula una vez el hash ficticio del login y hace `dispose()` al apagar.
- bcrypt corre con `asyncio.to_thread` y un semáforo, y los campos que van a bcrypt admiten como máximo 72 **bytes** (con más, el contrato responde 422). Con bcrypt 5.x una contraseña de más de 72 bytes ya no se trunca en silencio sino que da error: por eso el límite se valida antes.
- El token JWT viaja sólo en la cookie `access_token` (HttpOnly, SameSite=Lax); nunca en el cuerpo ni en `Authorization`.
- Trabajo en equipo (Belén, Elías, Hernán, Bruno y Joaquín): una rama `feat/<change>` por change, PR a `main` con la aprobación de un compañero. Ver [CONTRIBUTING.md](CONTRIBUTING.md) y la [bitácora](docs/bitacora.md).
