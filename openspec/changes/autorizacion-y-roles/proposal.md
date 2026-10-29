# Proposal: Autorización, gestión de roles y eventos de seguridad (CH-05)

## Why

El change `CH-04` (`autenticacion`) dejó operativas la autenticación con cookie `HttpOnly`, la validación de `iat < password_cambiada_en` sin truncar y la consulta de roles vigentes en `app/core/dependencies.py`. Falta completar la Épica 5 (`US-011`, `US-012`, `US-013`):
1. Bloquear en **todo el grupo de rutas protegidas** (`rutas_protegidas` en `main.py`) a los usuarios con cambio de contraseña pendiente (`debe_cambiar_password = True` → `403 Forbidden`), permitiendo únicamente las rutas abiertas (`/health/*` y `/auth/*`) para que puedan consultar su identidad, cambiar su contraseña o cerrar sesión (`RN-06`, `C-09`).
2. Permitir al `ADMIN` dar de alta personal con contraseña provisoria (`POST /usuarios`, `debe_cambiar_password=True`), consultar y asignar roles con o sin vencimiento (`GET /usuarios/{id}/roles`, `POST /usuarios/{id}/roles`) y revocar roles conservando el historial (`DELETE /usuarios/{id}/roles/{rol}` con `revocada_en`), garantizando la autoprotección del administrador (`RN-05`, `C-07`, `C-08`).
3. Exponer el listado paginado de auditoría de eventos de seguridad (`GET /eventos`) para el `ADMIN` (`US-012`, `DD-15`).

## What Changes

- **`app/core/dependencies.py`**:
  - Mantener intactas las firmas y el contrato de `get_usuario_actual` y `requiere_rol(*roles)` (usadas por `CH-06`, `CH-07` y `CH-08`).
  - Incorporar la dependencia `verificar_cambio_password_obligatorio(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario`, que lanza `HTTPException(403)` cuando `usuario.debe_cambiar_password` es `True` (`RN-06`).
- **`main.py`**:
  - Declarar `rutas_protegidas = APIRouter(dependencies=[Depends(verificar_cambio_password_obligatorio)])` **una sola vez** sobre el grupo protegido antes de incluir los routers de los módulos.
  - Montar `usuarios_router` en `rutas_protegidas`.
- **`app/modules/usuarios/schemas.py`**:
  - Contratos de entrada estrictos (`extra="forbid"`, validación de texto sin NUL, contraseña de 1..72 bytes UTF-8):
    - `AltaPersonalRequest`: `email`, `nombre`, `password` (provisoria), `rol` (`ADMIN`, `RECEPCION`, `MECANICO`, `CLIENTE`).
    - `AsignarRolRequest`: `rol` (`ADMIN`, `RECEPCION`, `MECANICO`, `CLIENTE`), `vence_en: datetime | None = None` (si se informa, debe tener zona horaria explícita y ser futuro; de lo contrario `422`, nunca `409`).
  - Contratos de salida:
    - `UsuarioPersonalResponse`: `id`, `email`, `nombre`, `activo`, `debe_cambiar_password`, `rol`.
    - `AsignacionRolResponse`: `id`, `usuario_id`, `rol`, `desde`, `vence_en`, `revocada_en`, `otorgada_por`.
    - `EventoSeguridadResponse`: `id`, `cuando`, `actor`, `accion`.
- **`app/modules/usuarios/repository.py`**:
  - `AsignacionRolRepository`:
    - `listar_asignaciones_usuario(usuario_id)`: devuelve las asignaciones del usuario ordenadas por `id`.
    - `obtener_asignacion_abierta(usuario_id, rol)`: busca la fila con `revocada_en IS NULL` para `(usuario_id, rol)`.
    - `contar_admins_vigentes(ahora)`: cuenta cuántos usuarios activos distintos tienen el rol `ADMIN` vigente (`revocada_en IS NULL` y `(vence_en IS NULL OR vence_en > ahora)`).
  - `EventoSeguridadRepository`:
    - `listar_paginado(pagina: ParametrosPagina) -> Pagina[EventoSeguridad]`: usa `self._paginar` heredado de `BaseRepository` (`CH-03`).
- **`app/modules/usuarios/service.py` y `app/modules/usuarios/router.py`**:
  - Separar en `app/modules/usuarios/router.py` dos routers: `router` (`/auth`, grupo abierto) y `usuarios_router` (sin prefijo propio, montado en `rutas_protegidas`, con `/usuarios`, `/usuarios/{id}/roles`, `/usuarios/{id}/roles/{rol}` y `/eventos`).
  - `POST /usuarios` (`ADMIN` → `201`, `409`, `422`): hashea la contraseña provisoria fuera de la transacción (regla 9) y en un único `UsuarioUnitOfWork` inserta `Usuario(debe_cambiar_password=True)`, `AsignacionRol(otorgada_por=admin.id)` y `EventoSeguridad(actor=admin.email, accion=ACCION_ALTA_PERSONAL)`.
  - `GET /usuarios/{id}/roles` (`ADMIN` → `200`, `404`): verifica existencia del usuario (`404` si no existe) y lista sus asignaciones de rol.
  - `POST /usuarios/{id}/roles` (`ADMIN` → `201`, `404`, `409`, `422`): valida `vence_en` con zona horaria y en el futuro (`422` si es pasado o naive); verifica existencia del usuario (`404`); si existe una asignación abierta ya vencida (`revocada_en IS NULL` y `vence_en <= ahora`), la cierra (`revocada_en = ahora`) antes de insertar la nueva para respetar el índice único parcial `uq_asignacion_rol_abierta`; si ya tiene ese rol vigente responde `409`; registra `ACCION_ASIGNACION_ROL`.
  - `DELETE /usuarios/{id}/roles/{rol}` (`ADMIN` → `200`, `404`, `409`): valida que el rol sea válido (`422` si no está en el catálogo de roles); aplica autoprotección (`RN-05`: un admin no puede revocar su propio `ADMIN` → `409`, ni dejar al sistema sin administradores vigentes → `409`); si el usuario no existe o el rol no está vigente para ese usuario → `404`; fija `revocada_en = ahora_utc()` sin borrar la fila (`RN-03`) y registra `ACCION_REVOCACION_ROL`.
  - `GET /eventos` (`ADMIN` → `200`, `422`): listado paginado con `Depends(parametros_pagina)` y `Pagina[EventoSeguridadResponse]`.
- **`test/`**:
  - `test/C-07_revocacion_rol_y_vencimiento.http`
  - `test/C-08_autoproteccion_admin.http`
  - `test/C-09_cambio_obligatorio_password.http`

## Impact

- **`tests/test_grupos_de_rutas.py`**: actualiza el test `test_el_grupo_protegido_no_tiene_dependencias` (que tenía el comentario `# CH-05 le agrega, una sola vez, el control del cambio obligatorio.`) para verificar que `rutas_protegidas` tiene exactamente 1 dependencia (`verificar_cambio_password_obligatorio`).
- **Módulos de la ola 2 (`CH-06`, `CH-07`, `CH-08`)**: no requieren cambios porque las firmas de `get_usuario_actual` y `requiere_rol(*roles)` se mantienen idénticas y el control de `debe_cambiar_password` se hereda automáticamente desde `rutas_protegidas`.
