# Spec: Cambio obligatorio de contraseña y control de acceso en grupo protegido

## ADDED Requirements

### Requirement: Bloqueo transversal por cambio obligatorio de contraseña (RN-06, US-011, US-013, C-09)
El sistema MUST bloquear con `403 Forbidden` cualquier petición dirigida al grupo de rutas protegidas (`rutas_protegidas` en `main.py`) cuando el usuario autenticado tenga `debe_cambiar_password = True`.
El control MUST declararse una única vez sobre `rutas_protegidas` en `main.py`, dejando fuera al grupo de rutas abiertas (`rutas_abiertas`: `/health/*` y `/auth/*`).

#### Scenario: Usuario con cambio obligatorio intenta acceder a una ruta protegida
- **WHEN** un usuario autenticado con `debe_cambiar_password = True` (como `nuevo@example.com` en el seed) envía una petición con su cookie `access_token` a cualquier ruta del grupo protegido (por ejemplo `GET /mis-vehiculos`, `GET /usuarios/1/roles` o `GET /clientes/1`)
- **THEN** el sistema responde `403 Forbidden` con un mensaje descriptivo propio sin ejecutar el handler de la ruta

#### Scenario: Usuario con cambio obligatorio accede a rutas de /auth
- **WHEN** un usuario autenticado con `debe_cambiar_password = True` envía una petición a `GET /auth/yo`, `POST /auth/cambiar-password` o `POST /auth/logout`
- **THEN** el sistema permite la operación y responde `200 OK`

#### Scenario: Desbloqueo inmediato tras cambiar la contraseña provisoria (C-09)
- **WHEN** el usuario con `debe_cambiar_password = True` ejecuta `POST /auth/cambiar-password` con su contraseña actual y una nueva válida sin esperar entre el login y el cambio
- **THEN** `debe_cambiar_password` pasa a `False`, la nueva cookie `access_token` permite acceder a las rutas protegidas (`200 OK`), y la cookie anterior es rechazada con `401 Unauthorized`

#### Scenario: Petición sin sesión a ruta protegida prioriza 401 sobre 403
- **WHEN** se envía una petición sin cookie `access_token` (o con token inválido/revocado) a cualquier ruta de `rutas_protegidas`
- **THEN** el sistema responde `401 Unauthorized`
