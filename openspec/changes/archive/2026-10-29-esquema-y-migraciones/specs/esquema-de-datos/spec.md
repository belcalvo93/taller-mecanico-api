# Spec Delta

## Purpose

Define las 13 tablas del taller (nombres, columnas, tipos, nulos, restricciones e índices) y la navegación entre modelos, de modo que la base garantice la unicidad, las claves foráneas y las comprobaciones que piden la consigna y sus casos de prueba.

## ADDED Requirements

### Requirement: Tablas y columnas con los nombres de la consigna
Después de migrar, la base SHALL tener exactamente las 13 tablas de la consigna (`usuario`, `asignacion_rol`, `intento_acceso`, `evento_seguridad`, `cliente`, `vehiculo`, `repuesto`, `estado_orden`, `orden_trabajo`, `item_orden`, `historial_estado_orden`, `movimiento_stock`, `historial_precio_repuesto`), cada una con todas las columnas que lista la consigna y con esos mismos nombres. `usuario` MUST NOT tener columna `rol`.

#### Scenario: Las 13 tablas existen
- **WHEN** se listan las tablas del esquema público de una base migrada (sin contar `alembic_version`)
- **THEN** son exactamente las 13 de la consigna

#### Scenario: Columnas exactas por tabla
- **WHEN** se listan las columnas de cada tabla
- **THEN** cada tabla contiene todas las columnas que fija la consigna para ella, con el nombre idéntico

#### Scenario: Usuario sin columna de rol
- **WHEN** se listan las columnas de `usuario`
- **THEN** no hay ninguna columna llamada `rol`

### Requirement: Nulos sólo donde la consigna los permite
Las columnas que la consigna marca como "nulo" (`usuario.password_cambiada_en`, `asignacion_rol.vence_en`, `revocada_en` y `otorgada_por`, `cliente.usuario_id`, `vehiculo.borrado_en`, `repuesto.borrado_en`, `orden_trabajo.mecanico_id`, `historial_estado_orden.desde_estado`, `movimiento_stock.orden_id`) SHALL aceptar NULL; todas las demás columnas MUST ser NOT NULL.

#### Scenario: Columnas opcionales
- **WHEN** se consulta la nulabilidad de las columnas opcionales de la consigna
- **THEN** todas aceptan NULL

#### Scenario: Columnas obligatorias
- **WHEN** se inserta una fila con NULL en una columna que la consigna no marca como opcional (por ejemplo `vehiculo.patente` o `orden_trabajo.estado`)
- **THEN** la base rechaza la inserción

### Requirement: Fechas con zona horaria
Toda columna de fecha u hora SHALL ser `timestamp with time zone`, y su valor MUST conservar las fracciones de segundo.

#### Scenario: Tipo de todas las fechas
- **WHEN** se listan las columnas de tipo fecha/hora de las 13 tablas
- **THEN** todas son `timestamp with time zone`

#### Scenario: Fracciones de segundo
- **WHEN** se guarda un instante con microsegundos y se lo vuelve a leer
- **THEN** se obtiene el mismo instante, con zona horaria y con los microsegundos

### Requirement: Dinero en NUMERIC y Decimal
`repuesto.precio`, `item_orden.precio_unitario`, `historial_precio_repuesto.precio_anterior` y `precio_nuevo` SHALL ser `NUMERIC(10,2)`; `orden_trabajo.total` SHALL ser `NUMERIC(12,2)`. En el código esos campos MUST ser `Decimal`, nunca `float`.

#### Scenario: Precisión en la base
- **WHEN** se consulta el tipo de cada columna de dinero
- **THEN** es `numeric` con la precisión y escala indicadas

#### Scenario: Decimal al leer
- **WHEN** se lee de la base un repuesto con precio 8500.00
- **THEN** el valor es un `Decimal` igual a `8500.00`, no un `float`

### Requirement: Unicidad simple
La base SHALL rechazar un `usuario.email` repetido, un `cliente.documento` repetido, dos clientes con el mismo `usuario_id`, dos ítems de la misma orden con el mismo repuesto (`item_orden (orden_id, repuesto_id)`) y dos estados del catálogo con la misma `posicion`. Cada restricción MUST tener un nombre fijo y conocido.

#### Scenario: Correo repetido
- **WHEN** se insertan dos usuarios con el mismo email
- **THEN** la segunda inserción falla por violación de unicidad, identificada por el nombre de la restricción

#### Scenario: Cliente uno a uno con usuario
- **WHEN** se insertan dos clientes con el mismo `usuario_id` no nulo
- **THEN** la segunda inserción falla; dos clientes con `usuario_id` NULL se aceptan

#### Scenario: Repuesto repetido en una orden
- **WHEN** se insertan dos ítems con la misma orden y el mismo repuesto
- **THEN** el segundo falla por unicidad

#### Scenario: Documento y posición repetidos
- **WHEN** se inserta un cliente con un documento existente, o un estado con una posición existente
- **THEN** la inserción falla por unicidad

### Requirement: Unicidad parcial entre los vigentes
La base SHALL tener tres índices únicos parciales: `vehiculo (patente) WHERE borrado_en IS NULL`, `repuesto (codigo) WHERE borrado_en IS NULL` y `asignacion_rol (usuario_id, rol) WHERE revocada_en IS NULL`. Una fila dada de baja o revocada MUST NOT impedir otra fila vigente con el mismo valor.

#### Scenario: Patente vigente repetida
- **WHEN** existen un vehículo vigente con patente `AB123CD` y se inserta otro vigente con la misma patente
- **THEN** la inserción falla por el índice único parcial de patente

#### Scenario: Patente reutilizada tras la baja
- **WHEN** el primer vehículo tiene `borrado_en` con fecha y se inserta otro vigente con la misma patente
- **THEN** la inserción se acepta y ambas filas quedan en la tabla

#### Scenario: Código de repuesto
- **WHEN** se repite el código de un repuesto vigente, y después se lo repite tras dar de baja el original
- **THEN** el primer intento falla y el segundo se acepta

#### Scenario: Una asignación abierta por rol
- **WHEN** un usuario tiene una asignación de `MECANICO` sin `revocada_en` y se inserta otra igual
- **THEN** la inserción falla; si la primera tiene `revocada_en`, la nueva se acepta

#### Scenario: Roles distintos del mismo usuario
- **WHEN** un usuario tiene una asignación abierta de `ADMIN` y se inserta una abierta de `MECANICO`
- **THEN** la inserción se acepta

### Requirement: Comprobaciones de valores
La base SHALL rechazar: un `rol` fuera de `ADMIN`, `RECEPCION`, `MECANICO`, `CLIENTE`; `anio` fuera de 1950..2100; `repuesto.precio <= 0`; `stock < 0`; `total < 0`; `item_orden.cantidad <= 0` o `precio_unitario <= 0`; `movimiento_stock.cantidad = 0`; `precio_nuevo <= 0` o `precio_nuevo = precio_anterior`. Cada CHECK MUST tener nombre fijo.

#### Scenario: Valores fuera de rango
- **WHEN** se inserta cada uno de los valores prohibidos (rol `JEFE`, año 1949 y 2101, precio 0, stock -1, total -0.01, cantidad 0, precio unitario 0, movimiento de cantidad 0, precio nuevo 0, precio nuevo igual al anterior)
- **THEN** cada inserción falla por la comprobación correspondiente, identificada por su nombre

#### Scenario: Valores en el borde
- **WHEN** se insertan año 1950 y 2100, stock 0, total 0, movimientos de cantidad 5 y -3
- **THEN** todas las inserciones se aceptan

### Requirement: Estados como claves foráneas al catálogo
`orden_trabajo.estado`, `historial_estado_orden.desde_estado` y `hasta_estado` SHALL ser claves foráneas a `estado_orden.codigo`, cuya clave primaria es `codigo` (no un `id`). Ningún estado MUST validarse con un CHECK con lista de valores.

#### Scenario: Estado inexistente
- **WHEN** con el catálogo cargado se inserta o actualiza una orden con estado `DEMORADA`
- **THEN** la base la rechaza por la clave foránea

#### Scenario: Catálogo vacío
- **WHEN** el catálogo no tiene filas y se inserta una orden con estado `PENDIENTE`
- **THEN** la base la rechaza por la clave foránea

#### Scenario: Sin CHECK de estados
- **WHEN** se listan las comprobaciones de `orden_trabajo` e `historial_estado_orden`
- **THEN** ninguna menciona valores de estado

### Requirement: Claves foráneas con índice
Cada columna con clave foránea SHALL estar cubierta por un índice cuya primera columna sea esa. Las FK MUST ser: roles, cliente, órdenes como mecánico, historiales, movimientos y precios a `usuario.id`; vehículo a `cliente.id`; orden a `vehiculo.id`; ítem, historial de estados y movimiento a `orden_trabajo.id`; ítem, movimiento y precio a `repuesto.id`.

#### Scenario: Cada FK tiene índice
- **WHEN** se recorren todas las claves foráneas del esquema
- **THEN** para cada una existe un índice cuya primera columna es la columna de la FK

#### Scenario: Referencia inexistente
- **WHEN** se inserta un vehículo con un `cliente_id` que no existe
- **THEN** la base lo rechaza por la clave foránea

### Requirement: Índice de intentos de acceso
`intento_acceso` SHALL tener un índice sobre `(email, ip, cuando)`, en ese orden.

#### Scenario: Índice compuesto
- **WHEN** se listan los índices de `intento_acceso`
- **THEN** hay uno cuyas columnas son `email`, `ip` y `cuando`, en ese orden

### Requirement: Navegación en los dos extremos
Los modelos SHALL declarar la navegación en ambos extremos de cada relación que se lee: usuario–asignaciones, usuario–cliente, cliente–vehículos, vehículo–órdenes, mecánico–órdenes, orden–ítems, ítem–repuesto, orden–historial, repuesto–movimientos y repuesto–historial de precios. `Usuario.cliente` MUST devolver un objeto o nada, nunca una lista.

#### Scenario: Uno a uno usuario–cliente
- **WHEN** se lee un usuario con su cliente precargado
- **THEN** `cliente` es un objeto `Cliente` (o `None` si no tiene) y `cliente.usuario` vuelve al mismo usuario

#### Scenario: Composición orden–ítems
- **WHEN** se lee una orden con sus ítems y el repuesto de cada ítem precargados
- **THEN** `items` es una lista de ítems cuyo `orden` es esa orden y cuyo `repuesto` es el repuesto correspondiente

### Requirement: Carga perezosa prohibida
Acceder a una relación que no fue precargada explícitamente SHALL fallar de inmediato con un error, en lugar de lanzar una consulta implícita.

#### Scenario: Relación sin precargar
- **WHEN** se lee un cliente sin precargar sus vehículos y se accede a `cliente.vehiculos`
- **THEN** se lanza un error que indica que la relación no está cargada, y no se ejecuta ninguna consulta

#### Scenario: Relación precargada
- **WHEN** se lee el mismo cliente precargando sus vehículos
- **THEN** `cliente.vehiculos` devuelve la lista sin error
