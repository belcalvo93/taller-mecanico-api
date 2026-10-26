# Spec Delta

## Purpose

Expone dos chequeos de salud públicos: uno que confirma que el proceso responde sin tocar la base (`live`) y otro que confirma que la base contesta (`ready`), sin filtrar nunca detalles internos de la base al cliente.

## ADDED Requirements

### Requirement: Liveness sin tocar la base
`GET /health/live` SHALL responder 200 con el cuerpo `{"estado": "ok"}` sin abrir conexiones ni sesiones con la base. El endpoint MUST NOT exigir autenticación.

#### Scenario: Proceso vivo
- **WHEN** se pide `GET /health/live`
- **THEN** responde 200 con `{"estado": "ok"}`

#### Scenario: Vivo aunque la base esté caída
- **WHEN** la base es inaccesible y se pide `GET /health/live`
- **THEN** responde 200 sin intentar conectarse a la base

### Requirement: Readiness con SELECT 1
`GET /health/ready` SHALL ejecutar `SELECT 1` contra la base y responder 200 con `{"estado": "ok", "base": "ok"}` si la base contesta. El endpoint MUST NOT exigir autenticación.

#### Scenario: Base disponible
- **WHEN** la base acepta conexiones y se pide `GET /health/ready`
- **THEN** responde 200 con `{"estado": "ok", "base": "ok"}`

### Requirement: Readiness responde 503 sin filtrar detalles de la base
Si la base no contesta (conexión rechazada, credenciales inválidas, base inexistente o demora mayor a un límite corto), `GET /health/ready` MUST responder 503 con el cuerpo `{"estado": "no disponible", "base": "no disponible"}`. La respuesta MUST NOT incluir texto del driver o de la base, trazas, la URL, el host, el usuario ni la contraseña (RN-18), y MUST NOT ser un 500.

#### Scenario: Base caída
- **WHEN** la base no acepta conexiones y se pide `GET /health/ready`
- **THEN** responde 503 con `{"estado": "no disponible", "base": "no disponible"}`

#### Scenario: Credenciales inválidas
- **WHEN** la contraseña configurada es incorrecta y se pide `GET /health/ready`
- **THEN** responde 503 con el mismo cuerpo fijo, sin el mensaje de error de autenticación de la base

#### Scenario: Sin texto interno en la respuesta
- **WHEN** `GET /health/ready` responde 503
- **THEN** el cuerpo no contiene palabras del error interno (por ejemplo el nombre del driver, `Traceback`, el host o la contraseña)

#### Scenario: Base que no responde a tiempo
- **WHEN** la conexión a la base no se resuelve dentro del límite de espera del chequeo
- **THEN** responde 503 con el mismo cuerpo fijo, sin quedar colgado
