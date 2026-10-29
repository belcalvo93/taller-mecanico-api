# migraciones Specification

## Purpose

Garantiza que el esquema de la base se crea y se deshace exclusivamente con migraciones versionadas de Alembic (plantilla asincrónica), sin credenciales en el repositorio, y que el ciclo completo funciona sobre una base vacía.

## Requirements

### Requirement: Esquema creado sólo por migraciones
El esquema SHALL crearse únicamente aplicando las migraciones (`alembic upgrade head`). Ni la aplicación, ni `seed.py`, ni las migraciones, ni la suite MUST crear tablas del esquema real a partir de los modelos (`create_all`).

#### Scenario: Upgrade sobre base vacía
- **WHEN** se ejecuta `alembic upgrade head` sobre una base sin tablas
- **THEN** termina sin error y quedan creadas las 13 tablas, la tabla de versiones con la última revisión, la función y los disparadores de sólo agregado

#### Scenario: Nadie usa create_all
- **WHEN** se busca `create_all` en el código de la aplicación, `seed.py`, `migrations/` y `tests/`
- **THEN** no aparece ninguna llamada sobre los metadatos de los modelos de la aplicación

### Requirement: Configuración de Alembic sin credenciales
`alembic.ini` MUST NOT contener URL, usuario ni contraseña de la base. Alembic SHALL tomar la conexión de la misma configuración que la aplicación (variables de entorno o `.env`), con driver asincrónico, de modo que cambiar `POSTGRES_DB` cambie la base migrada.

#### Scenario: alembic.ini limpio
- **WHEN** se lee `alembic.ini`
- **THEN** no tiene una `sqlalchemy.url` con valor ni ningún texto con forma de URL de base de datos o contraseña

#### Scenario: La base sale del entorno
- **WHEN** se ejecuta `alembic upgrade head` con `POSTGRES_DB=taller_test`
- **THEN** se migra `taller_test` y no la base de desarrollo

#### Scenario: Sin contraseña no migra
- **WHEN** se ejecuta Alembic sin `POSTGRES_PASSWORD` en el entorno ni en el `.env`
- **THEN** falla antes de conectarse con un error de configuración

### Requirement: Dos migraciones en cadena
El historial SHALL tener exactamente dos revisiones lineales: la primera, generada con `--autogenerate`, crea todas las tablas, restricciones e índices (incluidos los parciales) y deja `estado_orden` vacía; la segunda, escrita a mano y que depende de la primera, instala el sólo agregado.

#### Scenario: Historial lineal de dos revisiones
- **WHEN** se listan las revisiones de Alembic
- **THEN** hay exactamente dos, la segunda tiene a la primera como anterior y la segunda es la única cabeza

#### Scenario: Catálogo vacío tras migrar
- **WHEN** se aplica `upgrade head` sobre una base vacía
- **THEN** `estado_orden` existe y tiene cero filas (y lo mismo todas las demás tablas)

#### Scenario: Primera migración sola
- **WHEN** se aplica sólo la primera revisión
- **THEN** existen las 13 tablas con sus índices parciales y todavía no existe el disparador de sólo agregado

#### Scenario: Modelos y migración coinciden
- **WHEN** con la base en `head` se compara el esquema con los modelos (`alembic check`)
- **THEN** no se detectan diferencias pendientes

### Requirement: Comentario de lectura previa
Cada archivo de migración SHALL llevar, al principio, un comentario que diga que se leyó antes de aplicarla, quién la leyó y qué se corrigió a mano (o que no se corrigió nada).

#### Scenario: Ambas migraciones comentadas
- **WHEN** se abre cada archivo de `migrations/versions/`
- **THEN** cada uno contiene el comentario de lectura previa

### Requirement: Ciclo upgrade, downgrade, upgrade
`alembic downgrade base` SHALL deshacer todo lo creado por las migraciones (tablas, índices, función y disparadores), y un nuevo `upgrade head` MUST dejar el mismo esquema que el primero.

#### Scenario: Downgrade completo
- **WHEN** después de `upgrade head` se ejecuta `downgrade base`
- **THEN** no queda ninguna de las 13 tablas, ni la función ni los disparadores, y la tabla de versiones queda sin revisión

#### Scenario: Volver a subir
- **WHEN** después del `downgrade base` se ejecuta otra vez `upgrade head`
- **THEN** termina sin error y el esquema (tablas, columnas, restricciones, índices y disparadores) es igual al del primer `upgrade`

#### Scenario: Downgrade con datos cargados
- **WHEN** la base tiene los datos iniciales cargados y se ejecuta `downgrade base`
- **THEN** termina sin error, aunque haya filas en las tablas de sólo agregado

### Requirement: Base de pruebas migrada
La suite SHALL preparar `taller_test` con `upgrade head` antes de los tests que necesitan esquema; los tests que antes se salteaban por falta de migraciones MUST ejecutarse.

#### Scenario: La fixture deja de saltearse
- **WHEN** se corre la suite completa con las migraciones presentes
- **THEN** el test que verifica la tabla de versiones de `taller_test` se ejecuta y pasa
