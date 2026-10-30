# Spec: Listado paginado de eventos de seguridad

## ADDED Requirements

### Requirement: Consulta paginada de eventos de seguridad (US-012, DD-15)
El endpoint `GET /eventos` MUST requerir el rol `ADMIN` vigente y devolver una página de eventos de seguridad con el envoltorio estándar `Pagina[EventoSeguridadResponse]` (`items`, `total`, `page`, `size`, `pages`), aceptando los parámetros de consulta `page` (`>= 1`) y `size` (`1..100`).

#### Scenario: Listado paginado incluye el evento inicial del seed y eventos posteriores
- **WHEN** un `ADMIN` consulta `GET /eventos?page=1&size=20` sobre la base sembrada
- **THEN** el sistema responde `200 OK` con `items`, `total`, `page`, `size` y `pages`, incluyendo la fila inicial `{actor: "SISTEMA", accion: "Carga de los datos iniciales"}` y los eventos generados por las operaciones de seguridad

#### Scenario: Página inexistente o parámetros fuera de rango responden 422
- **WHEN** un `ADMIN` consulta `GET /eventos` con `page=999` (mayor que `pages`), `page=0` o `size=500`
- **THEN** el sistema responde `422 Unprocessable Entity` con mensaje propio

#### Scenario: Usuario sin rol ADMIN recibe 403 en GET /eventos
- **WHEN** un usuario autenticado sin rol `ADMIN` vigente consulta `GET /eventos`
- **THEN** el sistema responde `403 Forbidden`
