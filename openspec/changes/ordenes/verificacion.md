# Verificación de CH-08 `ordenes` (grupo 10)

Suite completa: **916 passed** (195 s). Sin brechas encontradas en el código. Lo único pendiente es correr los `.http` contra el servidor real (ver al final).

## Reglas de negocio

| RN | Qué exige | Dónde está | Tests |
|---|---|---|---|
| RN-10 | Nace PENDIENTE, ≥1 ítem, sin repuestos repetidos; precio copiado; total del servidor | `schemas.OrdenCrear` (`extra="forbid"`, validador de repetidos), `service.crear_orden` | `test_ordenes_contratos` (precio/total rechazados, ítems vacíos, repetidos); `test_ordenes_alta::test_alta_como_recepcion_con_el_cuerpo_de_la_consigna`, `test_el_precio_queda_fijo_en_la_orden`, `test_total_que_no_entra_en_numeric_es_409_no_500` |
| RN-11 | Transiciones y quién las hace | `service.iniciar_orden` / `terminar_orden` / `cancelar_orden` | `test_ordenes_transiciones` (iniciar, terminar asignado/ADMIN, 409 por estado), `test_ordenes_terminar::test_ciclo_crear_iniciar_terminar_deja_tres_lineas_en_orden` |
| RN-12 | Cancelan recepción, admin o dueño; permiso antes que estado | `service.cancelar_orden`; ruta sin `requiere_rol` | `test_laura_cancela_su_orden_pendiente`, `test_recepcion_y_admin_cancelan...`, `test_403_antes_que_409_la_orden_ajena_en_reparacion`, `test_ajena_pendiente_tambien_403`, `test_el_dueno_cancela_aunque_el_vehiculo_este_dado_de_baja` |
| RN-13 | Terminar descuenta stock, un movimiento por ítem y una línea de historial; todo o nada | `service.terminar_orden` (un solo bloque `async with uow`) | `test_c12_*`, `test_un_movimiento_por_item_con_cantidades_negativas`, `test_c11_sin_stock_409_y_nada_cambia`, `test_c11_falta_en_el_segundo_item_revierte_el_primero`, `test_check_de_la_base_tambien_da_409`, `test_dos_terminaciones_simultaneas_*` |
| RN-14 | El stock solo cambia por el punto único | `terminar_orden` llama solo a `RepuestoRepository.mover_stock`; no hay otra asignación a `.stock` en el módulo (grep) | `test_c12_*` (movimiento −4 con `orden_id`); `test_repuestos_*` de CH-07 |
| RN-15 | Historial de sólo agregado | `_pasar_a` solo hace `historial.add`; el módulo no tiene rutas de alta ni de edición del historial | `test_historial_add_hace_flush_sin_confirmar`; `test_solo_agregado` (trigger, CH-02); una línea por transición en `test_ordenes_transiciones` ("sin línea nueva" en los 409) |
| RN-16 | Vehículo/repuesto dado de baja no se usa en órdenes nuevas; sus datos se conservan | `crear_orden` usa `get_by_id` (excluye bajas); detalle y terminar usan los datos aun con baja (DD-14) | `test_409_sin_filas`, `test_un_repuesto_valido_y_otro_inexistente_no_deja_nada`, `test_item_con_repuesto_dado_de_baja_sigue_mostrando_codigo_y_descripcion`, `test_dd14_repuesto_dado_de_baja_igual_descuenta`, `test_listar_de_usuario_incluye_ordenes_de_vehiculos_dados_de_baja` |
| RN-17 | Lo propio: el cliente ve sus órdenes y ninguna otra | `obtener_detalle` (personal o dueño → 403), `listar_de_usuario` filtra en la consulta | `test_el_dueno_ve_su_orden_y_no_la_ajena`, `test_sin_rol_vigente_ni_ficha_no_ve_la_orden`, `test_laura_ve_solo_sus_ordenes`, `test_personal_sin_ficha_de_cliente_pagina_vacia` |
| RN-18 | Sin texto de la base ni 500 por entrada inválida | `_ERRORES` del router (mensajes propios), `IdRuta` 1..2³¹−1, `Falla` sin NUL, tope del total, 409 por `ck_repuesto_stock_no_negativo` | `test_c01_id_invalido_422_sin_ejecutar_el_servicio` (consultas y transiciones), `test_contrato_invalido_422_sin_filas`, `test_ids_fuera_de_rango`, `test_total_que_no_entra_en_numeric_es_409_no_500`, `test_check_de_la_base_tambien_da_409` |
| RN-19 | Catálogo consultable, de solo lectura; vacío → 409 al crear | `EstadoOrdenRepository` (no hereda de `BaseRepository`), `GET /estados-orden`, `CatalogoVacio` | `test_ordenes_catalogo` (solo lectura, sin rutas de escritura, enum = seed), `test_catalogo_vacio_en_el_servicio`, `test_catalogo_vacio_por_la_ruta_es_409_con_mensaje_propio` |

## Casos C

| Caso | Cobertura automática | `.http` |
|---|---|---|
| C-01 (parte órdenes) | `test_c01_id_invalido_422_sin_ejecutar_el_servicio` (consultas y transiciones) | `C-01_parametro_no_entero.http` |
| C-06 | `test_c06_sin_cookie_las_ocho_rutas_son_401`, `test_c06_laura_es_403_en_listar_y_crear_y_200_en_lo_propio`, `test_c06_cambio_de_password_pendiente_es_403`, `test_el_dueno_ve_su_orden_y_no_la_ajena` | `C-06_401_contra_403_y_lo_propio.http` |
| C-10 | `test_alta_como_recepcion_con_el_cuerpo_de_la_consigna`, `test_409_sin_filas`, `test_un_repuesto_valido_y_otro_inexistente_no_deja_nada` | `C-10_alta_de_orden.http` |
| C-11 | `test_c11_sin_stock_409_y_nada_cambia`, `test_c11_falta_en_el_segundo_item_revierte_el_primero` | `C-11_stock_insuficiente.http` |
| C-12 | `test_c12_reponer_y_terminar_descuenta_el_stock`, `test_el_aviso_sale_despues_de_la_respuesta`, `test_sin_aviso_cuando_terminar_falla` | `C-12_reponer_y_terminar.http` |
| C-13 | `test_laura_cancela_su_orden_pendiente` (200), `test_ajena_pendiente_tambien_403`, `test_cancelar_una_terminada_409_sin_linea_nueva`, `test_terminada_ya_no_se_cancela_409` | `C-13_cancelar_orden.http` |
| C-15 | `test_c15_misma_cantidad_de_sentencias_con_2_y_con_4_items`, `test_get_detalle_misma_cantidad_de_sentencias_con_2_y_4_items` | `C-15_detalle_sin_n_mas_1.http` |
| C-17 | `test_listado_filtrado_por_estado`, `test_estado_no_declarado_422`, `test_catalogo_para_admin_y_para_un_cliente`, `test_catalogo_sin_cookie_401` | `C-17_catalogo_y_filtro.http` |

## Las 8 rutas (códigos de la consigna)

| Ruta | Códigos | Verificado en |
|---|---|---|
| `POST /ordenes` | 201, 409, 422 (+401/403) | `test_ordenes_alta` |
| `GET /ordenes` | 200, 422 | `test_ordenes_consultas` (filtro, `size`, página inexistente, estado no declarado) |
| `GET /ordenes/{id}` | 200, 403, 404 | `test_ordenes_consultas` |
| `POST /ordenes/{id}/iniciar` | 200, 404, 409 | `test_ordenes_transiciones` (además 403 sin rol MECANICO, SU-03) |
| `POST /ordenes/{id}/terminar` | 200, 403, 404, 409 | `test_ordenes_transiciones`, `test_ordenes_terminar` |
| `POST /ordenes/{id}/cancelar` | 200, 403, 404, 409 | `test_ordenes_transiciones` |
| `GET /estados-orden` | 200 | `test_ordenes_catalogo` |
| `GET /mis-ordenes` | 200, 422 | `test_ordenes_consultas` |

## Reglas de CLAUDE.md

| Regla | Resultado |
|---|---|
| 6 (unicidad en la base; sin 500) | Cumple: el módulo no tiene unicidad propia; el único `IntegrityError` posible (`ck_repuesto_stock_no_negativo`) se traduce por nombre de restricción a 409 con mensaje propio. Lo del repuesto dado de baja se mira porque no viola ninguna FK. |
| 13 (repositorios) | Cumple: `add`/`update` heredados hacen `flush`, ningún `commit`; precarga declarada dentro de cada método; relaciones `lazy="raise"`; `EstadoOrdenRepository` no hereda de `BaseRepository`. |
| 14 (UoW) | Cumple: el router lo construye (`get_ordenes_uow`), el servicio lo abre con `async with` y no lo construye; RN-10 y RN-13 en un bloque cada una; el stock se escribe solo por `mover_stock`. El `_detalle` posterior es un segundo bloque de solo lectura, ya confirmado el primero. |
| 15 (append-only sin endpoint) | Cumple: no hay rutas sobre `historial_estado_orden`; se escribe en `crear_orden` y `_pasar_a`. |
| 16 (contratos y listados) | Cumple: `extra="forbid"` en toda entrada (`_Entrada`); listados con `Pagina` `{items,total,page,size,pages}`; página inexistente → 422; cero resultados = página vacía; sin `password_hash` en las salidas. |
| 17 (SQL y async) | Cumple: sin `text()` ni concatenación en el módulo (grep); filtros con parámetros ligados; los 8 handlers son `async def`; el aviso usa `asyncio.sleep`. |

## Observaciones (no son brechas)

- El logger `taller.avisos` lleva su propio `StreamHandler` (D11): si CH-09 configura el logging global, el aviso puede verse duplicado.
- Sin ejecutar todavía: los `.http` contra un servidor real con `python seed.py` (C-06, C-10 a C-13, C-15, C-17). Falta capturar la consola de C-15 (`SQL_ECHO=true`) y la del aviso de C-12 para CH-09.
