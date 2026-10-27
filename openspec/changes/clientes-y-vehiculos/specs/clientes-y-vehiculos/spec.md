# Spec Delta

## Purpose

Permite que la recepción y el administrador registren clientes y sus vehículos, consulten un cliente con sus vehículos vigentes y den de baja un vehículo vendido sin perder su historia, de modo que el comprador pueda registrarlo con la misma patente; y que cualquier usuario autenticado vea sólo sus propios vehículos.

## ADDED Requirements

### Requirement: Alta de cliente
`POST /clientes` SHALL crear un cliente con `nombre`, `documento` y `telefono` y responder 201 con el cliente creado (`id`, `usuario_id`, `nombre`, `documento`, `telefono`). El contrato MUST rechazar con 422 cualquier campo no declarado (incluido `usuario_id`), los campos faltantes o vacíos y los que superan su largo máximo. El documento se guarda sin espacios al principio ni al final.

#### Scenario: Alta correcta
- **WHEN** la recepción envía un cliente nuevo válido
- **THEN** responde 201 con el cliente, `usuario_id` nulo y un `id` nuevo

#### Scenario: Campo no declarado
- **WHEN** el cuerpo trae `usuario_id` u otro campo que el contrato no declara
- **THEN** responde 422 y no se crea ninguna fila

#### Scenario: Campo vacío o faltante
- **WHEN** el cuerpo no trae `documento` o lo trae vacío o sólo con espacios
- **THEN** responde 422

### Requirement: Documento único garantizado por la base
El documento de un cliente SHALL ser único (RN-01). La unicidad MUST garantizarla la base: el servicio no consulta antes, y traduce el `IntegrityError` de `uq_cliente_documento` a 409 con un mensaje propio. La respuesta MUST NOT contener texto de la base (RN-18).

#### Scenario: Documento repetido
- **WHEN** se da de alta un cliente con el documento de otro que ya existe (también si llega con espacios alrededor)
- **THEN** responde 409 con un mensaje propio, sin texto de la base, y la cantidad de clientes no cambia

### Requirement: Consulta de un cliente con sus vehículos vigentes
`GET /clientes/{id}` SHALL responder 200 con el cliente y la lista `vehiculos` de sus vehículos NO dados de baja, ordenados por `id`. Los vehículos MUST obtenerse con carga anticipada declarada en el método del repositorio (sin carga perezosa). Un cliente inexistente MUST responder 404.

#### Scenario: Cliente con vehículos
- **WHEN** se pide el cliente 1 del seed
- **THEN** responde 200 con sus dos vehículos (`AB123CD` y `AC456EF`)

#### Scenario: Vehículo dado de baja no aparece
- **WHEN** uno de sus vehículos fue dado de baja y se pide el cliente
- **THEN** la lista `vehiculos` no lo incluye

#### Scenario: Cliente inexistente
- **WHEN** se pide un cliente que no existe
- **THEN** responde 404

### Requirement: Alta de vehículo de un cliente
`POST /clientes/{id}/vehiculos` SHALL crear un vehículo del cliente de la ruta con `patente`, `marca`, `modelo` y `anio`, y responder 201 con `id`, `cliente_id`, `patente`, `marca`, `modelo` y `anio`. La patente se guarda en mayúsculas y sin espacios. El contrato MUST rechazar con 422 los campos no declarados y un `anio` fuera de 1950..2100. Si el cliente no existe MUST responder 404, aunque la patente esté repetida.

#### Scenario: Alta correcta
- **WHEN** la recepción registra un vehículo válido para un cliente existente
- **THEN** responde 201 con el vehículo y `cliente_id` igual al de la ruta

#### Scenario: Patente normalizada
- **WHEN** la patente llega como ` ab 123 zz `
- **THEN** se guarda y se devuelve `AB123ZZ`

#### Scenario: Año fuera de rango
- **WHEN** `anio` es 1949 o 2101
- **THEN** responde 422 y no se crea el vehículo

#### Scenario: Año en el borde
- **WHEN** `anio` es 1950 o 2100
- **THEN** responde 201

#### Scenario: Cliente inexistente
- **WHEN** el cliente de la ruta no existe
- **THEN** responde 404

### Requirement: Patente única entre los vehículos vigentes
La patente SHALL ser única sólo entre los vehículos no dados de baja (RN-01). La unicidad MUST garantizarla el índice único parcial `uq_vehiculo_patente_vigente`: el servicio no consulta antes y traduce su `IntegrityError` a 409 con mensaje propio.

#### Scenario: Patente vigente repetida
- **WHEN** se registra una patente que ya tiene un vehículo vigente (de cualquier cliente)
- **THEN** responde 409 con mensaje propio y no se crea el vehículo

#### Scenario: Patente de un vehículo dado de baja
- **WHEN** el vehículo con esa patente fue dado de baja y se la registra para otro cliente
- **THEN** responde 201

### Requirement: Baja lógica de vehículo
`DELETE /vehiculos/{id}` SHALL dar de baja el vehículo escribiendo `borrado_en` (la fila y sus órdenes se conservan) y responder 204 sin cuerpo. Un vehículo inexistente o ya dado de baja MUST responder 404. Un vehículo con al menos una orden abierta —en un estado cuyo `es_final` es falso en el catálogo `estado_orden`— MUST responder 409 y no se da de baja (RN-16).

#### Scenario: Baja sin órdenes
- **WHEN** se da de baja un vehículo sin órdenes
- **THEN** responde 204, la fila sigue en la tabla con `borrado_en` cargado y el vehículo deja de aparecer en `GET /clientes/{id}`

#### Scenario: Baja con órdenes sólo finales
- **WHEN** todas las órdenes del vehículo están en estados finales (TERMINADA o CANCELADA)
- **THEN** responde 204

#### Scenario: Baja con una orden abierta
- **WHEN** el vehículo tiene una orden PENDIENTE o EN_REPARACION
- **THEN** responde 409 con mensaje propio y `borrado_en` sigue nulo

#### Scenario: Vehículo inexistente o ya dado de baja
- **WHEN** se da de baja un vehículo que no existe, o uno que ya fue dado de baja
- **THEN** responde 404

### Requirement: Mis vehículos
`GET /mis-vehiculos` SHALL responder 200 con la lista de vehículos vigentes del cliente vinculado al usuario autenticado, ordenados por `id`, y ninguno ajeno (RN-17). Sólo MUST exigir estar autenticado (ningún rol). Un usuario sin ficha de cliente recibe una lista vacía.

#### Scenario: Cliente con vehículos
- **WHEN** Laura (`cliente@example.com`) pide sus vehículos
- **THEN** recibe `AB123CD` y `AC456EF`, y no `AD789GH` (de Jorge)

#### Scenario: Usuario sin ficha de cliente
- **WHEN** un usuario de personal sin ficha de cliente pide sus vehículos
- **THEN** responde 200 con una lista vacía

#### Scenario: Vehículo propio dado de baja
- **WHEN** uno de los vehículos del cliente fue dado de baja
- **THEN** no aparece en la lista

### Requirement: Permisos de las rutas de clientes y vehículos
`POST /clientes`, `GET /clientes/{id}`, `POST /clientes/{id}/vehiculos` y `DELETE /vehiculos/{id}` SHALL exigir un rol vigente RECEPCION o ADMIN (`requiere_rol`), y `GET /mis-vehiculos` sólo una sesión (`get_usuario_actual`). Sin sesión MUST responder 401; con sesión y sin el rol, 403. Las cinco rutas MUST estar en el grupo protegido de `main.py`.

#### Scenario: Sin sesión
- **WHEN** se llama a cualquiera de las cinco rutas sin cookie
- **THEN** responde 401

#### Scenario: Sin el rol
- **WHEN** un MECANICO o un CLIENTE llama a una ruta de personal
- **THEN** responde 403

#### Scenario: Con el rol
- **WHEN** un ADMIN o una RECEPCION llama a una ruta de personal
- **THEN** la petición se atiende

### Requirement: Entradas inválidas nunca terminan en 500
Los parámetros de ruta `{id}` SHALL ser enteros entre 1 y 2147483647 (el rango de la columna); fuera de eso, o no enteros, MUST responder 422 sin ejecutar el handler (C-01). Ningún texto con el carácter NUL (que PostgreSQL rechaza) MUST llegar a la base: el contrato responde 422 (RN-18).

#### Scenario: Id no entero
- **WHEN** con sesión iniciada se pide `GET /clientes/abc` o `DELETE /vehiculos/1.5`
- **THEN** responde 422 y el servicio no se ejecuta

#### Scenario: Id fuera del rango de la columna
- **WHEN** se pide `GET /clientes/3000000000`
- **THEN** responde 422 (no 500)

#### Scenario: Texto con NUL
- **WHEN** el nombre de un cliente trae `\u0000`
- **THEN** responde 422 (no 500)
