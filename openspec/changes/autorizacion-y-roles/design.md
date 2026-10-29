# Design: Autorización, gestión de roles y eventos de seguridad (CH-05)

## Context

`main` cuenta con `CH-01`, `CH-02`, `CH-03`, `CH-04` y `CH-06` integrados. En `CH-04` se implementaron `get_usuario_actual` y `requiere_rol(*roles)` en `app/core/dependencies.py` consultando `asignacion_rol` en cada petición. `CH-05` completa la autorización transversal (bloqueo por cambio obligatorio de contraseña en el grupo protegido) y agrega los endpoints administrativos de personal, roles y eventos de seguridad (`US-011`, `US-012`, `US-013`).

## Goals / Non-Goals

**Goals:**
- Garantizar que toda ruta de `rutas_protegidas` rechace con `403` a cualquier usuario con `debe_cambiar_password=True`, habiendo configurado la dependencia **una sola vez** en `main.py` (`RN-06`, `C-09`).
- Mantener sin cambios las firmas de `get_usuario_actual` y `requiere_rol(*roles)` en `app/core/dependencies.py`.
- Implementar `POST /usuarios`, `GET /usuarios/{id}/roles`, `POST /usuarios/{id}/roles`, `DELETE /usuarios/{id}/roles/{rol}` y `GET /eventos` cumpliendo todas las reglas de negocio (`RN-01`, `RN-03`, `RN-04`, `RN-05`, `RN-18`).
- Documentar y verificar los casos `C-07`, `C-08` y `C-09` en archivos `.http`.

**Non-Goals:**
- Modificar el esquema de base de datos o las migraciones (`0001` y `0002` ya están cerradas en `CH-02`).
- Alterar los endpoints de `/auth` (`CH-04`) o de `/clientes` y `/vehiculos` (`CH-06`).

## Decisions

### D1 — Control único de `debe_cambiar_password` en `rutas_protegidas`
En `app/core/dependencies.py` se define:
```python
async def verificar_cambio_password_obligatorio(
    usuario: Usuario = Depends(get_usuario_actual),
) -> Usuario:
    if usuario.debe_cambiar_password:
        raise HTTPException(
            status_code=403,
            detail="Debe cambiar su contraseña provisoria antes de continuar",
        )
    return usuario
```
Y en `main.py`:
```python
rutas_protegidas = APIRouter(
    dependencies=[Depends(verificar_cambio_password_obligatorio)]
)
```
- **Por qué**:
  1. `verificar_cambio_password_obligatorio` depende de `get_usuario_actual`. Si la petición no tiene cookie o el token es inválido/expirado/revocado, `get_usuario_actual` responde `401` primero (`US-011`).
  2. Si el usuario está autenticado pero tiene `debe_cambiar_password=True`, responde `403` antes de evaluar permisos específicos o ejecutar el handler, incluso en rutas que sólo piden `get_usuario_actual` (como `/mis-vehiculos`, `/estados-orden` o `/mis-ordenes`).
  3. En los tests de otros módulos (como `tests/test_clientes_rutas.py`) que reemplazan `get_usuario_actual` en `app.dependency_overrides`, FastAPI inyecta el mismo override en `verificar_cambio_password_obligatorio`, manteniendo 100 % de compatibilidad con la suite existente.

### D2 — Dos routers en `app/modules/usuarios/router.py`
Para respetar la separación de grupos en `main.py` sin duplicar módulos:
- `router = APIRouter(prefix="/auth", tags=["auth"])` permanece para el grupo abierto (`rutas_abiertas`).
- `usuarios_router = APIRouter(tags=["usuarios y roles"])` agrupa `POST /usuarios`, `GET /usuarios/{id}/roles`, `POST /usuarios/{id}/roles`, `DELETE /usuarios/{id}/roles/{rol}` y `GET /eventos`, y se incluye en `rutas_protegidas` en `main.py`.

### D3 — Validación de `vence_en` en `POST /usuarios/{id}/roles` (422 vs 409)
La consigna (`C-07` y tabla de rutas) exige que una fecha `vence_en` sin zona horaria (naive) o en el pasado responda **`422 Unprocessable Entity` (nunca `409`)**.
- En `AsignarRolRequest`, el validador de Pydantic verifica que si `vence_en is not None`, entonces `vence_en.tzinfo is not None and vence_en.utcoffset() is not None` (si no, lanza `ValueError` → FastAPI responde `422`).
- Además, verifica que `vence_en > ahora_utc()` (si `vence_en <= ahora_utc()`, lanza `ValueError` → FastAPI responde `422`).

### D4 — Reasignación de un rol vencido vs rol vigente (`uq_asignacion_rol_abierta`)
En la base de datos (`CH-02`), el índice único parcial `uq_asignacion_rol_abierta` está definido sobre `(usuario_id, rol) WHERE revocada_en IS NULL`.
- Una asignación **vencida** (`vence_en <= ahora`) pero nunca revocada manualmente tiene `revocada_en IS NULL`.
- Si el administrador vuelve a asignar ese mismo rol al usuario después de que venció (`RN-03`, `RN-04`), la asignación anterior ya no está vigente, por lo que la operación es válida (`201 Created`).
- Para que el índice parcial `WHERE revocada_en IS NULL` permita insertar la nueva fila conservando la fila histórica (`RN-03`), el servicio inspecciona dentro del `UsuarioUnitOfWork` si existe una fila con `revocada_en IS NULL` para `(usuario_id, rol)`:
  - Si existe y está **vigente** (`vence_en is None or vence_en > ahora`), lanza `RolYaVigenciaError` → `409 Conflict`.
  - Si existe y ya **venció** (`vence_en <= ahora`), actualiza esa fila con `revocada_en = ahora` (`flush()`) para cerrar el ciclo histórico y luego inserta la nueva `AsignacionRol`.
  - Adicionalmente, envuelve el bloque `async with uow:` en `try/except IntegrityError` por si una carrera dispara `uq_asignacion_rol_abierta`, traduciéndola también a `409 Conflict`.

### D5 — Autoprotección del administrador y orden de validaciones en `DELETE /usuarios/{id}/roles/{rol}` (`RN-05`, `C-08`)
En `DELETE /usuarios/{id}/roles/{rol}`:
1. Los parámetros de ruta se validan en el contrato: `id: IdRuta` (`Path(ge=1, le=2_147_483_647)`) y `rol: RolNombre` (`Literal["ADMIN", "RECEPCION", "MECANICO", "CLIENTE"]`). Un id no entero o fuera de rango, o un nombre de rol inexistente, responde `422` sin ejecutar el servicio (`C-01`, `RN-18`).
2. Si `usuario_id == admin_actual.id` y `rol == "ADMIN"`, el servicio lanza `AutoproteccionAdminError` → **`409 Conflict`** ("Un administrador no puede revocar su propio rol ADMIN").
3. Si el usuario objetivo no existe o no tiene una asignación vigente de `rol`, lanza `RolNoEncontradoError` / `UsuarioNoEncontradoError` → **`404 Not Found`**.
4. Si `rol == "ADMIN"` y la cantidad de administradores activos con rol `ADMIN` vigente en el sistema es `<= 1`, lanza `AutoproteccionAdminError` → **`409 Conflict`** ("El sistema no puede quedar sin administradores").
5. Si pasa las validaciones, actualiza `asignacion.revocada_en = ahora_utc()`, registra `EventoSeguridad(actor=admin_actual.email, accion=ACCION_REVOCACION_ROL)` y confirma en el mismo `UsuarioUnitOfWork`.

### D6 — `GET /usuarios/{id}/roles`: asignaciones históricas y vigentes
`GET /usuarios/{id}/roles` verifica primero que el usuario `id` exista (`404` si no existe) y devuelve la lista de objetos `AsignacionRolResponse` del usuario (incluyendo `desde`, `vence_en`, `revocada_en`, `otorgada_por`), lo que permite verificar en `C-07` que tras `DELETE /usuarios/{id}/roles/{rol}` la fila revocada sigue en la base con `revocada_en` completado (`RN-03`).

### D7 — `GET /eventos` paginado con el núcleo de `CH-03`
`EventoSeguridadRepository.listar_paginado(pagina: ParametrosPagina)` utiliza `self._paginar(consulta, pagina)` de `BaseRepository` (`CH-03`), ordenando por `EventoSeguridad.id.asc()`. Cuando se pide una página mayor al total de páginas, `_paginar` lanza `PaginaInexistente`, que el manejador global en `main.py` traduce a `422` con mensaje propio (`{"detail": "La página X no existe: hay Y"}`).
