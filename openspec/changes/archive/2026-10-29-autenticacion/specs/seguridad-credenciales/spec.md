# Spec Delta

## Purpose

Centraliza en `app/core/security.py` el cálculo y la verificación asincrónica de hashes `bcrypt` fuera del bucle de eventos bajo un semáforo de concurrencia, así como la emisión y verificación de tokens JWT con marca temporal fraccionaria (`iat`) y clave de firma fija desde la configuración.

## ADDED Requirements

### Requirement: Hash y verificación bcrypt fuera del bucle de eventos y bajo semáforo
Toda operación de hash o verificación con `bcrypt` SHALL ejecutarse mediante `asyncio.to_thread` dentro del semáforo `app.state.bcrypt_semaforo`, utilizando el factor de costo `settings.BCRYPT_COST`, y MUST completarse antes de abrir cualquier transacción de base de datos.

#### Scenario: Hash y verificación correctos con el costo configurado
- **WHEN** se genera el hash de una contraseña y luego se verifica con la misma contraseña y con una distinta
- **THEN** el hash resultante lleva el costo configurado (`$2b$<costo>$...`), la verificación da `True` para la contraseña correcta y `False` para la incorrecta, habiendo corrido en `asyncio.to_thread` bajo el semáforo

#### Scenario: Límite de concurrencia respetado
- **WHEN** se lanzan en paralelo más operaciones `bcrypt` que `BCRYPT_MAX_CONCURRENT`
- **THEN** a lo sumo `BCRYPT_MAX_CONCURRENT` llamadas a `bcrypt` se ejecutan simultáneamente

### Requirement: Emisión y decodificación de JWT con `iat` fraccionario
El sistema SHALL emitir tokens JWT firmados con `settings.JWT_SECRET_KEY` y `settings.JWT_ALGORITHM` que incluyan las reclamaciones `sub` (identificador del usuario como string), `iat` con fracciones de segundo (`float`, sin truncar a segundos enteros), `exp` (`iat + settings.ACCESS_TOKEN_EXPIRE_SECONDS`) y `roles` (lista de roles vigentes al momento de emisión).

#### Scenario: Emisión y lectura de claims con precisión de microsegundos
- **WHEN** se emite un JWT para un usuario con roles vigentes y se decodifica con la clave configurada
- **THEN** el payload contiene `sub`, `roles`, `exp` e `iat` como número de punto flotante que preserva la fracción de segundo del instante de emisión

#### Scenario: Rechazo de token vencido o firmado con otra clave
- **WHEN** se intenta decodificar un JWT firmado con otra clave o cuyo `exp` ya transcurrió
- **THEN** la decodificación falla de forma controlada sin filtrar secretos ni trazas internas
