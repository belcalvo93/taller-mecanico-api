# Spec Delta

## Purpose

Implementa el inicio de sesión con cookie `HttpOnly` (`POST /auth/login`), el límite de intentos fallidos por correo e IP (`RN-08`), la respuesta indistinguible ante correos inexistentes (`RN-09`), el registro de cada intento en su propia sesión y transacción (`Ejercicio 7`), el cierre de sesión (`POST /auth/logout`), la consulta de identidad (`GET /auth/yo`), el cambio de contraseña con invalidación de tokens anteriores (`POST /auth/cambiar-password`, `RN-07`) y los casos de prueba `.http` `C-01` a `C-05`.

## ADDED Requirements

### Requirement: Límite de intentos fallidos antes de calcular hash (RN-08, SU-02)
En `POST /auth/login`, el sistema SHALL consultar primero en `intento_acceso` la cantidad de intentos fallidos del par `(email, ip)` ocurridos en los últimos 60 segundos desde el último intento exitoso de ese mismo par. Si existen 5 o más fallos vigentes, MUST responder inmediatamente `429` con la cabecera `Retry-After`, **sin ejecutar `bcrypt`** y **sin insertar una nueva fila de fallo** en `intento_acceso`. Un login exitoso posterior reinicia el conteo sin borrar las filas históricas.

#### Scenario: Sexto intento fallido dentro de 60 segundos recibe 429 sin ejecutar bcrypt
- **WHEN** un mismo par `(email, ip)` acumula 5 intentos de login fallidos en menos de 60 segundos y envía un sexto intento (incluso con la contraseña correcta)
- **THEN** el sexto intento responde `429` con cabecera `Retry-After` en pocos milisegundos sin llamar a `bcrypt`, y en `intento_acceso` siguen existiendo exactamente los 5 fallos (RN-08, SU-02, C-05)

#### Scenario: Un login exitoso reinicia la cuenta de fallos
- **WHEN** un par `(email, ip)` tiene menos de 5 fallos recientes, logra un login exitoso (`200`) y luego vuelve a fallar
- **THEN** los fallos anteriores al éxito siguen en la tabla `intento_acceso` pero ya no se suman a los nuevos fallos

### Requirement: Anti-enumeración con hash ficticio y mismo mensaje 401 (RN-09)
Si no se superó el límite de intentos, `POST /auth/login` SHALL verificar la contraseña con `bcrypt` contra el `password_hash` del usuario (si el correo existe y está activo) o contra `app.state.hash_ficticio` (si el correo no existe o el usuario está inactivo), devolviendo ante un fallo exactamente el mismo código `401` y el mismo cuerpo JSON en un tiempo comparable.

#### Scenario: Correo existente con contraseña errónea vs correo inexistente
- **WHEN** se intenta iniciar sesión con un correo registrado y contraseña incorrecta, y luego con un correo que no existe en la base
- **THEN** ambas peticiones ejecutan una verificación `bcrypt`, responden `401` con idéntico cuerpo JSON y ninguna emite cookie `access_token` (RN-09, C-04)

### Requirement: Registro de `intento_acceso` en sesión y transacción propias (Ejercicio 7)
Cada intento de login que llega a la etapa de verificación (exitoso o fallido) SHALL registrarse en la tabla `intento_acceso` (`email`, `ip`, `exito`, `cuando`) abriendo una **sesión y transacción propias e independientes** de la sesión de la petición y confirmándolas siempre (`commit`), con un comentario explícito en el código que declare esta excepción y su costo (deja filas persistidas aunque la petición falle con `401`).

#### Scenario: Los intentos fallidos sobreviven al rechazo 401 del login
- **WHEN** un usuario falla el login y recibe `401`
- **THEN** la fila con `exito=False` queda confirmada en `intento_acceso` en la base de datos (C-05)

### Requirement: Emisión del JWT sólo en cookie `HttpOnly` al iniciar sesión
Cuando las credenciales son válidas, `POST /auth/login` SHALL responder `200` con el cuerpo `{"mensaje": "Sesión iniciada", "debe_cambiar_password": <bool>, "expira_en_segundos": <int>}` (sin incluir el token en el cuerpo) y enviar el JWT únicamente en la cabecera `Set-Cookie: access_token=...` con los atributos `HttpOnly`, `SameSite=Lax`, `Max-Age=<ACCESS_TOKEN_EXPIRE_SECONDS>` y `Secure` según `settings.COOKIE_SECURE`.

#### Scenario: Login exitoso entrega cookie segura y cuerpo sin token
- **WHEN** un usuario activo envía credenciales válidas a `POST /auth/login`
- **THEN** responde `200` con `Set-Cookie` conteniendo `access_token`, `HttpOnly`, `SameSite=lax` y `Max-Age=1800`, y el cuerpo JSON contiene sólo `mensaje`, `debe_cambiar_password` y `expira_en_segundos` (C-03)

### Requirement: Cierre de sesión (`POST /auth/logout`) y consulta de identidad (`GET /auth/yo`)
`POST /auth/logout` SHALL responder `200` e instruir al cliente el borrado de la cookie `access_token`. `GET /auth/yo` SHALL requerir sesión válida (`401` si no la hay) y devolver los datos del usuario autenticado (sin `password_hash`), la lista de `roles_vigentes` consultados en la base de datos en ese instante y la lista de `roles_token` leída del payload del JWT.

#### Scenario: Logout borra la cookie
- **WHEN** se envía `POST /auth/logout`
- **THEN** responde `200` con `Set-Cookie` expirando/borrando `access_token` (`Max-Age=0`)

#### Scenario: `/auth/yo` expone roles vigentes de la base y roles del token
- **WHEN** un usuario con sesión válida consulta `GET /auth/yo`
- **THEN** responde `200` con su `id`, `email`, `nombre`, `activo`, `debe_cambiar_password`, `roles_vigentes` (de `asignacion_rol` vigente en la base) y `roles_token` (del JWT), sin incluir `password_hash`

### Requirement: Cambio de contraseña con nuevo token e invalidación inmediata de sesiones previas (RN-07)
`POST /auth/cambiar-password` SHALL requerir sesión válida (`401`), validar hasta 72 bytes (`422`), verificar la contraseña actual y calcular el nuevo hash antes de la transacción, y en un único `UnitOfWork` actualizar `password_hash`, `password_cambiada_en`, `debe_cambiar_password=False` y registrar el evento. Luego MUST emitir un JWT nuevo posterior a `password_cambiada_en`, invalidando tokens previos aunque sean del mismo segundo.

#### Scenario: Cambio de contraseña exitoso invalida la cookie anterior en el mismo segundo
- **WHEN** un usuario autenticado cambia su contraseña en `POST /auth/cambiar-password` inmediatamente después de iniciar sesión (sin espera entre el login y el cambio)
- **THEN** responde `200` con una nueva cookie `access_token`, se registra el evento en `evento_seguridad`, `debe_cambiar_password` pasa a `False`, la nueva cookie es aceptada en `GET /auth/yo` (`200`) y la cookie anterior recibe `401` (RN-07, C-09)

#### Scenario: Contraseña actual incorrecta en cambio de contraseña
- **WHEN** un usuario autenticado envía una `password_actual` que no coincide con su contraseña vigente
- **THEN** responde `401` (o `400`/`401` según contrato de credenciales inválidas: `401` según tabla de endpoints `200, 401, 422`), no modifica `password_hash` ni `password_cambiada_en` y no registra evento

### Requirement: Casos `.http` C-01 a C-05
El repositorio SHALL incluir en `test/` los archivos `.http` correspondientes a los casos `C-01`, `C-02`, `C-03`, `C-04` y `C-05`, cada uno con la respuesta esperada documentada en comentarios.

#### Scenario: Parámetro de ruta no entero con sesión iniciada (C-01)
- **WHEN** con una sesión iniciada se invoca una ruta con parámetro `{id}` entero enviando un valor no entero (por ejemplo `/usuarios/abc/roles` o `/clientes/abc`)
- **THEN** FastAPI responde `422` en la validación del contrato sin ejecutar el handler (C-01)
