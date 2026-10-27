# Spec Delta

## Purpose

Define cómo la aplicación obtiene su configuración del entorno o de un archivo `.env` no versionado, qué variables son obligatorias, cómo se arma la URL de la base y qué contrato cumple `env.example`, de modo que el repositorio nunca contenga secretos.

## ADDED Requirements

### Requirement: Configuración leída del entorno o de un .env no versionado
La aplicación SHALL leer toda su configuración desde variables de entorno o, en su defecto, desde un archivo `.env` en la raíz del proyecto. Las variables de entorno MUST tener prioridad sobre el `.env`. Variables desconocidas en el entorno MUST ignorarse sin error.

#### Scenario: Valores tomados del entorno
- **WHEN** las variables obligatorias están definidas en el entorno del proceso y no existe `.env`
- **THEN** la configuración se construye con esos valores

#### Scenario: El entorno pisa al .env
- **WHEN** `POSTGRES_DB` vale `taller` en el `.env` y `taller_test` en el entorno del proceso
- **THEN** la configuración usa `taller_test`

### Requirement: Contraseña de la base y clave de firma obligatorias y sin valor por defecto
`POSTGRES_PASSWORD` y `JWT_SECRET_KEY` MUST NOT tener valor por defecto en el código. Si alguna falta o está vacía, construir la configuración MUST fallar y la aplicación MUST NOT arrancar. `JWT_SECRET_KEY` MUST tener al menos 32 caracteres. El mensaje de error MUST nombrar la variable faltante sin mostrar el valor de ningún secreto.

#### Scenario: Falta POSTGRES_PASSWORD
- **WHEN** se construye la configuración sin `POSTGRES_PASSWORD` en el entorno ni en un `.env`
- **THEN** la construcción falla con un error de validación que menciona `POSTGRES_PASSWORD`

#### Scenario: Falta JWT_SECRET_KEY
- **WHEN** se construye la configuración sin `JWT_SECRET_KEY`
- **THEN** la construcción falla con un error de validación que menciona `JWT_SECRET_KEY`

#### Scenario: Secreto vacío copiado de env.example
- **WHEN** `POSTGRES_PASSWORD` o `JWT_SECRET_KEY` están definidas pero vacías
- **THEN** la construcción falla igual que si faltaran

#### Scenario: Clave de firma demasiado corta
- **WHEN** `JWT_SECRET_KEY` tiene menos de 32 caracteres
- **THEN** la construcción falla con un error de validación que menciona `JWT_SECRET_KEY`

#### Scenario: Los secretos no se exponen al representar la configuración
- **WHEN** se convierte la configuración a texto (repr o str)
- **THEN** el texto no contiene el valor de `POSTGRES_PASSWORD` ni el de `JWT_SECRET_KEY`

#### Scenario: La app no arranca sin secretos
- **WHEN** se inicia la aplicación sin `JWT_SECRET_KEY` disponible
- **THEN** el arranque falla antes de atender peticiones

### Requirement: URL de la base computada con driver asincrónico
La configuración SHALL exponer una URL de conexión calculada a partir de `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` y `POSTGRES_DB`, con el esquema `postgresql+asyncpg`. La URL MUST NOT poder fijarse directamente desde el entorno y MUST escapar caracteres especiales del usuario y la contraseña.

#### Scenario: URL armada con los cinco valores
- **WHEN** `POSTGRES_USER=taller`, `POSTGRES_HOST=localhost`, `POSTGRES_PORT=5432`, `POSTGRES_DB=taller` y una contraseña dada
- **THEN** la URL es `postgresql+asyncpg://taller:<contraseña>@localhost:5432/taller`

#### Scenario: Contraseña con caracteres especiales
- **WHEN** la contraseña contiene `@`, `:` o `/`
- **THEN** la URL los codifica y al interpretarla se recuperan el host, el puerto y la contraseña originales

#### Scenario: Otro host, puerto y base
- **WHEN** `POSTGRES_HOST=db.local`, `POSTGRES_PORT=5433` y `POSTGRES_DB=taller_test`
- **THEN** la URL apunta a `db.local:5433/taller_test` con el mismo esquema `postgresql+asyncpg`

### Requirement: Parámetros operativos declarados en la configuración
La configuración SHALL declarar, con valores por defecto no secretos y validados: `JWT_ALGORITHM` (`HS256`), `ACCESS_TOKEN_EXPIRE_SECONDS` (1800, mayor que 0), `COOKIE_SECURE` (falso), `BCRYPT_COST` (12, entre 4 y 31), `BCRYPT_MAX_CONCURRENT` (4, al menos 1), `DB_POOL_SIZE` (5, al menos 1) y `SQL_ECHO` (falso).

#### Scenario: Valores por defecto
- **WHEN** sólo se definen las variables obligatorias
- **THEN** `ACCESS_TOKEN_EXPIRE_SECONDS` vale 1800, `COOKIE_SECURE` es falso, `BCRYPT_COST` vale 12, `BCRYPT_MAX_CONCURRENT` vale 4, `DB_POOL_SIZE` vale 5 y `SQL_ECHO` es falso

#### Scenario: Valores tomados del entorno
- **WHEN** el entorno define `SQL_ECHO=true`, `COOKIE_SECURE=true`, `BCRYPT_COST=4` y `DB_POOL_SIZE=2`
- **THEN** la configuración refleja esos cuatro valores con su tipo (booleanos y enteros)

#### Scenario: Valor fuera de rango
- **WHEN** `BCRYPT_COST=3` o `DB_POOL_SIZE=0`
- **THEN** la construcción de la configuración falla con un error de validación

### Requirement: Datos de conexión no secretos
`POSTGRES_USER` y `POSTGRES_DB` MUST ser obligatorias (sin valor por defecto). `POSTGRES_HOST` y `POSTGRES_PORT` SHALL tener por defecto `localhost` y `5432`.

#### Scenario: Host y puerto por defecto
- **WHEN** no se definen `POSTGRES_HOST` ni `POSTGRES_PORT`
- **THEN** la configuración usa `localhost` y `5432`

#### Scenario: Falta POSTGRES_DB
- **WHEN** se construye la configuración sin `POSTGRES_DB`
- **THEN** la construcción falla con un error de validación que menciona `POSTGRES_DB`

### Requirement: env.example completo y sin secretos
El repositorio SHALL incluir `env.example` con todas las variables que la configuración acepta. `POSTGRES_PASSWORD` y `JWT_SECRET_KEY` MUST figurar sin valor. El archivo `.env` MUST NOT versionarse.

#### Scenario: Todas las variables listadas
- **WHEN** se comparan las claves de `env.example` con los campos de la configuración
- **THEN** cada campo configurable aparece en `env.example`, y no hay claves de más

#### Scenario: Secretos vacíos
- **WHEN** se lee `env.example`
- **THEN** `POSTGRES_PASSWORD` y `JWT_SECRET_KEY` aparecen con valor vacío

#### Scenario: .env ignorado por git
- **WHEN** existe un `.env` en la raíz del proyecto
- **THEN** `git check-ignore .env` lo reporta como ignorado y no aparece en `git status`
