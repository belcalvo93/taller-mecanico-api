# Spec Delta

## Purpose

Permite que el personal consulte y filtre las órdenes de trabajo y que cada cliente vea sólo las órdenes de sus vehículos, con un detalle que se resuelve con un número fijo de consultas y con la separación entre "no autenticado" (401) y "sin permiso" (403).

## ADDED Requirements

### Requirement: Detalle de una orden
`GET /ordenes/{id}` SHALL responder 200 con `id`, `estado`, `patente`, `cliente` (nombre), `total`, `creada_en`, `mecanico_id`, `falla`, `items` (`repuesto_id`, `codigo`, `descripcion`, `cantidad`, `precio_unitario`, `subtotal`) e `historial` (`desde_estado`, `hasta_estado`, `usuario_id`, `cuando`) en orden cronológico. Los importes MUST viajar como texto decimal con dos decimales. Orden inexistente → 404.

#### Scenario: Detalle de la orden 2
- **WHEN** el personal pide la orden 2 del seed
- **THEN** responde 200 con `patente` AD789GH, `cliente` "Jorge Gómez", un ítem BUJ-100 por 4, y un historial de dos líneas (null → PENDIENTE, PENDIENTE → EN_REPARACION)

#### Scenario: Repuesto dado de baja en el detalle
- **WHEN** el repuesto de un ítem fue dado de baja
- **THEN** el detalle sigue mostrando su `codigo` y `descripcion`

#### Scenario: Orden inexistente
- **WHEN** se pide una orden que no existe
- **THEN** responde 404

### Requirement: Detalle con un número fijo de consultas
El detalle de una orden, con su vehículo, el cliente, los ítems, el repuesto de cada ítem y el historial, SHALL resolverse con un número de consultas a la base que no depende de la cantidad de ítems ni de líneas de historial, y MUST NOT depender de la carga perezosa.

#### Scenario: Dos ítems contra cuatro (C-15)
- **WHEN** se pide el detalle de una orden con 2 ítems y el de otra con 4 ítems, contando las sentencias que llegan a la base
- **THEN** las dos peticiones ejecutan la misma cantidad de consultas

### Requirement: Quién ve el detalle
El detalle SHALL verse por cualquier usuario con rol vigente RECEPCION, ADMIN o MECANICO, o por el dueño del vehículo de la orden (RN-17). Cualquier otro usuario autenticado MUST recibir 403.

#### Scenario: El cliente ve su orden (C-06)
- **WHEN** Laura pide la orden 1, de su vehículo
- **THEN** responde 200

#### Scenario: El cliente no ve la ajena (C-06)
- **WHEN** Laura pide la orden 2, del vehículo de Jorge
- **THEN** responde 403

#### Scenario: El personal ve cualquiera
- **WHEN** la recepción, un mecánico o un ADMIN piden la orden 2
- **THEN** responde 200

### Requirement: Listado de órdenes del personal
`GET /ordenes` SHALL responder con el envoltorio `{items, total, page, size, pages}` de las órdenes ordenadas por `id`, cada una con `id`, `estado`, `patente`, `cliente`, `total`, `creada_en`, `mecanico_id` y `falla`. Con `estado`, MUST filtrar por ese estado y contar el total con el mismo filtro. Sólo RECEPCION, ADMIN y MECANICO; los demás reciben 403.

#### Scenario: Filtro por estado
- **WHEN** el personal pide `GET /ordenes?estado=PENDIENTE` con el seed
- **THEN** responde 200 con sólo la orden 1, `total` 1 y `pages` 1

#### Scenario: Sin filtro
- **WHEN** el personal pide `GET /ordenes?size=1`
- **THEN** responde 200 con una orden, `total` 2 y `pages` 2

#### Scenario: Estado sin órdenes
- **WHEN** se filtra por TERMINADA sin órdenes terminadas
- **THEN** responde 200 con `items` vacío, `total` 0 y `pages` 1

#### Scenario: Página inexistente o tamaño inválido
- **WHEN** se pide `page=3` habiendo 2 páginas, o `size=500`, o `page=0`
- **THEN** responde 422 con mensaje propio

#### Scenario: Un cliente no lista
- **WHEN** Laura pide `GET /ordenes`
- **THEN** responde 403

### Requirement: Órdenes propias
`GET /mis-ordenes` SHALL responder con el envoltorio paginado de las órdenes de los vehículos del cliente vinculado al usuario autenticado, con el mismo formato que el listado del personal, y nunca MUST incluir órdenes de vehículos de otros clientes. Sólo pide estar autenticado (RN-17). Un usuario sin ficha de cliente recibe una página vacía.

#### Scenario: Laura ve sólo las suyas (C-06)
- **WHEN** Laura pide `GET /mis-ordenes`
- **THEN** responde 200 con la orden 1 y sin la orden 2, aunque no tenga ningún rol de personal

#### Scenario: Personal sin ficha de cliente
- **WHEN** la recepción pide `GET /mis-ordenes`
- **THEN** responde 200 con `items` vacío, `total` 0 y `pages` 1

#### Scenario: Paginación inválida
- **WHEN** Laura pide `GET /mis-ordenes?page=2` teniendo una sola página
- **THEN** responde 422

### Requirement: 401 contra 403 en las rutas de órdenes
Toda ruta de órdenes y del catálogo SHALL responder 401 sin una sesión válida, antes de cualquier decisión de permiso o de estado. Con sesión válida y sin el rol que la ruta exige MUST responder 403. Lo propio (`/mis-ordenes`, `/auth/yo`) MUST responder 200 a un usuario sin rol de personal.

#### Scenario: Sin cookie (C-06)
- **WHEN** se pide cualquiera de las ocho rutas de órdenes y catálogo sin la cookie de sesión
- **THEN** cada una responde 401

#### Scenario: Con sesión pero sin rol (C-06)
- **WHEN** Laura (sólo CLIENTE) pide `GET /ordenes` o `POST /ordenes`
- **THEN** responde 403

#### Scenario: Lo propio sin rol (C-06)
- **WHEN** Laura pide `GET /mis-ordenes` y `GET /auth/yo`
- **THEN** las dos responden 200

#### Scenario: Cambio de contraseña pendiente
- **WHEN** `nuevo@example.com`, con el cambio obligatorio pendiente, pide `GET /ordenes`
- **THEN** responde 403
