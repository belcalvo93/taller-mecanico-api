# Resultados de la Fase B (los 19 casos con CH-01..CH-08 en `main`)

Fecha de la corrida: 2026-10-30. Base: `taller`, sembrada con `python seed.py` antes de cada archivo (C-13 continúa a C-12 sin volver a sembrar, como indica su encabezado). Servidor: `uvicorn main:app --port 8000` con `SQL_ECHO=true`.

Los `.http` se ejecutaron con el mismo script descartable de la Fase A (httpx, fuera del repo; reproduce `@var`, `# @name`, `# @no-cookie-jar` y `{{nombre.response.headers.Set-Cookie}}`). Las URLs usaron `127.0.0.1` en lugar de `localhost` por la misma razón que en la Fase A (resolución del nombre en Windows). `ordenes` está montado en `main.py` (`rutas_protegidas.include_router(ordenes_router)`) y `GET /openapi.json` lista `/ordenes`, `/mis-ordenes`, `/ordenes/{id}`, `/ordenes/{id}/iniciar|terminar|cancelar` y `/estados-orden`.

## Migraciones

| Paso | Resultado |
|---|---|
| `alembic upgrade head` | OK |
| `alembic downgrade base` | OK (0002 -> 0001 -> base) |
| `alembic upgrade head` | OK (`alembic current` = 0002, head) |

## Casos

| Caso | Archivo | Esperado | Obtenido | Resultado | Dueño si falla |
|---|---|---|---|---|---|
| C-01 | `C-01_parametro_no_entero.http` | 200 login; 422 con `/usuarios/abc/roles`, `/clientes/abc` y `/ordenes/abc` | 200, 422, 422, 422 (`int_parsing`) | Aprobado | — |
| C-02 | `C-02_registro_cliente.http` | 201; 409 correo repetido; 409 documento de Jorge; 422 campo extra; 422 contraseña de 74 bytes | 201 (id 8, cliente_id 3), 409, 409, 422 (`extra_forbidden`), 422 | Aprobado | — |
| C-03 | `C-03_login_cookie.http` | login con cookie, cuerpo sin token; `/auth/yo` 200; logout 200; sin cookie 401; con Bearer 401 | 200, 200, 200, 401, 401 (el paso 5 sigue mandando el token de relleno; ver Observaciones de la Fase A) | Aprobado | — |
| C-04 | `C-04_login_anti_enumeracion.http` | 401 con el mismo cuerpo y tiempo parecido | 401 `{"detail":"Credenciales inválidas"}` en los dos. El tiempo se midió en la Fase A (311 ms contra 337 ms) | Aprobado (confirmar el tiempo con REST Client) | — |
| C-05 | `C-05_login_limite_intentos.http` | cinco 401 y el sexto 429 con `Retry-After` | 401 x5 y 429 "Demasiados intentos fallidos..." | Aprobado (confirmar el tiempo con REST Client) | — |
| C-06 | `C-06_401_contra_403_y_lo_propio.http` | 401 sin cookie; Laura 403 en `GET /ordenes` y `POST /ordenes`; 200 en `/mis-ordenes`; 403 en la orden 2 ajena; 200 `/auth/yo`; recepción 200 en `/ordenes` y 200 con lista vacía en `/mis-ordenes` | 401, 200, 403, 403, 200, 403 ("Sin permiso sobre esta orden"), 200, 200, 200, 200 (`items: []`) | Aprobado | — |
| C-07 | `C-07_revocacion_rol_y_vencimiento.http` | recepción 200; revocar su rol; misma cookie 403; `/auth/yo` con `roles_vigentes` distinto de `roles_token`; fila revocada sigue; vencimiento pasado y sin zona 422 | 200 x4 (el 4.º con `revocada_en`), 403, 200, 200 con la fila, 422, 422 | Aprobado | — |
| C-08 | `C-08_autoproteccion_admin.http` | 409 al revocarse su propio ADMIN; 200 al revocar a admin2; 409 siendo el único | 200, 409, 200, 409 | Aprobado | — |
| C-09 | `C-09_cambio_obligatorio_password.http` | 403 en `/mis-vehiculos`; `/auth/yo` 200; cambio 200 con cookie nueva; la nueva 200; la anterior 401 | 200 (`debe_cambiar_password: true`), 403, 200, 200, 200 `[]`, 401 "sesión revocada por cambio de contraseña" | Aprobado | — |
| C-10 | `C-10_alta_de_orden.http` | 201 con dos ítems (total calculado por el servidor); 409 repuesto inexistente; 422 con `total` en el cuerpo | 201 (orden 3, total 68000.00), 409 "Algún repuesto no existe o fue dado de baja", 422 (`extra_forbidden`) | Aprobado | — |
| C-11 | `C-11_stock_insuficiente.http` | terminar la orden 2 (4 bujías, stock 2) da 409; la orden sigue EN_REPARACION; stock 2; sin movimiento de la orden | 409 "No hay stock suficiente de BUJ-100", orden EN_REPARACION, stock 2, movimientos sin `orden_id` | Aprobado | — |
| C-12 | `C-12_reponer_y_terminar.http` | reponer 10 (stock 12); terminar 200 (TERMINADA); stock 8; movimiento de -4 con `orden_id`; aviso en el servidor después de la respuesta | 200 (stock 12), 200 TERMINADA, stock 8, movimiento `{orden_id: 2, cantidad: -4, motivo: "Orden 2 terminada"}`; el aviso "Aviso a Jorge Gómez: su vehículo AD789GH (orden 2) está listo para retirar" salió en el log del servidor (los acentos se ven rotos en la consola de Windows; ver [C-12_aviso.txt](C-12_aviso.txt)) | Aprobado | — |
| C-13 | `C-13_cancelar_orden.http` | Laura 403 en la orden 2 ajena; 200 en la suya (1); 409 al repetir; recepción 409 sobre la orden 2 TERMINADA | 403, 200 CANCELADA, 409 "La orden está en CANCELADA...", 200 (login), 409 "La orden está en TERMINADA..." | Aprobado | — |
| C-14 | `solo_agregado.sql` | siete rechazos (seis del disparador y uno de la FK), sin cambiar datos | siete errores; conteos de las tres tablas iguales antes y después (3, 4, 1), con la base de la corrida final. Ver "Evidencia de C-14" | Aprobado | — |
| C-15 | `C-15_detalle_sin_n_mas_1.http` | detalle con 2 y con 4 ítems con el mismo número de consultas | 200 y 200; 5 SELECT en cada uno (2 de autenticación y roles + 3 de la orden). Ver "Evidencia de C-15" | Aprobado | — |
| C-16 | `C-16_busqueda_con_comillas.http` | `' OR '1'='1` lista vacía total 0; `q=freno&size=1` total 1; page=2 422; size=500 422; PATCH parcial; PATCH stock 422; stock intacto | 200 vacía, 200, 422 "La página 2 no existe: hay 1", 422, 200, 422 (`extra_forbidden`), 200 stock 4 | Aprobado | — |
| C-17 | `C-17_catalogo_y_filtro.http` | 401 sin cookie; catálogo 200; `POST /estados-orden` no existe; filtro `PENDIENTE` 200; estado fuera del catálogo 422 | 401, 200 (4 estados), 405, 200, 422 (`enum`) | Aprobado | — |
| C-18 | `C-18_historial_de_precios_y_permiso.http` | precio 9500 agrega una línea; el PATCH de descripción no agrega; recepción 403 en precios y PATCH; recepción 200 en el catálogo | 200, dos líneas, 200, mismas dos líneas, 403, 403, 200 | Aprobado | — |
| C-19 | `C-19_baja_y_reuso_de_patente.http` | 204 baja; 201 misma patente para Jorge; 409 segunda vigente igual; 404 baja repetida; 409 con orden abierta | 200, 200, 204, 200, 201 (id 4), 409, 404, 409 | Aprobado | — |

Casos aprobados: 19 de 19. Fallados: 0 (no hay nada que avisar a ningún dueño). Ninguno queda "pendiente".

Para confirmar a mano con REST Client: C-04 y C-05 (tiempos) y C-03 paso 5 con un token real (igual que en la Fase A).

## Evidencia de C-14

`psql -h localhost -U taller -d taller -f test/solo_agregado.sql` (con `PGCLIENTENCODING=UTF8`) tras `python seed.py`: siete errores (seis "es de sólo agregado: no se permite UPDATE/DELETE" sobre `historial_estado_orden`, `movimiento_stock` y `historial_precio_repuesto`, y uno por la FK `fk_orden_trabajo_estado_estado_orden`). Conteos de las tres tablas antes y después: 3, 4, 1. La salida completa y la captura siguen en [C-14_salida_psql.txt](C-14_salida_psql.txt) y [C-14_psql.png](C-14_psql.png).

## Evidencia de C-15

Se volvió a verificar sobre `main` con `SQL_ECHO=true` (orden 1 con 2 ítems y orden 3 con 4 ítems): 5 SELECT en cada detalle (usuario, orden + vehículo + cliente, ítems + repuestos, historial, roles vigentes). Es lo mismo que ya estaba en [C-15_consola.txt](C-15_consola.txt), que por eso no se modificó.

## Suite pytest

`pytest` completa sobre `taller_test` (migrada con `alembic upgrade head`): **916 passed** en 197 s (en la Fase A eran 761).

## Revisión de los PR (AP-07)

Autores en GitHub: Belén = `belcalvo93`, Elías = `eEmanuel07`, Hernán = `mhernangonzalez32-gif`, Joaquín = `joaquinmo1`, Bruno = `BrunoFiouchetta`.

| PR | Rama | Autor | Aprobado por | Estado |
|---|---|---|---|---|
| #23 | `feat/autorizacion-y-roles` | Hernán | Belén | Aprobado |
| #22 | `feat/ordenes` | Elías | Belén | Aprobado |
| #21 | `feat/casos-y-entrega` (Fase A) | Belén | Elías | Aprobado |
| #20 | `feat/repuestos-y-stock` | Bruno | Elías, Belén | Aprobado |
| #19 | `feat/autorizacion-y-roles` | Hernán | Elías | Aprobado |
| #18 | `chore/archivar-esquema-y-migraciones` | Belén | Elías | Aprobado |
| #17 | `feat/clientes-y-vehiculos` | Joaquín | Hernán | Aprobado |
| #16 | `feat/autenticacion` | Hernán | Belén | Aprobado |
| #15 | `feat/autenticacion` | Hernán | Elías | Aprobado |
| #14 | `feat/nucleo-repositorios-uow` | Elías | Belén | Aprobado |
| #13 | `feat/esquema-y-migraciones` | Belén | Elías | Aprobado |
| #12 | `feat/infra-base` (CH-01) | Belén | nadie | **Sin aprobación** (`REVIEW_REQUIRED`), mergeado por Belén |
| #11 | `chore/fundacion-final` | Belén | nadie | **Sin aprobación**, mergeado por Belén |
| #10 | `chore/organizacion` | Belén | nadie | **Sin aprobación**, mergeado por Belén |

Hallazgos (dueño: Belén): los PR #10, #11 y #12 se mergearon sin aprobación; #12 es el de `infra-base` (CH-01), el único change de código sin revisión de un compañero; conviene explicarlo en la demo. Los demás changes de código tienen PR aprobado por un compañero. Detalle menor: en #21 consta una revisión de Joaquín descartada (`DISMISSED`) y en #20 un comentario del revisor automático de GitHub. Bruno y Joaquín no figuran como aprobadores de ningún PR (Joaquín sólo con esa revisión descartada).

## Archivado de changes

| Change | Resultado |
|---|---|
| `autorizacion-y-roles` | archivado como `openspec/changes/archive/2026-10-30-autorizacion-y-roles`; specs creadas: `auditoria-eventos`, `cambio-obligatorio-y-acceso`, `gestion-personal-y-roles` |
| `repuestos-y-stock` | archivado como `2026-10-30-repuestos-y-stock`; spec creada: `repuestos-y-stock` |
| `ordenes` | archivado como `2026-10-30-ordenes`; specs creadas: `catalogo-estados-orden`, `consulta-de-ordenes`, `ordenes-de-trabajo` |

Los tres deltas eran sólo ADDED sobre capacidades nuevas; se sincronizaron con `openspec archive <change> --yes` (crea el spec principal con los requisitos ADDED). Sólo queda activo `casos-y-entrega`.

## Resumen de la Fase B

| Concepto | Resultado |
|---|---|
| Casos aprobados | 19 de 19 (C-01 a C-19) |
| Casos fallados | 0 |
| Pendientes | 0 |
| Confirmar a mano con REST Client | C-04 y C-05 (tiempos); C-03 paso 5 con un token real |
| Suite pytest | 916 passed |
| Verificación RN-01..RN-20 | ver [verificacion-rn.md](verificacion-rn.md) |
| PR sin aprobación | #10, #11 y #12 (Belén) |
| Changes archivados | `autorizacion-y-roles`, `repuestos-y-stock`, `ordenes` |
