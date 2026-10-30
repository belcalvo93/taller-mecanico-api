# Resultados de la Fase A (casos disponibles con CH-01..CH-07)

Fecha de la corrida: 2026-10-29. Base: `taller`, sembrada con `python seed.py` antes de cada archivo. Servidor: `uvicorn main:app --port 8000`.

Los `.http` se ejecutaron con un script descartable (httpx, fuera del repo) que reproduce lo que hace REST Client (`@var`, `# @name`, `# @no-cookie-jar`, `{{nombre.response.headers.Set-Cookie}}`). Las URLs usaron `127.0.0.1` en lugar de `localhost`: con `localhost` el cliente de la corrida sumaba ~2 s por pedido (resolución del nombre en Windows), lo que falseaba los tiempos de C-04 y C-05; no es un problema de la API.

## Migraciones

| Paso | Resultado |
|---|---|
| `alembic upgrade head` | OK (0001, 0002) |
| `alembic downgrade base` | OK |
| `alembic upgrade head` | OK (`alembic current` = 0002, head) |

## Casos

| Caso | Archivo | Esperado | Obtenido | Resultado | Dueño si falla |
|---|---|---|---|---|---|
| C-01 | `C-01_parametro_no_entero.http` | 200 login; 422 con `/usuarios/abc/roles` y `/clientes/abc` | 200, 422, 422 (`int_parsing`) | Aprobado | — |
| C-02 | `C-02_registro_cliente.http` | 201; 409 correo repetido; 409 documento de Jorge; 422 campo extra; 422 contraseña de 74 bytes | 201 (id 8, cliente_id 3), 409, 409, 422, 422. En la base: 8 usuarios, 3 clientes, 8 roles, ninguna fila suelta y la ficha de Jorge sigue con `usuario_id` NULL | Aprobado | — |
| C-03 | `C-03_login_cookie.http` | Set-Cookie `HttpOnly; Max-Age=1800; Path=/; SameSite=lax`, cuerpo sin token; `/auth/yo` 200; logout 200 con `Max-Age=0`; sin cookie 401; con Bearer 401 | Todo igual. El paso 5 del archivo manda un token de relleno (`PEGAR_ACA_EL_TOKEN_DEL_PASO_1`); aparte probé con un JWT real en `Authorization: Bearer` y sin cookie: 401, y el mismo JWT en la cookie: 200 | Aprobado | — |
| C-04 | `C-04_login_anti_enumeracion.http` | 401 con el mismo cuerpo y tiempo parecido | 401 `{"detail":"Credenciales inválidas"}` en los dos; 311 ms (correo existente) contra 337 ms (inexistente) | Aprobado (confirmar el tiempo con REST Client) | — |
| C-05 | `C-05_login_limite_intentos.http` | cinco 401 y el sexto 429 con `Retry-After`, en pocos ms; 5 filas en `intento_acceso` | cinco 401 (~270 ms cada uno), sexto 429 con `Retry-After: 59` en 30 ms; `intento_acceso`: 5 filas con `exito = false` | Aprobado (confirmar el tiempo con REST Client) | — |
| C-07 | `C-07_revocacion_rol_y_vencimiento.http` | recepción 200; revocar su rol; misma cookie 403; `/auth/yo` con `roles_vigentes: []` y `roles_token: ["RECEPCION"]`; fila revocada sigue; vencimiento pasado y sin zona horaria 422 | 200, 200, 200, 200 con `revocada_en`, 403, 200 (diferencia visible), 200 con la fila, 422, 422 | Aprobado | — |
| C-08 | `C-08_autoproteccion_admin.http` | 409 al revocarse su propio ADMIN; 200 al revocar a admin2; 409 siendo el único | 200, 409, 200, 409 | Aprobado | — |
| C-09 | `C-09_cambio_obligatorio_password.http` | 403 en `/mis-vehiculos`; `/auth/yo` 200; cambio 200 con cookie nueva; la nueva 200; la anterior 401 | 200 (`debe_cambiar_password: true`), 403, 200, 200 con nueva cookie, 200 `[]`, 401 "sesión revocada por cambio de contraseña" | Aprobado | — |
| C-16 | `C-16_busqueda_con_comillas.http` | `' OR '1'='1` lista vacía total 0; `q=freno&size=1` total 1 pages 1; page=2 422; size=500 422; PATCH parcial; PATCH stock 422; stock intacto | 200 vacía, 200 (FRE-010), 422 "La página 2 no existe: hay 1", 422, 200, 422 (`extra_forbidden`), 200 stock 4 | Aprobado | — |
| C-18 | `C-18_historial_de_precios_y_permiso.http` | precio 9500 agrega una línea (8500 → 9500, usuario 1); el PATCH de descripción no agrega; recepción 403 en precios y PATCH; recepción 200 en el catálogo | 200, dos líneas, 200, mismas dos líneas, 403, 403, 200 | Aprobado | — |
| C-19 | `C-19_baja_y_reuso_de_patente.http` | 204 baja; 201 misma patente para Jorge; 409 segunda vigente igual; 404 baja repetida; 409 con orden abierta | 200, 200, 204, 200, 201 (id 4), 409, 404, 409 | Aprobado | — |
| C-14 | `solo_agregado.sql` | siete rechazos (seis del disparador y uno de la FK), sin cambiar datos | siete errores; conteos de las tres tablas iguales antes y después (3, 4, 1). Salida en `C-14_salida_psql.txt` | Aprobado (captura de pantalla pendiente de Belén) | — |

## Pendientes de CH-08 (Fase B)

| Caso | Motivo | Dueño del `.http` |
|---|---|---|
| C-06 | necesita los endpoints de órdenes | Elías (CH-08) |
| C-10 | necesita los endpoints de órdenes | Elías (CH-08) |
| C-11 | necesita los endpoints de órdenes | Elías (CH-08) |
| C-12 | necesita los endpoints de órdenes | Elías (CH-08) |
| C-13 | necesita los endpoints de órdenes | Elías (CH-08) |
| C-15 | necesita el detalle de una orden; evidencia con `SQL_ECHO=true` | Elías (CH-08) |
| C-17 | necesita el catálogo de estados y el filtro de órdenes | Elías (CH-08) |

## Observaciones sobre los archivos de los compañeros (sin modificar)

- C-03, paso 5: el `.http` manda `Authorization: Bearer PEGAR_ACA_EL_TOKEN_DEL_PASO_1` como texto literal; el 401 que da sería el mismo con cualquier valor. No es un fallo del caso, pero conviene pegar un token real al correrlo con REST Client (dueño: Hernán, CH-04).

## Prueba del README (base `taller_readme`)

Se siguieron los pasos del README sobre una copia limpia de los archivos versionados (más el README nuevo), sin `.env` ni `.venv`, con la base `taller_readme` (vacía, owner `taller`). La base `taller` y el `.env` real no se tocaron.

| Paso del README | Resultado |
|---|---|
| 1.1 `python -m venv .venv` + `pip install -r requirements.txt` | OK con Python 3.14.7; `pip check`: sin conflictos |
| 1.3 `cp env.example .env`, completar contraseña y `POSTGRES_DB=taller_readme`, clave con `python -c "import secrets; print(secrets.token_urlsafe(64))"` (86 caracteres) | OK |
| 1.4 `alembic upgrade head`, `downgrade base`, `upgrade head`, `current` | OK; `current` = `0002 (head)` |
| 1.5 `python seed.py` | OK: 7 usuarios, 4 estados, 2 órdenes |
| 1.6 `uvicorn main:app --port 8001` | `GET /health/live` = 200; login de `admin@example.com` = 200; con `SQL_ECHO=true` las consultas salen en el log |

Limitación de la prueba: la ruta de la copia (en el directorio temporal de esta herramienta) supera los 260 caracteres de Windows y el `.venv` de ahí no pudo cargar una DLL de SQLAlchemy; por eso desde el paso 1.4 se usó el intérprete del `.venv` del proyecto ejecutando dentro de la copia limpia. El paso 1.1 (instalación) sí se probó en el venv nuevo. Los servidores de prueba (puertos 8000 y 8001) se bajaron al terminar.

## Checklist de entrega

| Ítem | Resultado | Evidencia |
|---|---|---|
| `requirements.txt` | OK | 11 dependencias: fastapi[standard], sqlmodel, sqlalchemy[asyncio], asyncpg, alembic, pydantic-settings, bcrypt, PyJWT, pytest, pytest-asyncio, httpx; versiones mínimas. `asyncpg>=0.31` (la consigna dice 0.30): decisión de CH-01, documentada en la bitácora |
| `env.example` sin secretos | OK | `POSTGRES_PASSWORD=` y `JWT_SECRET_KEY=` vacías; incluye el comando para generar la clave |
| `alembic.ini` sin credenciales | OK | sin `sqlalchemy.url` ni usuario/contraseña; la URL sale de `get_settings().DATABASE_URL` |
| `migrations/` con 2 versiones | OK | `0001_esquema_inicial.py` (autogenerada) y `0002_solo_agregado.py` (a mano) |
| Comentario de lectura en cada migración | OK | 0001: "Leída antes de aplicarla por Belén Calvo el 25/10/2026"; 0002: ídem |
| `upgrade head` → `downgrade base` → `upgrade head` | OK | corrido en `taller` y en `taller_readme` |
| `test/` | OK | 11 `.http` y `solo_agregado.sql` (los de CH-08 todavía no están: C-06, C-10 a C-13, C-15, C-17) |
| `.env` fuera del repositorio | OK | `git ls-files` no lo incluye; `git check-ignore -v .env` → `.gitignore:2`; nunca estuvo en el historial (`git log --all -- .env` vacío) |
| Sin credenciales en archivos versionados | OK | búsqueda de URLs de conexión con contraseña, claves de firma, contraseñas literales y JWT en `git ls-files` (sin `seed.py` ni `tests/`, que llevan contraseñas de prueba): sin hallazgos reales (una coincidencia falsa: una etiqueta de texto "Cambio de contraseña") |
| Sin valores por defecto de secretos en el código | OK | en `Settings`, `POSTGRES_PASSWORD` y `JWT_SECRET_KEY` son `SecretStr` obligatorios sin default |
| Sin `create_all` | OK | ninguna ocurrencia en `app/`, `main.py`, `migrations/` ni `seed.py` |

## Suite pytest

`pytest` completa sobre `taller_test` (migrada con `alembic upgrade head`, versión `0002`): **761 passed** en 194 s. Al terminar, `taller_test` quedó vacía (0 filas en `usuario`, `orden_trabajo` y `estado_orden`).

## Revisión de la bitácora (`docs/bitacora.md`)

Cada integrante tiene su sección. Todas las entradas existentes tienen fecha, qué se le pidió al agente y qué se corrigió a mano y por qué. Estado según los changes que hizo cada uno (CH-01 a CH-08):

| Integrante | Changes | Entradas que existen | Faltan |
|---|---|---|---|
| Belén | CH-01, CH-02 (y CH-09) | CH-01 `infra-base` (2026-10-25); CH-02 `esquema-y-migraciones` (2026-10-25); CH-09 `casos-y-entrega`, Fase A (2026-10-29, en curso) | cerrar la entrada de CH-09 con la Fase B |
| Elías | CH-03, CH-08 | CH-03 `nucleo-repositorios-uow` (2026-10-27) | **CH-08 `ordenes`** (no está mergeado; entrada a su cargo) |
| Hernán | CH-04, CH-05 | CH-04 `autenticacion` en 3 entradas (2026-10-27: Gate T1, contratos y repositorios, login y cambio de contraseña); CH-05 `autorizacion-y-roles` (2026-10-28) | ninguna |
| Joaquín | CH-06 | CH-06 `clientes-y-vehiculos` (2026-10-27) | ninguna |
| Bruno | CH-07 | CH-07 `repuestos-y-stock` (2026-10-29) | ninguna |

La entrada de Belén de CH-09 se redactó a partir de lo que Belén pidió en esta sesión; la de CH-08 no se redactó por Elías.

Hallazgos (informativos, sin corregir):

- Hay archivos de herramientas versionados que no son parte de la entrega: `.active-orchestrator-state.json` y `.claude/commands/opsx/*.md`. No contienen credenciales; decidir si se dejan (dueño: Belén, change `infra-base`).
- `test/.gitkeep` sigue versionado aunque `test/` ya tiene archivos; es inocuo.

## Resumen de la Fase A

| Concepto | Resultado |
|---|---|
| Casos aprobados | 12 de 19: C-01 a C-05, C-07, C-08, C-09, C-14, C-16, C-18 y C-19 |
| Casos fallados | 0 (ningún caso para avisar a su dueño) |
| Pendientes de CH-08 (Fase B) | 7: C-06, C-10, C-11, C-12, C-13, C-15 y C-17 |
| Total | 12 + 0 + 7 = 19 |
| Confirmar a mano con REST Client | C-04 y C-05 (tiempos); C-03 paso 5 con un token real |
| Captura de pantalla pendiente de Belén | C-14 (psql) |
| Suite pytest | 761 passed |
| Checklist de entrega | todos los ítems OK; dos hallazgos informativos (archivos de herramientas versionados, `test/.gitkeep`) |
| Bitácora | falta la entrada de CH-08 de Elías; la de Belén para CH-09 se cierra con la Fase B |
