# ciclo-de-vida Specification

## Purpose
Define cuándo y dónde se crean y se liberan los recursos compartidos de la aplicación (motor de la base, fábrica de sesiones, semáforo de bcrypt y hash ficticio del login), cómo cada petición obtiene su sesión, y la organización de las rutas en un grupo abierto y uno protegido.

## Requirements

### Requirement: Ningún recurso se crea al importar un módulo
Importar cualquier módulo de la aplicación (incluido el punto de entrada) MUST NOT leer la configuración, crear el motor de la base, la fábrica de sesiones, el semáforo de bcrypt ni calcular hashes. Esos recursos SHALL crearse sólo al arrancar la aplicación (lifespan).

#### Scenario: Importar sin variables de entorno
- **WHEN** se importa el punto de entrada de la aplicación en un proceso sin `POSTGRES_PASSWORD` ni `JWT_SECRET_KEY` y sin `.env`
- **THEN** la importación termina sin error

#### Scenario: Estado vacío antes del arranque
- **WHEN** se importa la aplicación y todavía no se ejecutó el arranque
- **THEN** el estado de la aplicación no contiene motor, fábrica de sesiones ni hash ficticio

### Requirement: Motor y fábrica de sesiones creados en el arranque
Al arrancar, la aplicación SHALL crear un único motor asincrónico y una única fábrica de sesiones y guardarlos en el estado de la aplicación. El motor MUST usar la URL, el tamaño de pool y el `SQL_ECHO` de la configuración. La fábrica MUST crear sesiones asincrónicas que no expiren los objetos al confirmar. El arranque MUST NOT conectarse a la base.

#### Scenario: Recursos disponibles tras el arranque
- **WHEN** la aplicación termina de arrancar
- **THEN** su estado contiene el motor y la fábrica de sesiones

#### Scenario: Pool y eco desde la configuración
- **WHEN** se arranca con `DB_POOL_SIZE=2` y `SQL_ECHO=true`
- **THEN** el motor tiene un pool de tamaño 2 y el eco de SQL activado

#### Scenario: Sesiones sin expiración al confirmar
- **WHEN** se crea una sesión con la fábrica del estado
- **THEN** la sesión tiene desactivada la expiración de objetos al confirmar

#### Scenario: Arranque con la base caída
- **WHEN** se arranca la aplicación con la base inaccesible
- **THEN** el arranque termina sin error (la disponibilidad de la base la informa `/health/ready`)

### Requirement: Una sesión por petición tomada del estado de la aplicación
La aplicación SHALL proveer una dependencia que entregue a cada petición una sesión nueva creada con la fábrica guardada en el estado de la aplicación, y que la cierre al terminar la petición, incluso si la petición falla.

#### Scenario: Sesión distinta por petición
- **WHEN** dos peticiones usan la dependencia de sesión
- **THEN** cada una recibe una sesión distinta creada con la fábrica del estado

#### Scenario: Cierre al terminar
- **WHEN** termina la petición que usó la sesión, con éxito o con una excepción
- **THEN** la sesión queda cerrada

### Requirement: Hash ficticio calculado una sola vez al arrancar
Al arrancar, la aplicación SHALL calcular una única vez un hash bcrypt ficticio (con el costo de la configuración, fuera del bucle de eventos y bajo el semáforo de bcrypt) y guardarlo en el estado, para que el login lo use cuando el correo no existe. El semáforo SHALL crearse en el arranque con el tamaño `BCRYPT_MAX_CONCURRENT`.

#### Scenario: Hash disponible tras el arranque
- **WHEN** la aplicación termina de arrancar con `BCRYPT_COST=4`
- **THEN** el estado contiene un hash bcrypt válido con costo 4

#### Scenario: Calculado exactamente una vez
- **WHEN** la aplicación arranca y atiende varias peticiones
- **THEN** el hash ficticio se calculó una sola vez, durante el arranque

#### Scenario: Semáforo con el tamaño configurado
- **WHEN** se arranca con `BCRYPT_MAX_CONCURRENT=2`
- **THEN** el estado contiene un semáforo que admite 2 usos simultáneos

### Requirement: Liberación del motor al apagar
Al apagarse, la aplicación SHALL cerrar el motor de la base liberando todas sus conexiones, exactamente una vez.

#### Scenario: dispose al apagar
- **WHEN** la aplicación se apaga después de haber arrancado
- **THEN** el motor se cierra (dispose) una vez

#### Scenario: dispose aunque haya habido errores
- **WHEN** una petición falló durante la vida de la aplicación y luego la aplicación se apaga
- **THEN** el motor se cierra igual

### Requirement: Dos grupos de rutas
La aplicación SHALL organizar sus rutas en dos grupos: uno abierto (salud y `/auth/*`) y uno protegido, reservado para las rutas que llevarán el control del cambio obligatorio de contraseña montado una sola vez. En este change el grupo protegido MUST quedar sin rutas ni dependencias.

#### Scenario: Salud en el grupo abierto
- **WHEN** se piden `/health/live` o `/health/ready` sin cookie de sesión
- **THEN** se atienden sin exigir autenticación

#### Scenario: Grupo protegido vacío
- **WHEN** se listan las rutas de la aplicación
- **THEN** las únicas rutas propias son las de salud (más la documentación automática)
