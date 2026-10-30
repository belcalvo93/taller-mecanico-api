# Tasks: Autorización, gestión de roles y eventos de seguridad (CH-05)

## Grupo 1: Cambio obligatorio de contraseña en el grupo protegido (`US-011`, `US-013`, `RN-06`)

- [x] 1.1 **[ROJO]** Escribir tests en `tests/test_autorizacion_cambio_obligatorio.py` y actualizar `tests/test_grupos_de_rutas.py`:
  - Verificar que `main.rutas_protegidas` declara exactamente una dependencia (`verificar_cambio_password_obligatorio`) y `main.rutas_abiertas` ninguna.
  - Verificar que un usuario con `debe_cambiar_password=True` recibe `403` en cualquier ruta de `rutas_protegidas` (ej. `/mis-vehiculos`, `/clientes/1`), pero recibe `200` en `/auth/yo`, `/auth/cambiar-password` y `/auth/logout`.
  - Verificar que tras `POST /auth/cambiar-password`, la nueva cookie accede a `rutas_protegidas` (`200`) y la cookie anterior da `401` sin `sleep` (`C-09`).
- [x] 1.2 **[VERDE]** Implementar `verificar_cambio_password_obligatorio` en `app/core/dependencies.py` (sin tocar las firmas de `get_usuario_actual` ni `requiere_rol`) y montarla una sola vez en `rutas_protegidas` dentro de `main.py`.
- [x] 1.3 **[REFACTOR]** Verificar que toda la suite existente (`tests/test_clientes_rutas.py`, `tests/test_auth_*.py`, `tests/test_grupos_de_rutas.py`) pase en verde.
- [x] 1.4 **Checkpoint (Gobernanza CRITICO)**: Revisar con el usuario la dependencia en `app/core/dependencies.py` y su montaje en `main.py`.

## Grupo 2: Contratos y repositorios para personal, roles y eventos (`US-012`, `RN-03`, `RN-04`, `RN-05`, `DD-15`)

- [x] 2.1 **[ROJO]** Escribir tests unitarios de contratos en `tests/test_usuarios_admin_schemas.py` y de repositorios en `tests/test_usuarios_repos_uow.py`:
  - `AltaPersonalRequest`: rechaza `extra="forbid"`, contraseñas `> 72` bytes UTF-8, caracteres NUL y roles fuera de `('ADMIN', 'RECEPCION', 'MECANICO', 'CLIENTE')` (`422`).
  - `AsignarRolRequest`: rechaza `vence_en` sin zona horaria (naive) o en el pasado (`<= ahora_utc()`) con `ValidationError` (`422`), y acepta `None` o fecha futura con zona horaria.
  - `AsignacionRolRepository`: `listar_asignaciones_usuario`, `obtener_asignacion_abierta`, `contar_admins_vigentes`.
  - `EventoSeguridadRepository`: `listar_paginado` usando `_paginar` de `BaseRepository`.
- [x] 2.2 **[VERDE]** Implementar los contratos en `app/modules/usuarios/schemas.py` y los métodos de repositorio en `app/modules/usuarios/repository.py`.
- [x] 2.3 **[REFACTOR]** Limpiar validadores y verificar que todos los tests de contratos y repositorios pasen en verde.

## Grupo 3: Servicio y endpoints de personal, roles y eventos (`POST /usuarios`, `GET/POST/DELETE /usuarios/{id}/roles`, `GET /eventos`)

- [x] 3.1 **[ROJO]** Escribir tests de integración en `tests/test_usuarios_roles_y_eventos.py`:
  - `POST /usuarios`: alta de personal por `ADMIN` (`201` con `debe_cambiar_password=True`, rol inicial con `otorgada_por=admin.id` y evento `Alta de usuario de personal`); correo repetido (`409` sin filas sueltas); sin rol `ADMIN` (`403`); `bcrypt` fuera de la transacción.
  - `GET /usuarios/{id}/roles`: `200` con asignaciones del usuario; `404` si el usuario no existe; `422` si `id` no es entero o excede `INTEGER` (`C-01`).
  - `POST /usuarios/{id}/roles`: `201` con y sin `vence_en` futuro + evento `Asignación de rol`; `422` si `vence_en` es pasado o sin zona horaria (`C-07`); `409` si el rol ya está vigente; `201` si la asignación previa había vencido (cerrando la anterior con `revocada_en`); `404` si el usuario no existe.
  - `DELETE /usuarios/{id}/roles/{rol}`: `200` marcando `revocada_en` sin borrar la fila (`RN-03`) + evento `Revocación de rol`; en la petición siguiente la cookie del usuario recibe `403` y `/auth/yo` muestra la diferencia entre `roles_vigentes` y `roles_token` (`C-07`); `409` si el admin intenta revocar su propio `ADMIN` (`C-08`); `409` si intenta dejar al sistema sin administradores vigentes (`RN-05`); `404` si el usuario no existe o no tiene ese rol vigente.
  - `GET /eventos`: `200` paginado (`items`, `total`, `page`, `size`, `pages`) incluyendo el evento `SISTEMA` del seed; `422` con página inexistente o `size > 100`; `403` sin rol `ADMIN`.
- [x] 3.2 **[VERDE]** Implementar la lógica de negocio en `app/modules/usuarios/service.py`, las rutas en `usuarios_router` dentro de `app/modules/usuarios/router.py`, y montar `usuarios_router` en `rutas_protegidas` en `main.py`.
- [x] 3.3 **[REFACTOR]** Revisar traducción de errores de dominio y mensajes propios (`RN-18`), verificando que toda la suite pase en verde.
- [x] 3.4 **Checkpoint (Gobernanza CRITICO)**: Revisar con el usuario la implementación de autoprotección (`RN-05`), revocación/vencimiento (`RN-03`, `RN-04`) y eventos antes de cerrar los casos `.http`.

## Grupo 4: Casos de prueba `.http` (`C-07`, `C-08`, `C-09`), verificación integral y bitácora

- [x] 4.1 Crear `test/C-07_revocacion_rol_y_vencimiento.http` (sesiones simultáneas con `# @name` y `# @no-cookie-jar`, revocación en vivo -> `403`, `/auth/yo` mostrando `roles_vigentes` vs `roles_token`, fila revocada conservada en `GET /usuarios/3/roles`, y `vence_en` pasado o sin zona horaria -> `422`).
- [x] 4.2 Crear `test/C-08_autoproteccion_admin.http` (`admin@example.com` intenta revocar su propio `ADMIN` -> `409`; revoca el `ADMIN` de `admin2` -> `200`; `admin2` ya no puede usar rutas de `ADMIN` -> `403`).
- [x] 4.3 Crear `test/C-09_cambio_obligatorio_password.http` (`nuevo@example.com` con `debe_cambiar_password=True` recibe `403` en ruta protegida, `200` en `/auth/yo` y `/auth/cambiar-password`; tras el cambio sin espera, la cookie nueva accede a la ruta protegida y la cookie anterior da `401`).
- [x] 4.4 Ejecutar la suite completa de `pytest` y validar los casos `.http` contra la base sembrada, verificando también que `test/C-01_parametro_no_entero.http` ahora responda `422` en `/usuarios/abc/roles` y `/clientes/abc`.
- [x] 4.5 Registrar la entrada de `CH-05` (`autorizacion-y-roles`) en la sección de Hernán en `docs/bitacora.md`.
