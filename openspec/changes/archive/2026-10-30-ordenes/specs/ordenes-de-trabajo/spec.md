# Spec Delta

## Purpose

Permite abrir una orden de trabajo con los repuestos que lleva y moverla por su ciclo de vida (iniciar, terminar, cancelar), con reglas de permiso y de estado, el descuento de stock al terminar y un historial de estados que sólo crece.

## ADDED Requirements

### Requirement: Contrato de alta de una orden
`POST /ordenes` SHALL aceptar sólo `vehiculo_id`, `falla` e `items` (cada ítem con `repuesto_id` y `cantidad`). El contrato MUST rechazar con 422: campos no declarados (precio, total, estado, fecha u otros), `items` vacío, repuestos repetidos, cantidad no positiva y `falla` vacía. Ningún valor del cuerpo MUST terminar en 500.

#### Scenario: El cuerpo trae precio o total
- **WHEN** un ítem trae `precio_unitario` o el cuerpo trae `total`, `estado` o `creada_en`
- **THEN** responde 422 y no se crea ninguna orden

#### Scenario: Sin ítems
- **WHEN** `items` es una lista vacía
- **THEN** responde 422

#### Scenario: Repuesto repetido
- **WHEN** dos ítems tienen el mismo `repuesto_id`
- **THEN** responde 422 y no se crea ninguna orden

#### Scenario: Cantidad inválida o fuera de rango
- **WHEN** un ítem tiene `cantidad` 0, negativa o mayor que el máximo del contrato, o un id fuera del rango de un entero de la base
- **THEN** responde 422

### Requirement: Alta de una orden con precios copiados y total del servidor
Una orden válida SHALL nacer PENDIENTE, sin mecánico, con el precio de cada ítem copiado del precio vigente del repuesto y el total calculado por el servidor como la suma de `cantidad × precio_unitario` en decimal exacto (RN-10). Responde 201 con el detalle de la orden, incluida la primera línea de historial (desde nulo hasta PENDIENTE, con el usuario que la creó).

#### Scenario: Alta con dos ítems (C-10)
- **WHEN** la recepción crea una orden para el vehículo 2 con 1 pastilla de freno (32000.00) y 3 litros de aceite (12000.00)
- **THEN** responde 201 con `estado` PENDIENTE, `patente` AC456EF, `cliente` "Laura Cliente", `mecanico_id` nulo, `total` "68000.00", subtotales "32000.00" y "36000.00", y un historial de una línea (null → PENDIENTE) con el `usuario_id` de la recepción

#### Scenario: El precio queda fijo en la orden
- **WHEN** después de crear la orden cambia el precio del repuesto
- **THEN** el `precio_unitario` y el `total` de la orden no cambian

#### Scenario: Lo crea un ADMIN
- **WHEN** un ADMIN crea una orden válida
- **THEN** responde 201 y el historial lleva el id del ADMIN

### Requirement: Alta de una orden en un solo bloque
La orden, sus ítems y la primera línea de historial SHALL escribirse en una sola transacción. Si el vehículo no existe o está dado de baja, o algún repuesto no existe o está dado de baja (RN-16), MUST responder 409 con mensaje propio y no MUST quedar ninguna fila de la orden, de sus ítems ni de su historial.

#### Scenario: Repuesto inexistente (C-10)
- **WHEN** uno de los ítems pide un `repuesto_id` que no existe
- **THEN** responde 409 con mensaje propio, sin texto de la base, y la cantidad de órdenes, ítems y líneas de historial no cambia

#### Scenario: Repuesto dado de baja
- **WHEN** uno de los ítems pide un repuesto dado de baja
- **THEN** responde 409 y no se crea la orden

#### Scenario: Vehículo dado de baja o inexistente
- **WHEN** `vehiculo_id` es un vehículo dado de baja o que no existe
- **THEN** responde 409 y no se crea la orden

#### Scenario: Total que no entra en la columna
- **WHEN** los precios vigentes y las cantidades dan un total mayor que el máximo de `NUMERIC(12,2)`
- **THEN** responde 409 con mensaje propio, no 500, y no se crea la orden

### Requirement: Alta con el catálogo vacío
Si el catálogo de estados no tiene el estado PENDIENTE, crear una orden MUST responder 409 con un mensaje propio que lo explique (RN-19), sin crear ninguna fila y sin 500.

#### Scenario: Catálogo vacío
- **WHEN** se crea una orden válida con la tabla `estado_orden` vacía
- **THEN** responde 409 con un mensaje propio sobre el catálogo de estados y no se crea ninguna orden

### Requirement: Permiso para crear una orden
Crear una orden SHALL estar permitido sólo a usuarios con rol vigente RECEPCION o ADMIN; cualquier otro usuario autenticado MUST recibir 403.

#### Scenario: Mecánico o cliente intentan crear
- **WHEN** un MECANICO o un CLIENTE envía un alta válida
- **THEN** responde 403 y no se crea ninguna orden

### Requirement: Iniciar una orden
`POST /ordenes/{id}/iniciar` SHALL pasar una orden PENDIENTE a EN_REPARACION, asignar como `mecanico_id` al usuario que la inicia, agregar una línea de historial (PENDIENTE → EN_REPARACION) y responder 200 con el detalle. Sólo un usuario con rol vigente MECANICO MUST poder iniciar (SU-03): un ADMIN sin ese rol recibe 403. Orden inexistente → 404; en otro estado → 409.

#### Scenario: El mecánico inicia una pendiente
- **WHEN** `mecanico2@example.com` inicia la orden 1 (PENDIENTE)
- **THEN** responde 200 con `estado` EN_REPARACION, `mecanico_id` igual a su id y una línea nueva de historial PENDIENTE → EN_REPARACION

#### Scenario: Orden que no está pendiente
- **WHEN** un mecánico inicia la orden 2 (EN_REPARACION)
- **THEN** responde 409 y la orden y su historial no cambian

#### Scenario: Un ADMIN no inicia
- **WHEN** un ADMIN sin rol MECANICO inicia la orden 1
- **THEN** responde 403 y la orden sigue PENDIENTE

#### Scenario: Orden inexistente
- **WHEN** un mecánico inicia una orden que no existe
- **THEN** responde 404

### Requirement: Permiso para terminar antes que el estado
`POST /ordenes/{id}/terminar` SHALL estar permitido sólo al mecánico asignado a la orden (con rol MECANICO vigente) o a un usuario con rol ADMIN vigente. El permiso MUST evaluarse antes que el estado: quien no tiene permiso recibe 403 aunque la orden no esté EN_REPARACION. Orden inexistente → 404; con permiso pero en un estado distinto de EN_REPARACION → 409.

#### Scenario: Mecánico no asignado
- **WHEN** `mecanico2@example.com` termina la orden 2, asignada a `mecanico@example.com`
- **THEN** responde 403 y nada cambia

#### Scenario: Recepción o cliente
- **WHEN** la recepción o el cliente terminan una orden
- **THEN** responde 403

#### Scenario: 403 antes que 409
- **WHEN** un mecánico no asignado termina la orden 1 (PENDIENTE, sin mecánico)
- **THEN** responde 403, no 409

#### Scenario: Estado que no permite terminar
- **WHEN** un ADMIN termina la orden 1 (PENDIENTE)
- **THEN** responde 409 y nada cambia

#### Scenario: Orden inexistente
- **WHEN** un ADMIN termina una orden que no existe
- **THEN** responde 404

### Requirement: Terminar una orden descuenta stock en un solo bloque
Terminar una orden EN_REPARACION SHALL, en una sola transacción (RN-13): descontar del stock de cada repuesto la cantidad de su ítem por el punto único de escritura de stock (RN-14), dejar un movimiento de stock negativo por cada ítem vinculado a la orden, pasar la orden a TERMINADA y agregar una línea de historial (EN_REPARACION → TERMINADA). Responde 200 con el detalle.

#### Scenario: Reponer y terminar la orden 2 (C-12)
- **WHEN** se reponen bujías hasta tener al menos 4 y el mecánico asignado termina la orden 2
- **THEN** responde 200 con `estado` TERMINADA; el stock de bujías baja en 4; aparece un movimiento de −4 con la orden 2; y el historial suma la línea EN_REPARACION → TERMINADA

#### Scenario: Lo termina un ADMIN
- **WHEN** un ADMIN termina una orden EN_REPARACION con stock suficiente
- **THEN** responde 200 y la línea de historial lleva el id del ADMIN

#### Scenario: Un movimiento por ítem
- **WHEN** se termina una orden con dos ítems y stock suficiente
- **THEN** quedan exactamente dos movimientos nuevos, uno por repuesto, con la cantidad negativa de cada ítem

### Requirement: Stock insuficiente revierte todo
Si algún repuesto no alcanza para su ítem, terminar MUST responder 409 con mensaje propio y no MUST quedar ninguna escritura de la operación: el estado, el stock, los movimientos y el historial quedan exactamente como estaban.

#### Scenario: La orden 2 pide más bujías que las que hay (C-11)
- **WHEN** el mecánico asignado termina la orden 2 (4 bujías con 2 en stock)
- **THEN** responde 409; la orden sigue EN_REPARACION; el stock de bujías sigue en 2; la cantidad de movimientos y de líneas de historial no cambia

### Requirement: Terminar con un repuesto dado de baja
Terminar una orden SHALL funcionar aunque alguno de sus repuestos haya sido dado de baja después de crearla (DD-14): la baja lógica no impide descontar su stock.

#### Scenario: Repuesto dado de baja después del alta
- **WHEN** el repuesto de un ítem se da de baja y luego se termina la orden con stock suficiente
- **THEN** responde 200, la orden queda TERMINADA y el stock de ese repuesto baja

### Requirement: Aviso al cliente después de terminar
Al terminar una orden con éxito, el sistema SHALL agendar un aviso simulado al cliente (espera de 0,5 s sin bloquear y un mensaje en el registro con la orden) que corre después de enviar la respuesta. Si la operación no se confirmó (403, 404 o 409), el aviso MUST NOT ejecutarse.

#### Scenario: El aviso sale después de la respuesta (C-12)
- **WHEN** se termina una orden con éxito
- **THEN** el mensaje del aviso aparece en el registro después de que se envió el cuerpo de la respuesta

#### Scenario: Sin aviso si no se confirmó (C-11)
- **WHEN** terminar responde 409 por stock insuficiente
- **THEN** no aparece ningún mensaje de aviso en el registro

### Requirement: Cancelar una orden con permiso antes que el estado
`POST /ordenes/{id}/cancelar` SHALL permitir cancelar a un usuario con rol vigente RECEPCION o ADMIN, o al dueño del vehículo de la orden (RN-12, RN-17). La ruta no exige rol: el permiso MUST decidirse antes que el estado. Sin permiso → 403; con permiso, sólo PENDIENTE → CANCELADA, otro estado → 409. Orden inexistente → 404.

#### Scenario: El dueño cancela su orden pendiente (C-13)
- **WHEN** Laura (sólo rol CLIENTE) cancela la orden 1, de su vehículo, PENDIENTE
- **THEN** responde 200 con `estado` CANCELADA y una línea de historial PENDIENTE → CANCELADA con su id

#### Scenario: Orden ajena (C-13)
- **WHEN** Laura cancela una orden del vehículo de Jorge
- **THEN** responde 403 y la orden no cambia

#### Scenario: Orden terminada (C-13)
- **WHEN** la recepción cancela una orden TERMINADA
- **THEN** responde 409 y la orden no cambia

#### Scenario: 403 antes que 409
- **WHEN** Laura cancela una orden ajena que además está EN_REPARACION
- **THEN** responde 403, no 409

#### Scenario: Recepción o ADMIN cancelan
- **WHEN** la recepción o un ADMIN cancelan una orden PENDIENTE de cualquier cliente
- **THEN** responde 200 con `estado` CANCELADA

#### Scenario: Mecánico sin relación con la orden
- **WHEN** un mecánico cancela una orden PENDIENTE
- **THEN** responde 403

### Requirement: Historial de estados sólo agregado
Cada transición (alta, iniciar, terminar, cancelar) SHALL agregar exactamente una línea de historial con el estado anterior, el nuevo, el usuario que la hizo y el instante con zona horaria. Las líneas existentes MUST NOT modificarse ni borrarse (RN-15); una operación rechazada no agrega ninguna línea.

#### Scenario: Ciclo completo
- **WHEN** una orden se crea, se inicia y se termina
- **THEN** su historial tiene tres líneas en orden: null → PENDIENTE, PENDIENTE → EN_REPARACION, EN_REPARACION → TERMINADA

#### Scenario: Transición rechazada
- **WHEN** una transición responde 403, 404 o 409
- **THEN** la cantidad de líneas de historial no cambia

### Requirement: Identificadores de ruta válidos
Las rutas `/ordenes/{id}` y sus acciones SHALL rechazar con 422 un `id` no entero o fuera del rango de un entero de la base, sin ejecutar la operación (C-01).

#### Scenario: Id no entero (C-01)
- **WHEN** con sesión iniciada se pide `POST /ordenes/abc/cancelar` o `GET /ordenes/abc`
- **THEN** responde 422 y no se ejecuta la operación

#### Scenario: Id fuera de rango
- **WHEN** se pide `GET /ordenes/3000000000`
- **THEN** responde 422, no 500
