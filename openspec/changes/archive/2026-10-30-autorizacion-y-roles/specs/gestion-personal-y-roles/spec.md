# Spec: Alta de personal y gestión de roles

## ADDED Requirements

### Requirement: Alta de personal con contraseña provisoria (US-012, RN-01, RN-06, RN-18)
El endpoint `POST /usuarios` MUST requerir el rol `ADMIN` vigente y dar de alta un usuario de personal con contraseña provisoria (`debe_cambiar_password = True`, `activo = True`), su asignación de rol inicial en `asignacion_rol` (con `otorgada_por = admin.id`) y un evento en `evento_seguridad` (`actor = admin.email`, `accion = "Alta de usuario de personal"`), todo dentro de un único `UsuarioUnitOfWork` tras calcular el hash `bcrypt` fuera de la transacción.

#### Scenario: Alta exitosa de personal por un administrador
- **WHEN** un usuario con rol `ADMIN` vigente envía `POST /usuarios` con `email`, `nombre`, `password` (1..72 bytes UTF-8) y `rol` válido (`ADMIN`, `RECEPCION`, `MECANICO` o `CLIENTE`)
- **THEN** el sistema responde `201 Created` con los datos del usuario creado (`debe_cambiar_password = true`, sin `password_hash`), habiendo persistido el usuario, su asignación de rol y el evento de seguridad en la misma transacción

#### Scenario: Alta de personal con correo duplicado
- **WHEN** un `ADMIN` envía `POST /usuarios` con un `email` que ya existe en `usuario`
- **THEN** la base rechaza la inserción por `uq_usuario_email`, el `UsuarioUnitOfWork` revierte toda la transacción sin dejar filas en `asignacion_rol` ni `evento_seguridad`, y el sistema responde `409 Conflict` con mensaje propio

#### Scenario: Alta de personal rechazada por contrato inválido o sin permiso
- **WHEN** se envía `POST /usuarios` con campos extra (`extra="forbid"`), rol inválido o contraseña de más de 72 bytes UTF-8, o desde un usuario sin rol `ADMIN`
- **THEN** el sistema responde `422 Unprocessable Entity` ante errores de contrato o `403 Forbidden` si el usuario no posee rol `ADMIN` vigente

### Requirement: Consulta de asignaciones de rol de un usuario (US-012, RN-03, C-07)
El endpoint `GET /usuarios/{id}/roles` MUST requerir el rol `ADMIN` vigente y devolver las asignaciones de rol del usuario `{id}`, o `404 Not Found` si el usuario no existe.

#### Scenario: Consulta de roles de un usuario existente
- **WHEN** un `ADMIN` consulta `GET /usuarios/{id}/roles` para un usuario existente
- **THEN** el sistema responde `200 OK` con la lista de asignaciones de rol del usuario (incluyendo `desde`, `vence_en`, `revocada_en`, `otorgada_por`)

#### Scenario: Consulta de roles de un usuario inexistente
- **WHEN** un `ADMIN` consulta `GET /usuarios/9999/roles`
- **THEN** el sistema responde `404 Not Found` con mensaje propio

### Requirement: Asignación de rol con vencimiento opcional (US-012, RN-03, RN-04, C-07)
El endpoint `POST /usuarios/{id}/roles` MUST requerir el rol `ADMIN` vigente y asignar un rol al usuario `{id}` con fecha `vence_en` opcional, registrando `otorgada_por = admin.id` y un evento en `evento_seguridad` (`accion = "Asignación de rol"`).

#### Scenario: Asignación exitosa de rol con o sin vencimiento futuro
- **WHEN** un `ADMIN` envía `POST /usuarios/{id}/roles` con un `rol` válido que el usuario no tiene vigente y `vence_en` nulo o con zona horaria en el futuro
- **THEN** el sistema crea la fila en `asignacion_rol`, registra el evento de seguridad y responde `201 Created`

#### Scenario: Vencimiento en el pasado o sin zona horaria responde 422 (C-07)
- **WHEN** un `ADMIN` envía `POST /usuarios/{id}/roles` con `vence_en` sin zona horaria (naive, ej. `"2030-01-01T00:00:00"`) o con una fecha en el pasado
- **THEN** el sistema rechaza la petición con `422 Unprocessable Entity` (nunca `409 Conflict`)

#### Scenario: Asignación de un rol que el usuario ya tiene vigente responde 409
- **WHEN** un `ADMIN` envía `POST /usuarios/{id}/roles` con un `rol` que ya está vigente (no revocado y no vencido) para ese usuario
- **THEN** el sistema responde `409 Conflict` con mensaje propio

#### Scenario: Reasignación de un rol previamente vencido cierra la fila anterior y crea una nueva
- **WHEN** un usuario tenía una asignación de `rol` con `revocada_en IS NULL` pero `vence_en <= ahora_utc()` y un `ADMIN` le vuelve a asignar ese mismo `rol`
- **THEN** el sistema marca `revocada_en` en la asignación vencida, inserta la nueva asignación vigente y responde `201 Created`

### Requirement: Revocación de rol e invariante de autoprotección de ADMIN (US-012, RN-03, RN-04, RN-05, C-07, C-08)
El endpoint `DELETE /usuarios/{id}/roles/{rol}` MUST requerir el rol `ADMIN` vigente, marcar `revocada_en = ahora_utc()` sobre la asignación vigente sin borrar la fila (`RN-03`), registrar el evento en `evento_seguridad` (`accion = "Revocación de rol"`) e impedir que un administrador revoque su propio rol `ADMIN` o deje al sistema sin administradores (`RN-05`).

#### Scenario: Revocación exitosa de rol quita el permiso en la petición siguiente (C-07)
- **WHEN** un `ADMIN` ejecuta `DELETE /usuarios/{id}/roles/RECEPCION` sobre un usuario con sesión abierta
- **THEN** el sistema actualiza `revocada_en`, registra el evento de seguridad y responde `200 OK`; en la petición siguiente con la misma cookie, el usuario recibe `403 Forbidden` en las rutas que requieren `RECEPCION` y `/auth/yo` muestra `roles_vigentes: []` frente a `roles_token: ["RECEPCION"]`

#### Scenario: Administrador intenta revocar su propio rol ADMIN (C-08)
- **WHEN** un administrador autenticado ejecuta `DELETE /usuarios/{su_propio_id}/roles/ADMIN`
- **THEN** el sistema rechaza la operación con `409 Conflict` sin modificar `asignacion_rol`

#### Scenario: Intento de revocar el último administrador vigente del sistema
- **WHEN** sólo queda un usuario activo con rol `ADMIN` vigente y se intenta revocar ese rol `ADMIN`
- **THEN** el sistema rechaza la operación con `409 Conflict`

#### Scenario: Revocación de un rol no vigente o de usuario inexistente responde 404
- **WHEN** un `ADMIN` ejecuta `DELETE /usuarios/{id}/roles/{rol}` para un usuario inexistente o un rol que el usuario no tiene vigente
- **THEN** el sistema responde `404 Not Found`
