# Design

## Context

Motivación y alcance: ver `proposal.md`. Requisitos: ver `specs/dependencias-acceso`, `specs/seguridad-credenciales`, `specs/registro-cliente` y `specs/sesion-y-credenciales`.

Estado actual en `main`:
- **CH-01 (`infra-base`) y CH-02 (`esquema-y-migraciones`) ya están mergeados en `main`**:
  - `main.py` expone en `app.state`: `settings`, `engine`, `session_factory`, `bcrypt_semaforo` (`asyncio.Semaphore(settings.BCRYPT_MAX_CONCURRENT)`) y `hash_ficticio` (`bytes`, calculado una sola vez en el lifespan con `settings.BCRYPT_COST`).
  - `main.py` define `rutas_abiertas` y `rutas_protegidas` con el marcador `# CH-04: rutas_abiertas.include_router(auth_router)`.
  - `app/modules/usuarios/models.py` define `Usuario`, `AsignacionRol`, `IntentoAcceso` y `EventoSeguridad` con `lazy="raise"` en todas las relaciones y nombres de restricciones fijos (`uq_usuario_email`, `uq_asignacion_rol_abierta`, `ck_asignacion_rol_rol_valido`, `ix_intento_acceso_email_ip_cuando`).
  - `app/modules/clientes/models.py` define `Cliente` con `uq_cliente_usuario_id` y `uq_cliente_documento`.
  - `seed.py` ya siembra los 7 usuarios de prueba (`admin@`, `admin2@`, `recepcion@`, `mecanico@`, `mecanico2@`, `cliente@`, `nuevo@example.com`) y los 2 clientes (`Laura Cliente` doc `30111222` con usuario 6, `Jorge Gómez` doc `25333444` sin usuario).
- **CH-03 (`nucleo-repositorios-uow`, Elías)** sigue abierto:
  - La **Tarea 1 (T1)** de CH-04 (`app/core/dependencies.py` provisorio) **no depende de CH-03**: puede usar `AsyncSession` directamente o funciones livianas sobre `session` y mergearse ya mismo en un PR chico para desbloquear a Joaquín (CH-06) y Bruno (CH-07).
  - El resto de CH-04 (`repository.py`, `unit_of_work.py`, `service.py`, `router.py`) usa `BaseRepository[T]` y `UnitOfWork` de `app/core/repository.py` y `app/core/unit_of_work.py` una vez mergeado CH-03.

## Goals / Non-Goals

**Goals:**
- Entregar primero el gate **T1 (`app/core/dependencies.py`)** con firmas inmutables para que CH-06, CH-07 y luego CH-05/CH-08 no tengan que tocar sus imports ni sus decoradores.
- Garantizar que ninguna llamada a `bcrypt` corra en el event loop ni dentro de una transacción abierta, y que toda contraseña que va a `bcrypt` se valide a `<= 72` bytes en el contrato Pydantic (`422`).
- Garantizar la atomicidad de `POST /auth/registro` (tres tablas + evento de seguridad en un solo UoW) y la independencia transaccional de `intento_acceso` en `POST /auth/login`.
- Asegurar que el cambio de contraseña invalide los tokens emitidos antes del cambio aunque sean del mismo segundo (`iat` fraccionario comparado sin truncar con `password_cambiada_en`).

**Non-Goals:**
- Endpoints `/usuarios`, `/usuarios/{id}/roles` y `/eventos` (pertenecen a CH-05 `autorizacion-y-roles`).
- Montar el control de `debe_cambiar_password` (`403`) en `rutas_protegidas` de `main.py` (pertenece a CH-05).

## Decisions

### D1 — Estrategia en dos pasos para `app/core/dependencies.py` (Gate T1 → CH-04 → CH-05)
Las firmas públicas en `app/core/dependencies.py` quedan fijas desde el primer commit (T1):

```python
async def get_usuario_actual(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> Usuario: ...

def requiere_rol(*roles: str) -> Callable[..., Awaitable[Usuario]]:
    async def _verificar_rol(
        usuario: Usuario = Depends(get_usuario_actual),
        session: AsyncSession = Depends(get_session),
    ) -> Usuario: ...
    return _verificar_rol
```

- **Por qué estas firmas**:
  - `get_usuario_actual` recibe `Request` (para leer `request.cookies.get("access_token")` y `request.app.state.settings`) y `session = Depends(get_session)` (para buscar el `Usuario` en la base), y devuelve `Usuario`.
  - `requiere_rol(*roles: str)` recibe uno o más nombres de rol (`"ADMIN"`, `"RECEPCION"`, `"MECANICO"`, `"CLIENTE"`) y devuelve una dependencia inyectable con `Depends(requiere_rol("RECEPCION", "ADMIN"))` que retorna el `Usuario` autenticado y autorizado.
- **Qué hace en T1 (PR chico inmediato a `main`)**:
  - Lee únicamente `request.cookies.get("access_token")` (nunca `Authorization`); si falta o el token es inválido/vencido o el usuario no existe/está inactivo o `iat < password_cambiada_en`, lanza `HTTPException(status_code=401, detail="No autenticado")`.
  - `requiere_rol(*roles)` consulta en la base las filas vigentes de `AsignacionRol` del usuario (`revocada_en IS NULL` y `(vence_en IS NULL OR vence_en > ahora_utc())`); si no tiene ninguno de los `roles` pedidos, lanza `HTTPException(status_code=403, detail="Sin permiso suficiente")`.
  - De este modo T1 ya cumple el contrato funcional para que CH-06 y CH-07 puedan cablear sus rutas y correr sus tests, y CH-05 lo refina/integra con los repositorios definitivos y el control de `debe_cambiar_password` sin cambiar las firmas.

### D2 — `app/core/security.py`: bcrypt con `to_thread` + semáforo y JWT con `iat` fraccionario
- **Funciones de contraseña**:
  - `async def hashear_password(password: str, settings: Settings, semaforo: asyncio.Semaphore) -> str`:
    codifica `password.encode("utf-8")`, adquiere `async with semaforo:`, y ejecuta `await asyncio.to_thread(bcrypt.hashpw, password_bytes, bcrypt.gensalt(rounds=settings.BCRYPT_COST))` devolviendo el `str` UTF-8. Se invoca `bcrypt.hashpw` a través del módulo `bcrypt` (igual que en `main.py`) para permitir espiar/contar llamadas en los tests.
  - `async def verificar_password(password: str, password_hash: str | bytes, semaforo: asyncio.Semaphore) -> bool`:
    convierte `password_hash` a `bytes` si es `str`, adquiere `async with semaforo:`, y ejecuta `await asyncio.to_thread(bcrypt.checkpw, password.encode("utf-8"), hash_bytes)`.
- **Funciones de JWT (`PyJWT`)**:
  - `crear_access_token(usuario_id: int, roles: list[str], settings: Settings, ahora: datetime | None = None) -> str`:
    toma `instante = ahora or ahora_utc()`, calcula `iat = instante.timestamp()` (`float` con microsegundos, **sin truncar a `int`**) y `exp = iat + float(settings.ACCESS_TOKEN_EXPIRE_SECONDS)`. Firma el payload `{"sub": str(usuario_id), "iat": iat, "exp": exp, "roles": list(roles)}` con `jwt.encode(..., settings.JWT_SECRET_KEY.get_secret_value(), algorithm=settings.JWT_ALGORITHM)`.
  - `decodificar_access_token(token: str, settings: Settings) -> dict[str, Any]`:
    llama a `jwt.decode(token, settings.JWT_SECRET_KEY.get_secret_value(), algorithms=[settings.JWT_ALGORITHM], options={"require": ["sub", "iat", "exp"]})`. Cualquier ` jwt.PyJWTError` se traduce a una excepción de dominio/autenticación (`TokenInvalidoError`) que `get_usuario_actual` convierte en `401`.
- **Comparación sin truncar (RN-07)**:
  - Cuando `usuario.password_cambiada_en` no es `None`, se compara `float(payload["iat"]) < usuario.password_cambiada_en.timestamp()`.
  - En `POST /auth/cambiar-password`, al actualizar `usuario.password_cambiada_en = instante_cambio`, el nuevo token se emite con `ahora = max(ahora_utc(), instante_cambio)` (donde `iat >= instante_cambio.timestamp()`), mientras que cualquier token emitido antes del cambio tiene `iat < instante_cambio.timestamp()` y queda inválido inmediatamente aunque el login y el cambio ocurran en el mismo milisegundo.

### D3 — Validación de contraseñas en `schemas.py` (`<= 72 bytes` y `extra="forbid"`)
- `bcrypt` 5.0 lanza `ValueError` si recibe más de 72 bytes, y un carácter multibyte como `ñ` o un tilde ocupa 2 bytes en UTF-8.
- Todos los esquemas de entrada (`RegistroRequest`, `LoginRequest`, `CambiarPasswordRequest`) heredan de una clase base con `model_config = ConfigDict(extra="forbid")`.
- Se define un tipo anotado reutilizable `PasswordBcryptStr`:
  - Verifica que `1 <= len(valor.encode("utf-8")) <= 72`. Si supera 72 bytes (o está vacío), Pydantic devuelve `422 Unprocessable Entity` antes de entrar al handler (cumpliendo la regla 9 de `CLAUDE.md` y evitando cualquier `500`).
  - No exige complejidad arbitraria en `LoginRequest` ni en `password_actual` para que contraseñas cortas incorrectas lleguen al servicio y respondan `401` (C-04).

### D4 — Repositorios de `usuarios`, `ClienteRepository` (DD-13) y `UsuarioUnitOfWork`
- En `app/modules/usuarios/repository.py`:
  - `UsuarioRepository(BaseRepository[Usuario])`:
    - `get_by_email(email: str) -> Usuario | None`
    - `get_by_id_con_asignaciones(usuario_id: int) -> Usuario | None` (con `selectinload(Usuario.asignaciones)` declarado dentro del método).
  - `AsignacionRolRepository(BaseRepository[AsignacionRol])`:
    - `listar_roles_vigentes(usuario_id: int, ahora: datetime) -> list[str]`: devuelve los nombres de rol (`rol`) de `asignacion_rol` para `usuario_id` con `revocada_en IS NULL` y `(vence_en IS NULL OR vence_en > ahora)`, ordenados.
  - `IntentoAccesoRepository(BaseRepository[IntentoAcceso])`:
    - `contar_fallos_vigentes_y_primer_fallo(email: str, ip: str, desde: datetime) -> tuple[int, datetime | None]`: obtiene la fecha del último intento con `exito == True` para `(email, ip)`; toma como piso `max(desde, ultimo_exito)` y devuelve la cantidad de intentos fallidos (`exito == False`) posteriores a ese piso junto con el `cuando` del más antiguo de esos fallos (para calcular `Retry-After`).
  - `EventoSeguridadRepository(BaseRepository[EventoSeguridad])`:
    - `registrar(actor: str, accion: str) -> EventoSeguridad`: inserta con `flush()`.
- En `app/modules/clientes/repository.py` (DD-13):
  - Si CH-06 T1 ya está en `main`, se importa `ClienteRepository` tal cual. Si todavía no está en `main`, se crea con la firma estándar `class ClienteRepository(BaseRepository[Cliente]): pass` para que Joaquín la extienda en CH-06.
- En `app/modules/usuarios/unit_of_work.py`:
  - `UsuarioUnitOfWork(UnitOfWork)` instancia con la misma `session`: `self.usuarios = UsuarioRepository(session, Usuario)`, `self.asignaciones_rol = AsignacionRolRepository(session, AsignacionRol)`, `self.intentos_acceso = IntentoAccesoRepository(session, IntentoAcceso)`, `self.eventos_seguridad = EventoSeguridadRepository(session, EventoSeguridad)` y `self.clientes = ClienteRepository(session, Cliente)`.
  - Dependencia `get_usuario_uow(session: AsyncSession = Depends(get_session)) -> UsuarioUnitOfWork` para inyectar en el router.

### D5 — Registro atómico (`POST /auth/registro`) y traducción de `IntegrityError` a 409
1. El servicio calcula `password_hash = await hashear_password(...)` **antes** de `async with uow:`.
2. Dentro de `async with uow:`:
   - `usuario = await uow.usuarios.add(Usuario(email=..., nombre=..., password_hash=password_hash, activo=True, debe_cambiar_password=False))` (hace `flush()` y obtiene `usuario.id`).
   - `await uow.asignaciones_rol.add(AsignacionRol(usuario_id=usuario.id, rol="CLIENTE"))`.
   - `cliente = await uow.clientes.add(Cliente(usuario_id=usuario.id, nombre=..., documento=..., telefono=...))`.
   - `await uow.eventos_seguridad.registrar(actor=usuario.email, accion="ALTA_USUARIO_CLIENTE")`.
3. Si `uow.usuarios.add` o `uow.clientes.add` lanza `sqlalchemy.exc.IntegrityError`:
   - El `async with uow` hace rollback de toda la transacción (no queda ni `usuario`, ni `asignacion_rol`, ni `cliente`, ni `evento_seguridad`).
   - Se inspecciona el nombre de la restricción (`uq_usuario_email` o `uq_cliente_documento` en `exc.orig`) y se lanza un error de negocio que el router traduce a `409 Conflict` con mensaje propio (`"El correo electrónico ya está registrado"` o `"El documento ya pertenece a un cliente registrado"`), sin filtrar nunca texto de SQLAlchemy/asyncpg (RN-01, RN-02, RN-18).

### D6 — Orden estricto de `POST /auth/login` (RN-08, RN-09, SU-02) y sesión propia de `intento_acceso`
1. **Paso 1 — Límite de intentos (sin hash)**:
   - Se calcula `ventana_inicio = ahora - timedelta(seconds=60)`.
   - Se consulta `contar_fallos_vigentes_y_primer_fallo(email, ip, ventana_inicio)`.
   - Si `cantidad_fallos >= 5`: se calcula `retry_after = max(1, math.ceil((primer_fallo + timedelta(seconds=60) - ahora).total_seconds()))` y se responde `429 Too Many Requests` con cabecera `Retry-After: <retry_after>` y mensaje propio, **sin llamar a `bcrypt`** y **sin agregar una sexta fila en `intento_acceso`** (SU-02).
2. **Paso 2 — Búsqueda de usuario y verificación en tiempo constante**:
   - Se busca `usuario = await uow.usuarios.get_by_email(datos.email)`.
   - Si `usuario` existe y `usuario.activo` es `True`: se verifica `es_valido = await verificar_password(datos.password, usuario.password_hash, semaforo)`.
   - Si `usuario` no existe o está inactivo: se ejecuta igualmente `await verificar_password(datos.password, hash_ficticio, semaforo)` y se fuerza `es_valido = False`.
3. **Paso 3 — Persistencia de `intento_acceso` en sesión y transacción propias (Ejercicio 7)**:
   - Se abre una sesión dedicada desde `session_factory` (`async with session_factory() as sesion_intento, sesion_intento.begin():`), separada de la sesión del request/UoW, para insertar `IntentoAcceso(email=datos.email, ip=ip_cliente, exito=es_valido, cuando=ahora)`.
   - El código lleva el comentario obligatorio declarando por qué tiene su propia sesión/transacción y cuál es su costo (deja filas confirmadas aunque la petición de login falle con `401`).
4. **Paso 4 — Respuesta**:
   - Si `not es_valido`: responde `401` con `{"detail": "Credenciales inválidas"}` (idéntico mensaje exista o no el correo, RN-09).
   - Si `es_valido`: consulta los roles vigentes del usuario en la base, emite el JWT con `crear_access_token`, configura `response.set_cookie(key="access_token", value=token, httponly=True, samesite="lax", max_age=settings.ACCESS_TOKEN_EXPIRE_SECONDS, secure=settings.COOKIE_SECURE, path="/")` y devuelve `200` con `{"mensaje": "Sesión iniciada", "debe_cambiar_password": usuario.debe_cambiar_password, "expira_en_segundos": settings.ACCESS_TOKEN_EXPIRE_SECONDS}`.

### D7 — `GET /auth/yo`, `POST /auth/logout` y `POST /auth/cambiar-password`
- `POST /auth/logout`: llama a `response.delete_cookie(key="access_token", httponly=True, samesite="lax", secure=settings.COOKIE_SECURE, path="/")` y devuelve `200 {"mensaje": "Sesión cerrada"}`.
- `GET /auth/yo`: usa `usuario: Usuario = Depends(get_usuario_actual)`, decodifica los roles del token (`roles_token`) y consulta en la base los roles vigentes (`roles_vigentes`), devolviendo `UsuarioYoResponse` (sin `password_hash`).
- `POST /auth/cambiar-password`:
  1. Requiere `usuario: Usuario = Depends(get_usuario_actual)`.
  2. Antes de abrir el UoW, verifica `password_actual` con `verificar_password` (si no coincide → `401` con mensaje propio) y calcula `nuevo_hash = await hashear_password(datos.password_nueva, settings, semaforo)`.
  3. Dentro de `async with uow:`:
     - Registra `instante_cambio = ahora_utc()`. Si el token actual se emitió en el mismo microsegundo o reloj del sistema no avanzó respecto al `iat` del token actual, asegura que `instante_cambio` sea estrictamente mayor al `iat` del token anterior (`max(ahora_utc(), datetime.fromtimestamp(iat_anterior, tz=timezone.utc) + timedelta(microseconds=1))`).
     - Actualiza `usuario.password_hash = nuevo_hash`, `usuario.password_cambiada_en = instante_cambio`, `usuario.debe_cambiar_password = False` con `flush()`.
     - Registra en `evento_seguridad`: `actor=usuario.email`, `accion="CAMBIO_PASSWORD"`.
  4. Al salir del UoW (commit hecho), consulta los roles vigentes y emite un nuevo JWT cuyo `iat` es `>= instante_cambio.timestamp()`, colocándolo en `Set-Cookie: access_token`. Así la cookie anterior tiene `iat < password_cambiada_en.timestamp()` (da `401` de inmediato, sin `sleep`) y la nueva cookie tiene `iat >= password_cambiada_en.timestamp()` (pasa).

### D8 — Convención de códigos de `evento_seguridad` (DD-15)
Para que CH-04 y CH-05 compartan un único catálogo de acciones de seguridad (DD-15), se definen constantes en `app/modules/usuarios/schemas.py` (o `constants.py` importado por ambos):
- `ACCION_CARGA_INICIAL = "Carga de los datos iniciales"` (usada en `seed.py` con `actor="SISTEMA"`).
- `ACCION_ALTA_CLIENTE = "Alta de usuario cliente"` (usada en `POST /auth/registro`).
- `ACCION_CAMBIO_PASSWORD = "Cambio de contraseña"` (usada en `POST /auth/cambiar-password`).
- `ACCION_ALTA_PERSONAL = "Alta de usuario de personal"` (para CH-05).
- `ACCION_ASIGNACION_ROL = "Asignación de rol"` (para CH-05).
- `ACCION_REVOCACION_ROL = "Revocación de rol"` (para CH-05).

## Risks / Trade-offs

- **[Bloqueo de CH-06 y CH-07 si esperan todo CH-04]** → Mitigación: la **Tarea 1 (T1)** crea `app/core/dependencies.py` y `app/core/security.py` (parte JWT) sin depender de CH-03 y se sube en un PR chico a `main` antes del resto de CH-04.
- **[Dependencia cruzada con CH-03 (`BaseRepository`, `UnitOfWork`) y CH-06 T1 (`ClienteRepository`)]** → Mitigación: si al terminar T1 todavía no está mergeado CH-03 en `main`, coordinamos con Elías su PR; si `ClienteRepository` de Joaquín (CH-06 T1) no está aún en `main`, creamos `app/modules/clientes/repository.py` con la firma mínima acordada en DD-13 (`class ClienteRepository(BaseRepository[Cliente]): pass`).
- **[Reloj de Windows con resolución menor al microsegundo entre login y cambio de contraseña]** → Mitigación: en `cambiar_password`, si `ahora_utc().timestamp() <= iat_token_actual`, se garantiza `instante_cambio = datetime.fromtimestamp(iat_token_actual, tz=timezone.utc) + timedelta(microseconds=1)` y el nuevo token se emite con `instante >= instante_cambio`. Así la invalidación de la cookie anterior dentro del mismo segundo nunca depende de un `sleep`.
