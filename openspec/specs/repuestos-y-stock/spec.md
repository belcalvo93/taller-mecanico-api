# repuestos-y-stock Specification

## Purpose
Permite consultar el catálogo de repuestos vigentes con búsqueda paginada segura frente a inyección SQL, y permite al administrador crear, editar, dar de baja y reponer repuestos manteniendo en la misma transacción el historial de movimientos de stock (a través de un único punto de escritura) y el historial de cambios de precio.

## Requirements

### Requirement: Listado paginado y búsqueda de repuestos vigentes
`GET /repuestos` SHALL responder 200 con la estructura paginada `{items, total, page, size, pages}` de los repuestos NO dados de baja, ordenados por `id`. Si se envía el parámetro opcional `q`, MUST filtrar por `descripcion` sin distinguir mayúsculas/minúsculas usando parámetros ligados (nunca concatenando SQL, `C-16`). `total` MUST contarse con los mismos filtros que `items`. Si `page` supera `pages` MUST responder 422 (`PaginaInexistente`).

#### Scenario: Listado sin filtro
- **WHEN** un usuario de personal (`ADMIN`, `RECEPCION` o `MECANICO`) pide `GET /repuestos?page=1&size=20` sobre el seed
- **THEN** responde 200 con los 4 repuestos vigentes, `total: 4`, `page: 1`, `size: 20`, `pages: 1`

#### Scenario: Búsqueda por descripción sin distinguir mayúsculas
- **WHEN** se pide `GET /repuestos?q=filtro` o `GET /repuestos?q=FILTRO`
- **THEN** responde 200 con `FIL-001` ("Filtro de aceite") y `total: 1`

#### Scenario: Búsqueda con comillas y caracteres especiales (C-16)
- **WHEN** se pide `GET /repuestos?q=' OR '1'='1`
- **THEN** responde 200 con `items: []`, `total: 0`, `page: 1`, `size: 20`, `pages: 1` (el texto se busca literalmente con parámetros ligados)

#### Scenario: Repuesto dado de baja no aparece en el listado
- **WHEN** un repuesto fue dado de baja lógicamente y se lista `GET /repuestos`
- **THEN** no aparece en `items` ni se cuenta en `total`

#### Scenario: Parámetros de paginación inválidos o página inexistente
- **WHEN** se pide `page=0`, `size=0`, `size=101` o una página mayor a `pages` (por ejemplo `page=2` con 4 repuestos y `size=20`)
- **THEN** responde 422

### Requirement: Detalle de un repuesto vigente
`GET /repuestos/{id}` SHALL responder 200 con el repuesto (`id`, `codigo`, `descripcion`, `precio`, `stock`) si existe y no está dado de baja. Si no existe o fue dado de baja MUST responder 404.

#### Scenario: Repuesto existente
- **WHEN** personal consulta `GET /repuestos/1`
- **THEN** responde 200 con `FIL-001`

#### Scenario: Repuesto inexistente o dado de baja
- **WHEN** se consulta un `id` inexistente o un repuesto dado de baja
- **THEN** responde 404

### Requirement: Alta de repuesto con stock inicial en la misma transacción
`POST /repuestos` SHALL crear un repuesto con `codigo`, `descripcion`, `precio` (> 0) y `stock_inicial` (>= 0) y responder 201 con el repuesto creado. Si `stock_inicial > 0`, MUST registrar el alta de stock y su fila en `movimiento_stock` (`cantidad = stock_inicial`, `motivo = "Stock inicial"`, `orden_id = None`, `usuario_id` del admin autenticado) en la MISMA transacción a través del único punto de escritura de stock (`RN-14`, `DD-14`). Si `stock_inicial == 0`, el repuesto queda con `stock = 0` y MUST NOT insertar fila en `movimiento_stock` (la restricción `ck_movimiento_stock_cantidad_no_cero` prohíbe `cantidad = 0`).

#### Scenario: Alta con stock inicial positivo
- **WHEN** un `ADMIN` crea un repuesto con `stock_inicial: 15`
- **THEN** responde 201 con `stock: 15` y existe un movimiento con `cantidad: 15`, `motivo: "Stock inicial"` y `orden_id: null`

#### Scenario: Alta con stock inicial cero
- **WHEN** un `ADMIN` crea un repuesto con `stock_inicial: 0`
- **THEN** responde 201 con `stock: 0` y no se crea movimiento de stock para ese repuesto

#### Scenario: Validación de contrato en el alta
- **WHEN** `precio <= 0`, `stock_inicial < 0`, falta un campo o se envía un campo no declarado (como `stock` o `borrado_en`)
- **THEN** responde 422 y no se crea ninguna fila

### Requirement: Código de repuesto único entre los vigentes
El `codigo` de un repuesto SHALL ser único entre los repuestos no dados de baja (`RN-01`). La unicidad MUST garantizarla el índice único parcial `uq_repuesto_codigo_vigente`: el servicio no consulta antes y traduce el `IntegrityError` a 409 con mensaje propio y sin texto de la base (`RN-18`).

#### Scenario: Código vigente repetido
- **WHEN** un `ADMIN` intenta crear un repuesto con un `codigo` ya vigente (por ejemplo `FIL-001`)
- **THEN** responde 409 con mensaje propio, sin texto de la base, y no quedan filas nuevas en `repuesto` ni en `movimiento_stock`

#### Scenario: Reuso de código de un repuesto dado de baja
- **WHEN** el repuesto con código `FIL-001` fue dado de baja y un `ADMIN` crea otro con `codigo: "FIL-001"`
- **THEN** responde 201 y el nuevo repuesto queda vigente con su propio `id`

### Requirement: Edición parcial de repuesto e historial de precios en la misma transacción
`PATCH /repuestos/{id}` SHALL permitir a un `ADMIN` actualizar `descripcion` y/o `precio` (> 0) de un repuesto vigente y responder 200 con el repuesto actualizado. El contrato MUST rechazar con 422 cualquier intento de enviar `stock` o `codigo` en el cuerpo (`RN-14`). Si el precio cambia respecto del valor guardado, MUST insertarse en la MISMA transacción una fila en `historial_precio_repuesto` con `precio_anterior`, `precio_nuevo` y `usuario_id` (`RN-13`, `C-18`). Si sólo cambia `descripcion` o el `precio` enviado es igual al actual, MUST NOT insertarse fila en `historial_precio_repuesto`.

#### Scenario: Cambio de precio registra historial (C-18)
- **WHEN** un `ADMIN` envía `PATCH /repuestos/1` con `{"precio": "9500.00"}` (antes `8500.00`)
- **THEN** responde 200 con `precio: "9500.00"` y `GET /repuestos/1/precios` incluye la nueva fila con `precio_anterior: "8500.00"` y `precio_nuevo: "9500.00"`

#### Scenario: Cambio sólo de descripción no toca el historial de precios
- **WHEN** un `ADMIN` envía `PATCH /repuestos/1` con `{"descripcion": "Filtro de aceite sintético"}`
- **THEN** responde 200 con la nueva descripción y la cantidad de filas en `historial_precio_repuesto` no cambia

#### Scenario: Mismo precio no genera fila duplicada en el historial
- **WHEN** un `ADMIN` envía `PATCH /repuestos/1` con el mismo precio que ya tenía (`8500.00`)
- **THEN** responde 200 y no se inserta fila en `historial_precio_repuesto`

#### Scenario: Intento de modificar stock o código por PATCH
- **WHEN** el cuerpo de `PATCH /repuestos/{id}` incluye `stock` o `codigo`, o `precio <= 0`
- **THEN** responde 422

#### Scenario: Edición de repuesto inexistente o dado de baja
- **WHEN** se envía `PATCH /repuestos/{id}` para un repuesto que no existe o fue dado de baja
- **THEN** responde 404

### Requirement: Punto único de escritura de stock y reposición
Toda modificación de `repuesto.stock` SHALL pasar por un único método de repositorio (`RepuestoRepository.mover_stock`) que actualice `repuesto.stock` e inserte la fila correspondiente en `movimiento_stock` dentro de la misma transacción (`RN-14`, `DD-14`). `mover_stock` MUST NOT hacer `commit()` ni abrir el Unit of Work: confirma o revierte quien lo llama, para que un descuento de varios ítems sea todo o nada. Si `repuesto.stock + cantidad < 0`, MUST lanzar `StockInsuficiente` sin modificar nada; si `cantidad == 0`, MUST lanzar `ValueError`. `POST /repuestos/{id}/reponer` SHALL permitir a un `ADMIN` sumar `cantidad` (> 0) al stock de un repuesto vigente con un `motivo` (por defecto `"Reposición"`) usando ese punto único y responder 200 con el repuesto actualizado.

#### Scenario: Reposición válida
- **WHEN** un `ADMIN` envía `POST /repuestos/3/reponer` con `{"cantidad": 5, "motivo": "Compra a proveedor"}` (o sólo `{"cantidad": 5}`)
- **THEN** responde 200 con `stock: 7` (antes 2) y se agrega un movimiento con `cantidad: 5` y `orden_id: null`

#### Scenario: Reposición con cantidad inválida
- **WHEN** se envía `cantidad: 0` o `cantidad: -3` en `POST /repuestos/{id}/reponer`
- **THEN** responde 422 y el stock ni los movimientos cambian

#### Scenario: Reposición de repuesto inexistente o dado de baja
- **WHEN** se intenta reponer un repuesto que no existe o fue dado de baja
- **THEN** responde 404

#### Scenario: Movimiento fuera de una transacción propia
- **WHEN** `mover_stock` se llama dentro de un `async with uow` y el bloque termina con una excepción posterior
- **THEN** el stock y el movimiento se revierten junto con el resto del bloque, porque `mover_stock` no confirmó

#### Scenario: Descuento con stock insuficiente en el punto único
- **WHEN** se invoca `mover_stock` con `cantidad: -5` sobre un repuesto con `stock: 2`
- **THEN** lanza `StockInsuficiente` y ni `repuesto.stock` ni `movimiento_stock` se modifican

### Requirement: Baja lógica de repuesto
`DELETE /repuestos/{id}` SHALL marcar `borrado_en` en el repuesto vigente y responder 204 sin cuerpo. La fila, sus movimientos, su historial de precios y los ítems de órdenes que lo referencian se conservan (`RN-16`, `DD-14`). A diferencia de vehículos, dar de baja un repuesto que figura en una orden abierta MUST responder 204 (no 409, `DD-14` / `C-15`). Si el repuesto no existe o ya estaba dado de baja MUST responder 404.

#### Scenario: Baja lógica de repuesto (incluso en orden abierta)
- **WHEN** un `ADMIN` envía `DELETE /repuestos/3` (usado en la orden 2 `EN_REPARACION`)
- **THEN** responde 204, `borrado_en` queda cargado, y el repuesto deja de aparecer en `GET /repuestos` y `GET /repuestos/3` da 404

#### Scenario: Baja de repuesto inexistente o ya dado de baja
- **WHEN** un `ADMIN` envía `DELETE /repuestos/999` o repite `DELETE /repuestos/3`
- **THEN** responde 404

### Requirement: Consulta de movimientos de stock e historial de precios
`GET /repuestos/{id}/movimientos` y `GET /repuestos/{id}/precios` SHALL responder 200 con la lista de movimientos o cambios de precio del repuesto vigente ordenados por `id` ascendente. Si el repuesto no existe o fue dado de baja MUST responder 404.

#### Scenario: Historial de movimientos de un repuesto del seed
- **WHEN** un `ADMIN` pide `GET /repuestos/1/movimientos`
- **THEN** responde 200 con la lista que incluye el movimiento inicial (`cantidad: 10`, `motivo: "Stock inicial"`)

#### Scenario: Historial de precios de un repuesto del seed
- **WHEN** un `ADMIN` pide `GET /repuestos/1/precios`
- **THEN** responde 200 con el cambio del seed (`8000.00` → `8500.00`) y los cambios posteriores en orden cronológico (`id` ascendente)

### Requirement: Permisos de las rutas de repuestos
`GET /repuestos` y `GET /repuestos/{id}` SHALL exigir un rol vigente `ADMIN`, `RECEPCION` o `MECANICO` (un `CLIENTE` recibe 403). `POST /repuestos`, `PATCH /repuestos/{id}`, `DELETE /repuestos/{id}`, `POST /repuestos/{id}/reponer`, `GET /repuestos/{id}/movimientos` y `GET /repuestos/{id}/precios` SHALL exigir el rol vigente `ADMIN` (`RECEPCION`, `MECANICO` y `CLIENTE` reciben 403, `C-18`). Sin sesión todas las rutas MUST responder 401. Las ocho rutas MUST estar en el grupo protegido de `main.py`.

#### Scenario: Sin sesión
- **WHEN** se llama a cualquiera de las ocho rutas sin cookie `access_token`
- **THEN** responde 401

#### Scenario: Recepción y mecánico pueden consultar catálogo pero no administrar ni ver historiales (C-18)
- **WHEN** `RECEPCION` o `MECANICO` llama a `GET /repuestos` o `GET /repuestos/1`
- **THEN** responde 200; pero si llama a `POST /repuestos`, `PATCH /repuestos/1`, `DELETE /repuestos/1`, `POST /repuestos/1/reponer`, `GET /repuestos/1/movimientos` o `GET /repuestos/1/precios`, responde 403

#### Scenario: Cliente no puede acceder al catálogo de repuestos
- **WHEN** un usuario con rol `CLIENTE` llama a `GET /repuestos` o `GET /repuestos/1`
- **THEN** responde 403
