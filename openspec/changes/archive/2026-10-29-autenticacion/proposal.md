# Proposal

> CH-04 `autenticacion` · issue #4 · Responsable: Hernán · Ola 2 · Governance: CRITICO (autenticación, credenciales y sesiones).

## Why

El proyecto ya cuenta con la infraestructura base (CH-01) y los 13 modelos con sus migraciones y datos iniciales (CH-02), pero ningún usuario puede registrarse ni iniciar sesión, y los módulos de dominio de la ola 2 (`clientes-y-vehiculos` CH-06 y `repuestos-y-stock` CH-07) necesitan importar las dependencias `get_usuario_actual` y `requiere_rol(*roles)` con sus firmas definitivas desde `app/core/dependencies.py` (gate T1 de la ola 2) para cablear los permisos de sus rutas. Además, el Ejercicio 4 de la consigna (16 %) y parte del Ejercicio 7 (10 %, `intento_acceso` en sesión propia) evalúan directamente el flujo de registro atómico, login con cookie `HttpOnly`, límite de intentos, anti-enumeración y cambio de contraseña.

## What Changes

- **Tarea 1 (T1, gate "dependencias provisorias en `main`")**: crear `app/core/dependencies.py` con las firmas definitivas de `get_usuario_actual` y `requiere_rol(*roles)` para ser mergeadas primero en un PR chico a `main` que desbloquee a CH-06 y CH-07. En CH-04 `get_usuario_actual` lee la cookie `access_token` (nunca `Authorization`), decodifica el JWT, carga el usuario activo y verifica que `iat` no sea anterior a `password_cambiada_en` (sin truncar microsegundos); CH-05 completará `requiere_rol` contra la base en cada petición y montará el control del cambio obligatorio en el grupo protegido sin cambiar las firmas.
- **`app/core/security.py`**: funciones asincrónicas de hash y verificación de contraseñas con `bcrypt` ejecutadas fuera del event loop (`asyncio.to_thread`) bajo el semáforo `app.state.bcrypt_semaforo` y con costo `settings.BCRYPT_COST`, siempre **antes** de abrir la transacción; y funciones de emisión y decodificación de JWT (`PyJWT`) con `sub`, `iat` con fracciones de segundo (`float`), `exp` y `roles` firmados con `settings.JWT_SECRET_KEY`.
- **Repositorios y Unit of Work de `usuarios`** (`app/modules/usuarios/repository.py`, `app/modules/usuarios/unit_of_work.py`): `UsuarioRepository`, `AsignacionRolRepository`, `IntentoAccesoRepository` y `EventoSeguridadRepository`. El `UsuarioUnitOfWork` agrupa los repositorios del módulo e importa `ClienteRepository` desde `app/modules/clientes/repository.py` (DD-13; si aún no está en `main`, se crea con la firma acordada heredando de `BaseRepository[Cliente]`).
- **Contratos de entrada y salida** (`app/modules/usuarios/schemas.py`): esquemas Pydantic separados de los modelos de tabla, todos los de entrada con `extra="forbid"`, validación de máximo **72 bytes** en UTF-8 para todo campo de contraseña que llega a `bcrypt` (422), y ninguna respuesta con `password_hash`.
- **Servicio y endpoints de autenticación** (`app/modules/usuarios/service.py`, `app/modules/usuarios/router.py`, montado en `rutas_abiertas` de `main.py` bajo `/auth`):
  - `POST /auth/registro` → `201`: calcula el hash antes de abrir la transacción y en un único UoW crea `usuario`, `asignacion_rol` (`CLIENTE`), `cliente` y el registro en `evento_seguridad` (o quedan todas las filas o ninguna); traduce `IntegrityError` de correo o documento repetido a `409` con mensaje propio sin dejar filas sueltas ni apropiarse de un cliente existente del taller (RN-01, RN-02, RN-18).
  - `POST /auth/login` → `200` / `401` / `422` / `429`: primero verifica el límite de 5 intentos fallidos del par `(email, ip)` en los últimos 60 segundos desde el último éxito (`429` + cabecera `Retry-After` sin calcular hash y sin registrar un nuevo fallo, RN-08, SU-02); luego verifica la contraseña contra el hash real del usuario o contra `app.state.hash_ficticio` si el correo no existe (`401` con el mismo cuerpo y tiempo parecido, RN-09); registra cada intento evaluado (éxito o fallo) en `intento_acceso` usando una **sesión y transacción propias** confirmadas siempre (con comentario explícito en el código declarando su costo); emite el JWT únicamente en la cookie `access_token` (`HttpOnly`, `SameSite=Lax`, `Max-Age`, `Secure` según config) y devuelve `{"mensaje": "Sesión iniciada", "debe_cambiar_password": ..., "expira_en_segundos": ...}` sin el token en el cuerpo.
  - `POST /auth/logout` → `200`: borra la cookie `access_token`.
  - `GET /auth/yo` → `200` / `401`: devuelve los datos del usuario autenticado, sus roles vigentes leídos de la base y los roles informativos que trae el token.
  - `POST /auth/cambiar-password` → `200` / `401` / `422`: verifica la contraseña actual y calcula el hash de la nueva antes de abrir la transacción; en un UoW actualiza `password_hash`, `password_cambiada_en` (UTC con microsegundos), `debe_cambiar_password=False` y registra el evento en `evento_seguridad`; emite un token nuevo en la cookie posterior a `password_cambiada_en`, invalidando las sesiones anteriores aunque sean del mismo segundo (RN-07).
- **Casos `.http` y suite TDD (`pytest`)**: archivos `test/C-01_*.http` a `test/C-05_*.http` con respuestas esperadas en comentario, y tests automatizados en `tests/` contra `taller_test`.

Fuera de alcance: endpoints de administración de personal y roles (`POST /usuarios`, `/usuarios/{id}/roles`, `GET /eventos`) y el montaje del bloqueo `403` por cambio obligatorio de contraseña en `rutas_protegidas`, que corresponden a CH-05 (`autorizacion-y-roles`).

## Capabilities

### New Capabilities
- `dependencias-acceso`: resolución del usuario autenticado desde la cookie `access_token` (`get_usuario_actual`) y fábrica de dependencia de autorización por rol (`requiere_rol(*roles)`) en `app/core/dependencies.py`, con las firmas definitivas que consumen todos los módulos protegidos.
- `seguridad-credenciales`: cálculo y verificación de hashes `bcrypt` fuera del bucle de eventos con semáforo de concurrencia, y firma/decodificación de tokens JWT con `iat` de precisión fraccionaria en `app/core/security.py`.
- `registro-cliente`: auto-registro transaccional de clientes (`POST /auth/registro`) creando usuario, rol `CLIENTE`, ficha de cliente y evento de seguridad en un solo UoW con traducción de unicidad a `409` y validación de 72 bytes.
- `sesion-y-credenciales`: ciclo de sesión (`POST /auth/login`, `POST /auth/logout`, `GET /auth/yo`, `POST /auth/cambiar-password`), conteo de intentos y bloqueo `429` con `Retry-After`, persistencia de `intento_acceso` en sesión independiente, anti-enumeración con hash ficticio e invalidación de tokens previos al cambio de contraseña, junto con los casos `C-01` a `C-05`.

### Modified Capabilities
- (ninguna)

## Impact

- **Código nuevo**:
  - `app/core/dependencies.py` (entregado primero en PR chico para el gate T1, luego completado en CH-04 y CH-05).
  - `app/core/security.py`.
  - `app/modules/usuarios/schemas.py`, `app/modules/usuarios/repository.py`, `app/modules/usuarios/unit_of_work.py`, `app/modules/usuarios/service.py`, `app/modules/usuarios/router.py`.
  - `app/modules/clientes/repository.py` (sólo `ClienteRepository(BaseRepository[Cliente])` básico si CH-06 T1 aún no fue mergeado, acordado por DD-13).
  - `test/C-01_parametro_no_entero.http`, `test/C-02_registro_cliente.http`, `test/C-03_login_cookie.http`, `test/C-04_login_anti_enumeracion.http`, `test/C-05_login_limite_intentos.http`.
  - Tests en `tests/` (`tests/test_security.py`, `tests/test_dependencies_provisorias.py`, `tests/test_auth_registro.py`, `tests/test_auth_login.py`, `tests/test_auth_sesion_y_password.py`).
- **Código existente modificado**:
  - `main.py`: descomentado e import de `rutas_abiertas.include_router(auth_router)`.
  - `docs/bitacora.md`: entrada de Hernán para CH-04.
- **Dependencias con otros changes**:
  - **T1 de CH-04** (`app/core/dependencies.py` provisorio) no requiere esperar a CH-03 (`nucleo-repositorios-uow`) y habilita de inmediato a CH-06 (Joaquín) y CH-07 (Bruno).
  - El resto de CH-04 requiere CH-03 (`BaseRepository`, `UnitOfWork`) en `main`.
  - Habilita CH-05 (`autorizacion-y-roles`) y, junto con CH-05, a CH-08 (`ordenes`).
