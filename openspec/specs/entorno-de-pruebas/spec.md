# entorno-de-pruebas Specification

## Purpose
Fija la estructura de carpetas del proyecto, que las dependencias del stack se instalen en el entorno del equipo y que la suite automatizada corra contra una base PostgreSQL de prueba separada cuyo esquema sale sólo de las migraciones, para que todos los changes posteriores puedan trabajar con TDD.

## Requirements

### Requirement: Estructura obligatoria del proyecto
El repositorio SHALL tener el punto de entrada `main.py`, el paquete `app/core/` y un paquete por módulo en `app/modules/` (`health`, `usuarios`, `clientes`, `repuestos`, `ordenes`). El módulo `health` MUST tener sólo su router. Las carpetas `test/` (casos `.http` y `solo_agregado.sql`) y `tests/` (suite automatizada) MUST existir y estar separadas.

#### Scenario: Paquetes importables
- **WHEN** se importa cada uno de `app.core` y `app.modules.<módulo>` para los cinco módulos
- **THEN** todas las importaciones funcionan

#### Scenario: health sólo con router
- **WHEN** se listan los archivos Python de `app/modules/health/`
- **THEN** sólo están el router y el archivo de paquete

#### Scenario: test y tests separadas
- **WHEN** se corre la suite automatizada
- **THEN** sólo se recolectan tests de `tests/`, nunca archivos de `test/`

### Requirement: Dependencias instalables en el entorno del equipo
`requirements.txt` SHALL listar las dependencias del stack (framework web con su servidor, SQLModel, SQLAlchemy asincrónico, asyncpg, Alembic, pydantic-settings, bcrypt, PyJWT, pytest, pytest-asyncio y httpx) con versiones mínimas mayores o iguales a las de `CLAUDE.md`. MUST instalarse en un entorno virtual limpio con Python 3.12 o superior, incluido Python 3.14.

#### Scenario: Instalación limpia en Python 3.14
- **WHEN** se crea un entorno virtual con Python 3.14 y se instala `requirements.txt`
- **THEN** la instalación termina sin errores y cada paquete se puede importar

#### Scenario: Mínimos respetados
- **WHEN** se revisan las versiones mínimas declaradas en `requirements.txt`
- **THEN** ninguna es menor que la mínima que fija `CLAUDE.md` para ese paquete

### Requirement: Suite asincrónica contra la aplicación
La suite SHALL poder ejercitar la aplicación con un cliente HTTP asincrónico en proceso, con el arranque y el apagado de la aplicación ejecutados alrededor de cada uso del cliente.

#### Scenario: Cliente con la app arrancada
- **WHEN** un test usa el cliente HTTP de la suite
- **THEN** la aplicación ya ejecutó su arranque y el cliente puede pedir `/health/live`

### Requirement: Base de pruebas separada y creada con Alembic
Los tests que necesitan esquema SHALL usar una base distinta de la de desarrollo (`taller_test`), con las mismas credenciales del `.env`. Su esquema MUST crearse ejecutando `alembic upgrade head` y nunca creando tablas desde los modelos. La suite MUST negarse a migrar una base cuyo nombre no termine en `_test`.

#### Scenario: La suite apunta a taller_test
- **WHEN** corre la suite
- **THEN** la configuración que usa la aplicación bajo prueba tiene `POSTGRES_DB=taller_test`, aunque el `.env` diga `taller`

#### Scenario: Protección de la base de desarrollo
- **WHEN** la base de pruebas configurada no termina en `_test`
- **THEN** la preparación del esquema falla sin ejecutar migraciones

#### Scenario: Antes de que existan migraciones
- **WHEN** todavía no existe la configuración de Alembic en el repositorio (antes de CH-02)
- **THEN** los tests que piden la base migrada se saltean con un motivo explícito y el resto de la suite corre normalmente

#### Scenario: Esquema desde las migraciones
- **WHEN** existe la configuración de Alembic y un test pide la base migrada
- **THEN** la suite ejecuta `alembic upgrade head` sobre `taller_test` antes del test

### Requirement: Bitácora del equipo
El repositorio SHALL incluir `docs/bitacora.md` con una sección por integrante (Belén, Elías, Hernán, Bruno, Joaquín), y cada entrada MUST registrar fecha, qué se le pidió al agente, qué se corrigió a mano y por qué.

#### Scenario: Secciones por integrante
- **WHEN** se abre `docs/bitacora.md`
- **THEN** hay una sección para cada uno de los cinco integrantes y una plantilla de entrada con los cuatro datos
