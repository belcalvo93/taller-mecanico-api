# Tasks

> TDD estricto en cada tarea: **ROJO** (escribir primero el test indicado, ejecutarlo y verificar que falla por la razón esperada) → **VERDE** (código mínimo, ejecutado) → **TRIANGULAR** (otro caso con datos distintos) → **REFACTOR** (tests verdes tras cada paso). Cada escenario de las specs tiene al menos un test.
> Tests en `tests/` (pytest) contra la base real `taller_test` (la fija `tests/conftest.py`); `test/` es sólo para los archivos `.http` (`C-01` a `C-05`). Comando: `.venv/Scripts/python -m pytest` desde la raíz.
> Governance CRITICO: en cada **[CHECKPOINT]** se frena y se le muestra a Hernán lo hecho; no se sigue sin su OK.
> **No se hacen commits automáticos sin permiso**: nunca agregar líneas `Co-Authored-By`, `Claude-Session` ni "Generated with Claude Code". Ninguna contraseña de la base ni clave de firma en archivos versionados, en el chat ni en logs.

## 0. Entorno y red de seguridad

- [x] 0.1 Verificar entorno local (`.venv`, `.env` no versionado con secretos locales, bases PostgreSQL `taller` y `taller_test`) y correr la suite actual de CH-01 y CH-02 (`.venv/Scripts/python -m pytest`) confirmando que todos los tests existentes pasan antes de empezar

## 1. Gate T1: `app/core/security.py` y `app/core/dependencies.py` (PR chico para desbloquear CH-06 y CH-07)

- [x] 1.1 ROJO `tests/test_security.py`: tests para `hashear_password` y `verificar_password` (costo desde `settings.BCRYPT_COST`, ejecución con `asyncio.to_thread` bajo `app.state.bcrypt_semaforo`, límite de concurrencia respetado) y para `crear_access_token` / `decodificar_access_token` (`sub`, `iat` como `float` con fracción de segundo sin truncar, `exp`, `roles`, rechazo de token vencido o con firma inválida). Ejecutar pytest y verificar que falla (no existe `app/core/security.py`)
- [x] 1.2 VERDE `app/core/security.py`: implementar `hashear_password`, `verificar_password`, `crear_access_token`, `decodificar_access_token` y `TokenInvalidoError` según design D2. Ejecutar `tests/test_security.py` y verificar que pasa en verde
- [x] 1.3 ROJO `tests/test_dependencies_provisorias.py`: tests para `get_usuario_actual` y `requiere_rol(*roles)` verificando las firmas definitivas, lectura exclusiva de `request.cookies["access_token"]`, rechazo `401` sin cookie o con `Authorization: Bearer` sin cookie, `401` con token inválido/vencido, `401` con usuario inexistente o `activo=False`, `401` con `iat < password_cambiada_en` (sin truncar microsegundos), `403` cuando el usuario no posee ninguno de los roles vigentes en `asignacion_rol`, y `200` devolviendo el `Usuario` cuando sí lo posee. Ejecutar pytest y verificar que falla (no existe `app/core/dependencies.py`)
- [x] 1.4 VERDE `app/core/dependencies.py`: implementar `get_usuario_actual` y `requiere_rol(*roles)` con las firmas definitivas de design D1. Ejecutar `tests/test_dependencies_provisorias.py` y toda la suite verificando que pasan en verde
- [x] 1.5 **[CHECKPOINT 1 — Gate T1 listo para PR chico a `main`]** Frenar y mostrarle a Hernán `app/core/security.py`, `app/core/dependencies.py` y los tests de 1.1–1.4 para que pueda abrir el PR chico a `main` que desbloquea a Joaquín (CH-06) y Bruno (CH-07). Esperar su OK antes de seguir con el grupo 2

## 2. Contratos (`schemas.py`), repositorios y `UsuarioUnitOfWork`

- [ ] 2.1 Verificar que CH-03 (`app/core/repository.py` y `app/core/unit_of_work.py`) esté disponible en la rama de trabajo; si `app/modules/clientes/repository.py` (`ClienteRepository`, T1 de CH-06, DD-13) aún no está en `main`, crearlo con la firma acordada (`class ClienteRepository(BaseRepository[Cliente]): pass`)
- [ ] 2.2 ROJO `tests/test_auth_schemas.py`: tests para `RegistroRequest`, `LoginRequest`, `CambiarPasswordRequest`, `RegistroResponse`, `LoginResponse` y `UsuarioYoResponse` verificando `extra="forbid"` (`422` ante campo `rol` u otros no declarados), límite de 72 **bytes** en UTF-8 (`422` con 73 caracteres ASCII y con 37 letras `ñ` = 74 bytes, `200` con 72 bytes exactos) y ausencia de `password_hash` en los esquemas de salida. Ejecutar pytest y verificar que falla
- [ ] 2.3 VERDE `app/modules/usuarios/schemas.py`: implementar los contratos de entrada/salida, el validador de 72 bytes en UTF-8 (design D3) y las constantes de acciones de `evento_seguridad` (design D8). Ejecutar `tests/test_auth_schemas.py` y verificar que pasa en verde
- [ ] 2.4 ROJO `tests/test_usuarios_repos_uow.py`: tests contra `taller_test` para `UsuarioRepository` (`get_by_email`, precarga en `get_by_id_con_asignaciones`), `AsignacionRolRepository` (`listar_roles_vigentes` excluyendo revocados y vencidos), `IntentoAccesoRepository` (`contar_fallos_vigentes_y_primer_fallo` respetando la ventana de 60 s y el reinicio tras un éxito), `EventoSeguridadRepository` y `UsuarioUnitOfWork` (commit al salir, rollback ante excepción, misma sesión en `usuarios`, `asignaciones_rol`, `clientes`, `eventos_seguridad`). Ejecutar pytest y verificar que falla
- [ ] 2.5 VERDE `app/modules/usuarios/repository.py` y `app/modules/usuarios/unit_of_work.py`: implementar los repositorios y el `UsuarioUnitOfWork` (design D4). Ejecutar `tests/test_usuarios_repos_uow.py` y verificar que pasa en verde

## 3. Auto-registro de cliente (`POST /auth/registro` — US-008, RN-01, RN-02, RN-18, C-02)

- [ ] 3.1 ROJO `tests/test_auth_registro.py`: tests de integración con `httpx.AsyncClient` para `POST /auth/registro`:
  - `201` crea `usuario`, `asignacion_rol` (`CLIENTE`), `cliente` vinculado y fila en `evento_seguridad` en una sola transacción; respuesta sin `password_hash`; el hash `bcrypt` se calcula antes de abrir la transacción;
  - `409` con mensaje propio (sin texto de PostgreSQL) si el `email` ya existe, sin dejar filas nuevas;
  - `409` con mensaje propio si el `documento` ya existe (incluido el documento de un cliente del taller sin usuario como Jorge Gómez `25333444`), verificando que no queda creado el `usuario` ni `asignacion_rol` (rollback atómico) y que la ficha existente sigue con `usuario_id=None`;
  - `422` si se envía un campo extra (`"rol": "ADMIN"`) o una contraseña de más de 72 bytes en UTF-8.
  Ejecutar pytest y verificar que falla
- [ ] 3.2 VERDE `app/modules/usuarios/service.py`, `app/modules/usuarios/router.py` y montaje en `main.py` (`rutas_abiertas.include_router(auth_router)`): implementar `registrar_cliente` y `POST /auth/registro` traduciendo `IntegrityError` (`uq_usuario_email`, `uq_cliente_documento`) a `409` con mensaje propio (design D5). Ejecutar `tests/test_auth_registro.py` y verificar que pasa en verde
- [ ] 3.3 **[CHECKPOINT 2 — Registro de cliente]** Frenar y mostrarle a Hernán el flujo de `POST /auth/registro` y los tests de atomicidad y `409`/`422`. Esperar su OK antes de seguir con el grupo 4

## 4. Login con cookie, límite de intentos y anti-enumeración (`POST /auth/login` — US-009, RN-08, RN-09, SU-02, C-03, C-04, C-05)

- [ ] 4.1 ROJO `tests/test_auth_login.py`: tests para `POST /auth/login`:
  - `200` con credenciales válidas: `Set-Cookie` incluye `access_token`, `HttpOnly`, `SameSite=lax`, `Max-Age=1800`; el cuerpo JSON contiene sólo `mensaje`, `debe_cambiar_password` y `expira_en_segundos` (sin token); registra fila `exito=True` en `intento_acceso`;
  - `401` con correo existente y contraseña errónea vs correo inexistente: ambos ejecutan `bcrypt` (real vs `app.state.hash_ficticio`), devuelven idéntico cuerpo JSON y registran el intento fallido en `intento_acceso` desde una sesión propia que sobrevive al `401` (C-04);
  - sexto intento dentro de 60 s para el mismo `(email, ip)` responde `429` con cabecera `Retry-After` sin invocar `bcrypt` (espía sobre `bcrypt.checkpw`) y sin insertar una sexta fila de fallo en `intento_acceso` (quedan 5 fallos, C-05, SU-02);
  - un login exitoso antes del 5.º fallo reinicia el conteo (los fallos anteriores siguen en `intento_acceso` pero no bloquean nuevos intentos);
  - contraseña de más de 72 bytes en el login responde `422`.
  Ejecutar pytest y verificar que falla
- [ ] 4.2 VERDE `app/modules/usuarios/service.py` y `router.py`: implementar `login` y `POST /auth/login` con el orden estricto de design D6 y la sesión independiente para `intento_acceso` con el comentario obligatorio del Ejercicio 7. Ejecutar `tests/test_auth_login.py` y verificar que pasa en verde

## 5. Logout, `/auth/yo` y cambio de contraseña (`POST /auth/logout`, `GET /auth/yo`, `POST /auth/cambiar-password` — US-010, RN-07, C-09 parcial)

- [ ] 5.1 ROJO `tests/test_auth_sesion_y_password.py`: tests para:
  - `POST /auth/logout` → `200` borrando la cookie `access_token`;
  - `GET /auth/yo` → `200` con datos del usuario (sin `password_hash`), `roles_vigentes` de la base y `roles_token` del JWT; `401` sin cookie o con `Authorization: Bearer` sin cookie (C-03);
  - `POST /auth/cambiar-password`: verifica contraseña actual (`401` si es incorrecta), calcula nuevo hash antes de abrir la transacción, actualiza `password_hash`, `password_cambiada_en`, `debe_cambiar_password=False` y registra el evento en `evento_seguridad` en un solo UoW; emite una cookie `access_token` nueva válida (`200` en `/auth/yo`) y deja inválida de inmediato la cookie anterior (`401` en `/auth/yo` sin esperar entre login y cambio, RN-07); `422` si la contraseña actual o nueva supera 72 bytes.
  Ejecutar pytest y verificar que falla
- [ ] 5.2 VERDE `app/modules/usuarios/service.py` y `router.py`: implementar `POST /auth/logout`, `GET /auth/yo` y `POST /auth/cambiar-password` según design D7. Ejecutar `tests/test_auth_sesion_y_password.py` y verificar que pasa en verde

## 6. Casos `.http` (`C-01` a `C-05`), verificación integral y bitácora

- [ ] 6.1 Crear los archivos `.http` en `test/` con la respuesta esperada en comentarios y verificar que las peticiones reflejan los datos de `seed.py`:
  - `test/C-01_parametro_no_entero.http` (parámetro de ruta no entero con sesión iniciada → `422` sin ejecutar el handler);
  - `test/C-02_registro_cliente.http` (registro `201`; correo y documento repetidos → `409` con mensaje propio y sin filas sueltas);
  - `test/C-03_login_cookie.http` (`Set-Cookie` con `HttpOnly`, `SameSite=Lax` y `Max-Age`; cuerpo sin token; sin cookie o con `Authorization: Bearer` → `401`);
  - `test/C-04_login_anti_enumeracion.http` (correo existente con contraseña mala y correo inexistente → `401` con el mismo cuerpo y tiempo parecido);
  - `test/C-05_login_limite_intentos.http` (seis intentos fallidos seguidos → el sexto responde `429` con `Retry-After` en pocos milisegundos y los cinco fallos están en `intento_acceso`)
- [ ] 6.2 Ejecutar toda la suite de pytest (`.venv/Scripts/python -m pytest`) y verificar que el 100 % de los tests de CH-01, CH-02, CH-03 y CH-04 pasan en verde y que se cumplen RN-01, RN-02, RN-07, RN-08, RN-09, RN-18 y las reglas 8–11, 13, 14 y 16 de `CLAUDE.md`
- [ ] 6.3 Actualizar la sección `## Hernán` en `docs/bitacora.md` con la entrada de CH-04 (`autenticacion`): fecha, qué se le pidió al agente, qué se revisó/corrigió a mano y decisiones clave (D1 a D8)
- [ ] 6.4 **[CHECKPOINT 3 — Cierre de CH-04 y propuesta de commits]** Mostrar el estado final (`git status` sin `.env`, suite pytest en verde, archivos `.http`) y presentar la división de commits en español para que Hernán confirme

## Workflow follow-up

- Abrir PR `feat/autenticacion` → `main` con `Closes #4` y pedir revisión de al menos un compañero.
- Una vez mergeado: ejecutar `/opsx:archive autenticacion`, marcar `[x]` en `CHANGES.md` y continuar con CH-05 (`autorizacion-y-roles`).
