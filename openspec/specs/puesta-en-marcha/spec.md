# puesta-en-marcha Specification

## Purpose
Define lo que tiene que haber en el repositorio para que cualquier persona lo levante desde cero siguiendo el README, y para que la entrega no lleve credenciales ni archivos que falten.

## Requirements

### Requirement: README con los pasos de arranque desde cero
El `README.md` SHALL describir, en orden, cómo levantar el proyecto en un equipo sin nada instalado del proyecto: entorno virtual, `pip install -r requirements.txt`, creación del usuario y de las bases `taller` y `taller_test` en el PostgreSQL local (sin Docker), copia de `env.example` a `.env`, `alembic upgrade head`, `python seed.py` y arranque del servidor. Cada comando MUST poder copiarse y correrse tal cual desde la raíz del repositorio.

#### Scenario: Arranque siguiendo sólo el README
- **WHEN** alguien con PostgreSQL 16 o superior y Python 3.12 o superior sigue el README paso a paso en un clon limpio
- **THEN** el servidor queda escuchando y `GET /health/live` responde 200 sin que haga falta ninguna acción que el README no mencione

#### Scenario: Migraciones reversibles
- **WHEN** se ejecutan `alembic upgrade head`, `alembic downgrade base` y otra vez `alembic upgrade head` sobre una base vacía
- **THEN** los tres comandos terminan sin error y el README documenta esa verificación

### Requirement: Clave de firma fija y sin secretos en el repositorio
El README SHALL explicar cómo generar `JWT_SECRET_KEY` una sola vez, con un comando que usa un generador criptográfico, y MUST aclarar que se guarda sólo en `.env`, que no se comparte ni se versiona y que no se vuelve a generar en cada arranque. El repositorio MUST NOT contener contraseñas ni claves de firma reales, ni en `env.example`, ni en `alembic.ini`, ni como valor por defecto en el código.

#### Scenario: env.example sin valores secretos
- **WHEN** se lee `env.example`
- **THEN** `POSTGRES_PASSWORD` y `JWT_SECRET_KEY` están vacías y no hay ninguna otra credencial

#### Scenario: alembic.ini sin credenciales
- **WHEN** se busca en `alembic.ini` una URL de conexión con usuario o contraseña
- **THEN** no hay ninguna; la conexión sale de la configuración leída del `.env`

#### Scenario: .env fuera del repositorio
- **WHEN** se ejecuta `git ls-files` y `git check-ignore .env`
- **THEN** `.env` no está versionado y está ignorado

### Requirement: Diagnóstico de consultas y uso de las dos carpetas de pruebas
El README SHALL explicar cómo ver las consultas SQL en la consola con `SQL_ECHO=true`, qué contiene `tests/` (suite pytest contra `taller_test`) y qué contiene `test/` (archivos `.http` y `solo_agregado.sql`), cómo correr la suite y que `python seed.py` se corre antes de cada archivo `.http`. También MUST decir que `taller_test` queda vacía tras la suite y que hay que vaciarla antes de correrla si se sembró a mano.

#### Scenario: Consultas visibles en la consola
- **WHEN** se levanta el servidor con `SQL_ECHO=true` y se hace un pedido que consulta la base
- **THEN** la consola muestra las sentencias SQL, como indica el README

#### Scenario: Suite verde
- **WHEN** se corre `pytest` con `taller_test` creada con `alembic upgrade head`, como indica el README
- **THEN** todos los tests pasan

### Requirement: Archivos de entrega completos
El repositorio SHALL contener `requirements.txt`, `env.example`, `alembic.ini`, la carpeta `migrations/` con exactamente dos versiones (la primera autogenerada y la segunda escrita a mano con el disparador de sólo agregado, cada una con el comentario de que se leyó antes de aplicarla) y la carpeta `test/`. Todas las fechas, el dinero y las claves foráneas MUST respetar las reglas de `CLAUDE.md`; esta revisión sólo informa, no corrige código ajeno.

#### Scenario: Lista de archivos presente
- **WHEN** se recorre el checklist de entrega
- **THEN** cada uno de `requirements.txt`, `env.example`, `alembic.ini`, `migrations/` (2 versiones) y `test/` figura como presente y verificado

#### Scenario: Hallazgo en código ajeno
- **WHEN** la revisión encuentra un incumplimiento en código escrito por otro integrante
- **THEN** se lista con el archivo y el dueño del change para avisarle y no se modifica
