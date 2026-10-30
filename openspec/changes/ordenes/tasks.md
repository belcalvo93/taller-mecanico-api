# Tasks

> TDD estricto en cada tarea: **ROJO** (escribir primero el test, ejecutarlo y ver que falla por la razón esperada) → **VERDE** (código mínimo) → **TRIANGULAR** (otro caso con datos distintos) → **REFACTOR** (suite verde tras cada paso). Cada escenario de las specs tiene al menos un test.
> Tests en `tests/test_ordenes_*.py` contra `taller_test` (la fija `tests/conftest.py`). Comando: `python -m pytest` desde la raíz.
> Los grupos 1 a 8 **no dependen de CH-07**. El grupo 9 está **bloqueado por CH-07** (`repuestos-y-stock`) y se hace después de rebasear sobre `main` con CH-07 mergeado (design D2 y D4).
> Sin líneas de coautoría ni de sesión en los commits. El `.env` no se versiona.

## 0. Red de seguridad

- [x] 0.1 Correr la suite completa sobre `main` (`b7e5b73`) y anotar la línea base (N passed) en la bitácora; si algo falla, frenar y reportarlo como falla previa
- [x] 0.2 Acordar con Bruno la firma del punto único de stock (design D4: vive en el repositorio, recibe la sesión, hace flush sin commit, no abre UoW) y dejarlo escrito en el issue #7 o #8 — la firma de `mover_stock` del PR #20 coincide con D4

## 1. Catálogo de estados (sólo lectura) y registro del router

- [x] 1.1 ROJO→VERDE `tests/test_ordenes_catalogo.py`: `EstadoOrdenRepository(session).listar_por_posicion()` devuelve los 4 estados del seed en orden 1..4 con `es_final` sólo en TERMINADA y CANCELADA; `get("PENDIENTE")` lo trae y `get("NO_EXISTE")` devuelve `None`
- [x] 1.2 ROJO→VERDE el repositorio no hereda de `BaseRepository` y no tiene `add`, `update` ni `delete` (D3)
- [x] 1.3 ROJO→VERDE `EstadoOrdenCodigo` (enum en `schemas.py`): sus valores son exactamente los códigos que carga `seed.py`
- [x] 1.4 ROJO→VERDE `GET /estados-orden` con sesión real (login): 200 con los 4 por posición para ADMIN y para Laura (sólo CLIENTE); sin cookie → 401; `POST`/`DELETE /estados-orden` → 405 (C-17, parte). Incluye `router.py` mínimo y la línea `include_router` de CH-08 en el grupo protegido de `main.py`, verificada con un test de que las rutas de órdenes están en el grupo protegido y no en el abierto
- [x] 1.5 Commit: `feat(ordenes): catálogo de estados de sólo lectura y GET /estados-orden` (agrupado en los commits de feat/ordenes)

## 2. Contratos

- [x] 2.1 ROJO→VERDE `tests/test_ordenes_contratos.py` `OrdenCrear`: acepta el cuerpo de ejemplo de la consigna; rechaza `total`, `estado`, `creada_en` y `precio_unitario` en un ítem (`extra="forbid"`); `items` vacío; `falla` vacía, sólo espacios o con NUL
- [x] 2.2 ROJO→VERDE `ItemOrdenCrear` y validación de lista: `repuesto_id` repetido → error; `cantidad` 0, −1 y 10 001 → error, 1 y 10 000 → ok; ids 0 y 2 147 483 648 → error; más de 50 ítems → error
- [x] 2.3 ROJO→VERDE `armar_detalle(orden)` (función pura, sin base): con una orden en memoria de dos ítems calcula `subtotal` por ítem, ordena los ítems por `id`, toma `patente` y `cliente` de las relaciones y serializa importes como `"32000.00"`; TRIANGULAR con cantidades y precios distintos
- [x] 2.4 Commit: `feat(ordenes): contratos de entrada y salida` (agrupado en los commits de feat/ordenes)

## 3. Repositorios y Unit of Work del módulo

- [x] 3.1 ROJO→VERDE `tests/test_ordenes_repositorios.py` `OrdenRepository.get_detalle(id)`: trae vehículo, cliente, ítems con su repuesto e historial sin tocar relaciones perezosas (acceder a ellas no lanza); `None` si no existe
- [x] 3.2 ROJO→VERDE `get_detalle` sin N+1: la misma cantidad de sentencias (fixture `sentencias`) para una orden de 2 ítems y otra de 4; TRIANGULAR con historial de 1 y de 3 líneas
- [x] 3.3 ROJO→VERDE `get_detalle` después de modificar la orden en la misma sesión devuelve el estado nuevo y el historial completo (`populate_existing`, D7)
- [x] 3.4 ROJO→VERDE `listar(estado, pagina)`: sin filtro trae las 2 del seed ordenadas por id; con PENDIENTE sólo la 1 y `total` 1; con TERMINADA página vacía (`total` 0, `pages` 1); `page` inexistente → `PaginaInexistente`
- [x] 3.5 ROJO→VERDE `listar_de_usuario(usuario_id, pagina)`: Laura (6) → sólo la orden 1; recepción (3, sin ficha) → página vacía; una orden de un vehículo de Laura dado de baja sigue apareciendo (D8)
- [x] 3.6 ROJO→VERDE `get_para_transicion(id)`: trae vehículo→cliente e ítems precargados y emite `FOR UPDATE` (se ve en las sentencias); `None` si no existe
- [x] 3.7 ROJO→VERDE `HistorialEstadoOrdenRepository.add` agrega con flush sin confirmar (otra sesión no la ve hasta el commit)
- [x] 3.8 ROJO→VERDE `OrdenesUnitOfWork(session)`: `ordenes`, `historial`, `estados`, `vehiculos`, `roles` y `repuestos` comparten la sesión; `repuestos` es `SoftDeleteRepository` de `Repuesto` (provisorio hasta CH-07, D2); `get_ordenes_uow` lo construye
- [x] 3.9 Commit: `feat(ordenes): repositorios de órdenes, historial y UoW del módulo` (agrupado en los commits de feat/ordenes)

## 4. Alta de una orden (RN-10, RN-16, RN-19) — C-10

- [x] 4.1 ROJO→VERDE `tests/test_ordenes_alta.py` `POST /ordenes` como recepción con el cuerpo de la consigna (vehículo 2, FRE-010×1, ACE-530×3): 201 con `estado` PENDIENTE, `patente` AC456EF, `cliente` "Laura Cliente", `total` "68000.00", subtotales, `mecanico_id` nulo e historial null → PENDIENTE con `usuario_id` 3; TRIANGULAR como ADMIN con otros ítems
- [x] 4.2 ROJO→VERDE precio fijo: cambiar por SQL el precio del repuesto después del alta no cambia `precio_unitario` ni `total` en `GET /ordenes/{id}`
- [x] 4.3 ROJO→VERDE 409 sin filas: repuesto inexistente (C-10), repuesto dado de baja, vehículo inexistente y vehículo dado de baja; en cada caso mensaje propio sin texto de la base y conteos de `orden_trabajo`, `item_orden` e `historial_estado_orden` iguales
- [x] 4.4 ROJO→VERDE total que no entra en NUMERIC(12,2) (precio subido por SQL + cantidades grandes) → 409 `TotalExcedido`, no 500, sin filas
- [x] 4.5 ROJO→VERDE catálogo vacío: test de servicio sobre `helpers.escenario(conexion, catalogo=False)` → `CatalogoVacio`; y por la ruta el router lo traduce a 409 con mensaje propio (D10)
- [x] 4.6 ROJO→VERDE permisos y contrato por la ruta: MECANICO y CLIENTE → 403 sin filas; cuerpo con `total` → 422; C-01: no aplica (sin `{id}`)
- [x] 4.7 `test/C-10_alta_de_orden.http`: login de recepción, alta con dos ítems (201 esperado en comentario) y alta con repuesto inexistente (409); correrlo contra el servidor real tras `python seed.py` — corrido contra el servidor real (36/36 OK)
- [x] 4.8 Commit: `feat(ordenes): alta de orden en un solo bloque (C-10)` (agrupado en los commits de feat/ordenes)

## 5. Consultas: detalle, listado y órdenes propias — C-06, C-15, C-17

- [x] 5.1 ROJO→VERDE `tests/test_ordenes_consultas.py` `GET /ordenes/{id}`: personal (recepción, mecánico, ADMIN) ve la orden 2 con BUJ-100×4 e historial de 2 líneas; inexistente → 404; un ítem con repuesto dado de baja sigue mostrando código y descripción
- [x] 5.2 ROJO→VERDE dueño: Laura ve la orden 1 (200) y no la 2 (403) (C-06)
- [x] 5.3 ROJO→VERDE C-15 por la ruta: crear por `POST /ordenes` una orden de 2 ítems y otra de 4; `GET` de cada una ejecuta la misma cantidad de sentencias
- [x] 5.4 ROJO→VERDE `GET /ordenes`: `estado=PENDIENTE` → sólo la 1; `size=1` → `total` 2, `pages` 2; `estado=ENTREGADA` → 422 (C-17); `page=3&size=1` → 422 con mensaje propio; `size=500` → 422; Laura → 403
- [x] 5.5 ROJO→VERDE `GET /mis-ordenes`: Laura → sólo la orden 1, sin rol de personal; recepción → página vacía; `page=2` → 422
- [x] 5.6 ROJO→VERDE C-06 completo: sin cookie, las ocho rutas de órdenes y catálogo → 401; Laura → 403 en `GET /ordenes` y `POST /ordenes`; Laura → 200 en `/mis-ordenes` y `/auth/yo`; `nuevo@example.com` (cambio pendiente) → 403 en `GET /ordenes`
- [x] 5.7 ROJO→VERDE C-01: `GET /ordenes/abc` y `GET /ordenes/3000000000` con sesión → 422 sin ejecutar el servicio (servicio espiado)
- [x] 5.8 `test/C-06_401_contra_403_y_lo_propio.http` (dos sesiones: Laura y recepción, `# @name` + `# @no-cookie-jar`), `test/C-15_detalle_sin_n_mas_1.http` (alta de una orden de 4 ítems y `GET` de una de 2 y otra de 4, con la nota de `SQL_ECHO=true`) y `test/C-17_catalogo_y_filtro.http`; agregar una línea de órdenes a `test/C-01_parametro_no_entero.http`; correrlos contra el servidor real — corrido contra el servidor real (36/36 OK)
- [x] 5.9 Commit: `feat(ordenes): detalle sin N+1, listados y órdenes propias (C-06, C-15, C-17)` (agrupado en los commits de feat/ordenes)

## 6. Iniciar una orden (RN-11, SU-03)

- [x] 6.1 ROJO→VERDE `tests/test_ordenes_transiciones.py` `POST /ordenes/1/iniciar` como `mecanico2@`: 200, EN_REPARACION, `mecanico_id` 5 y línea PENDIENTE → EN_REPARACION con `usuario_id` 5
- [x] 6.2 ROJO→VERDE orden 2 (EN_REPARACION) → 409 sin línea nueva; inexistente → 404; ADMIN sin MECANICO → 403 y la orden sigue PENDIENTE; recepción → 403
- [x] 6.3 ROJO→VERDE C-01 en `/ordenes/abc/iniciar` → 422
- [x] 6.4 Commit: `feat(ordenes): iniciar orden` (agrupado en los commits de feat/ordenes)

## 7. Cancelar una orden (RN-12, RN-17) — C-13

- [x] 7.1 ROJO→VERDE Laura cancela la orden 1 (suya, PENDIENTE): 200, CANCELADA y línea PENDIENTE → CANCELADA con `usuario_id` 6
- [x] 7.2 ROJO→VERDE recepción y ADMIN cancelan una PENDIENTE de Jorge (insertada para el test) → 200
- [x] 7.3 ROJO→VERDE permiso antes que estado: Laura sobre la orden 2 (ajena y EN_REPARACION) → 403, no 409; mecánico sobre una PENDIENTE → 403
- [x] 7.4 ROJO→VERDE estado: recepción sobre una orden TERMINADA (insertada por SQL) → 409; sobre la orden 2 (EN_REPARACION) → 409; en ambos casos sin línea nueva; inexistente → 404; `/ordenes/abc/cancelar` → 422
- [x] 7.5 `test/C-13_cancelar_orden.http` (sesiones de Laura y de recepción): el dueño cancela la orden 1 → 200; la orden 2 (ajena) → 403. El tramo "terminada → 409" necesita terminar una orden por la API y se agrega en 9.9. Correrlo contra el servidor real — corrido contra el servidor real (36/36 OK)
- [x] 7.6 Commit: `feat(ordenes): cancelar orden con 403 antes que 409 (C-13)` (agrupado en los commits de feat/ordenes)

## 8. Terminar: permiso, estado y 404 (sin tocar stock)

- [x] 8.1 ROJO→VERDE `mecanico2@` sobre la orden 2 (asignada al 4) → 403 y nada cambia; recepción y Laura → 403
- [x] 8.2 ROJO→VERDE 403 antes que 409: `mecanico2@` sobre la orden 1 (PENDIENTE, sin asignar) → 403
- [x] 8.3 ROJO→VERDE ADMIN sobre la orden 1 (PENDIENTE) → 409 sin cambios; inexistente → 404; `/ordenes/abc/terminar` → 422
- [x] 8.4 Esqueleto de `terminar_orden` en el servicio hasta las comprobaciones (permiso → estado); el paso de stock queda marcado `# CH-07` y no se ejecuta en ningún test de este grupo
- [x] 8.5 Commit: `feat(ordenes): terminar orden — permisos y estado` (agrupado en los commits de feat/ordenes)

## 9. BLOQUEADO POR CH-07 — Terminar con descuento de stock (RN-13, RN-14, DD-14) — C-11, C-12

- [x] 9.1 Rebasear `feat/ordenes` sobre `main` con CH-07 mergeado; correr la suite completa y comparar con la línea base
- [x] 9.2 Reemplazar en `OrdenesUnitOfWork` el `SoftDeleteRepository(session, Repuesto)` por `RepuestoRepository(session)`; los tests de los grupos 3 a 8 siguen verdes
- [x] 9.3 ROJO→VERDE `tests/test_ordenes_terminar.py` C-12: reponer bujías (por el punto único de CH-07 o `POST /repuestos/3/reponer`) y terminar la orden 2 como `mecanico@` → 200, TERMINADA; stock de BUJ-100 baja 4; un movimiento −4 con `orden_id` 2; línea EN_REPARACION → TERMINADA con `usuario_id` 4
- [x] 9.4 ROJO→VERDE un movimiento por ítem: orden de 2 ítems terminada por ADMIN → exactamente 2 movimientos nuevos con las cantidades negativas y la línea de historial con el id del ADMIN
- [x] 9.5 ROJO→VERDE C-11: terminar la orden 2 sin reponer → 409 con mensaje propio; estado EN_REPARACION, stock 2, cantidad de movimientos e historial iguales; cubrir la excepción de dominio de CH-07 y el `IntegrityError` de `ck_repuesto_stock_no_negativo` (D4)
- [x] 9.6 ROJO→VERDE DD-14: dar de baja el repuesto de un ítem y terminar la orden con stock suficiente → 200 y el stock baja
- [x] 9.7 ROJO→VERDE aviso (D11): con terminar exitoso, el mensaje de `taller.avisos` aparece después del `http.response.body` final (app ASGI con `send` espiado, `asyncio.sleep` sin espera); con 409 (C-11) y con 403 no aparece (`caplog`)
- [x] 9.8 ROJO→VERDE ciclo completo: crear → iniciar → terminar deja 3 líneas de historial en orden
- [x] 9.8b ROJO→VERDE concurrencia: dos órdenes distintas con el mismo repuesto terminadas a la vez (stock para una sola → 200 y 409, stock inicial − N, un solo movimiento negativo; stock para ambas → dos 200 y dos descuentos); `OrdenRepository.bloquear_repuestos` con `FOR UPDATE` ordenado por id (D6)
- [x] 9.9 `test/C-11_stock_insuficiente.http` y `test/C-12_reponer_y_terminar.http` (sesiones de ADMIN y de mecánico); completar el caso "terminada → 409" de `test/C-13_cancelar_orden.http`; correrlos contra el servidor real y ver el aviso en la consola después de la respuesta — corrido contra el servidor real (36/36 OK)
- [x] 9.10 Commit: `feat(ordenes): terminar orden con descuento de stock y aviso (C-11, C-12)` (agrupado en los commits de feat/ordenes)

## 10. Cierre e integración

- [x] 10.1 Suite completa verde y comparación con la línea base de 0.1
- [x] 10.2 Verificar contra RN-10, RN-11, RN-12, RN-13, RN-14, RN-15, RN-16, RN-17, RN-18, RN-19, los casos C-01 (parte), C-06, C-10, C-11, C-12, C-13, C-15, C-17, y las reglas 6, 13, 14, 15, 16 y 17 de `CLAUDE.md`
- [x] 10.3 `docs/bitacora.md` (sección Elías): qué se le pidió al agente, qué se corrigió a mano y por qué; decisiones D5 (409 para vehículo/total), D8 (órdenes de vehículos dados de baja) y D11 (logger del aviso)
- [x] 10.4 `git status` sin `.env` ni archivos fuera del alcance

## Workflow follow-up

- PR `feat/ordenes` → `main` con `Closes #8` y revisión de un compañero (ideal: Bruno, por el punto único de stock, o Hernán, por permisos).
- Tras el merge: `/opsx:archive ordenes` y marcar CH-08 en `CHANGES.md`.
