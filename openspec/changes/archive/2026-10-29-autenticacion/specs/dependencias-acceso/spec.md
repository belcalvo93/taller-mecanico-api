# Spec Delta

## Purpose

Provee las dependencias de acceso (`get_usuario_actual` y `requiere_rol(*roles)`) con sus firmas definitivas para que los módulos protegidos cableen sus rutas desde el inicio de la ola 2 (gate T1), leyendo el token exclusivamente desde la cookie `access_token` y validando la sesión activa.

## ADDED Requirements

### Requirement: Firma definitiva de las dependencias de acceso (Gate T1)
El sistema SHALL exponer `get_usuario_actual` y `requiere_rol(*roles)` en `app/core/dependencies.py` con las firmas definitivas que importan los routers de todos los módulos protegidos, permitiendo a CH-05 completar la consulta de roles vigentes en base de datos y el control de cambio obligatorio sin alterar las firmas.

#### Scenario: Importación e inyección en rutas protegidas
- **WHEN** un router declara `usuario: Usuario = Depends(get_usuario_actual)` o `Depends(requiere_rol("ADMIN", "RECEPCION"))`
- **THEN** FastAPI resuelve la dependencia y entrega la instancia de `Usuario` autenticada cuando la sesión y el rol son válidos

### Requirement: Lectura exclusiva de la cookie `access_token`
`get_usuario_actual` SHALL obtener el token únicamente desde `request.cookies["access_token"]` y MUST ignorar cualquier cabecera `Authorization` (incluida `Authorization: Bearer ...`).

#### Scenario: Petición sin cookie
- **WHEN** se invoca una ruta que requiere `get_usuario_actual` sin la cookie `access_token`
- **THEN** el sistema responde `401` con mensaje propio

#### Scenario: Petición con `Authorization: Bearer` y sin cookie
- **WHEN** se invoca una ruta autenticada enviando un JWT válido en la cabecera `Authorization: Bearer <token>` pero sin la cookie `access_token`
- **THEN** el sistema responde `401` (C-03)

### Requirement: Validación de vigencia e integridad de la sesión en `get_usuario_actual`
`get_usuario_actual` SHALL responder `401` si el token tiene firma inválida, está vencido, no contiene un `sub` entero válido, el usuario no existe o tiene `activo=False`, o si el instante `iat` del token es estrictamente anterior a `usuario.password_cambiada_en` (comparado sin truncar microsegundos, RN-07).

#### Scenario: Token adulterado o vencido
- **WHEN** la cookie `access_token` contiene un token con firma inválida o cuyo `exp` ya pasó
- **THEN** el sistema responde `401`

#### Scenario: Usuario inexistente o inactivo
- **WHEN** la cookie `access_token` referencia un `sub` que no existe en `usuario` o cuyo registro tiene `activo=False`
- **THEN** el sistema responde `401`

#### Scenario: Token emitido antes del último cambio de contraseña
- **WHEN** el usuario cambió su contraseña después de haberse emitido el token (incluso dentro del mismo segundo, `iat < password_cambiada_en`)
- **THEN** el sistema responde `401` al usar el token anterior y acepta el token emitido tras el cambio (RN-07, C-09)
