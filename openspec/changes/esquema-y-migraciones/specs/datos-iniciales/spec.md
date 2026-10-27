# Spec Delta

## Purpose

Deja la base en un estado inicial conocido y reproducible, con los datos mínimos que fija la consigna y que usan los casos de prueba C-01..C-19, cada vez que se ejecuta `python seed.py`.

## ADDED Requirements

### Requirement: Vaciado y recarga reproducible
`seed.py` SHALL vaciar todas las tablas del esquema y cargar los datos iniciales en una sola transacción: o queda la carga completa o la base queda como estaba. Correrlo dos veces seguidas MUST dejar exactamente los mismos datos, con los mismos identificadores (empiezan en 1).

#### Scenario: Corrida sobre base con datos ajenos
- **WHEN** la base migrada tiene filas extra (por ejemplo, un repuesto creado a mano y un movimiento suyo) y se ejecuta `seed.py`
- **THEN** las filas extra desaparecen y quedan sólo los datos iniciales

#### Scenario: Dos corridas iguales
- **WHEN** se ejecuta `seed.py` dos veces seguidas
- **THEN** las 13 tablas tienen las mismas filas, con los mismos `id`, después de cada corrida

#### Scenario: Falla a mitad de carga
- **WHEN** la carga falla después de vaciar las tablas (por ejemplo, un dato inválido)
- **THEN** la base queda con los datos que tenía antes de la corrida

### Requirement: Catálogo de estados primero
`seed.py` SHALL cargar el catálogo antes que cualquier otra tabla, con PENDIENTE (posición 1), EN_REPARACION (2), TERMINADA (3, final) y CANCELADA (4, final), cada uno con su descripción.

#### Scenario: Orden de carga
- **WHEN** se registran las sentencias de inserción que ejecuta `seed.py`
- **THEN** la primera inserción es sobre `estado_orden`

#### Scenario: Contenido del catálogo
- **WHEN** se lee `estado_orden` ordenado por posición
- **THEN** son PENDIENTE, EN_REPARACION, TERMINADA y CANCELADA en las posiciones 1 a 4, sólo las dos últimas finales, y ninguna descripción vacía

### Requirement: Usuarios y roles iniciales
`seed.py` SHALL crear siete usuarios activos con su rol vigente (sin vencimiento ni revocación): `admin@example.com` y `admin2@example.com` (ADMIN), `recepcion@example.com` (RECEPCION), `mecanico@example.com` y `mecanico2@example.com` (MECANICO), `cliente@example.com` (CLIENTE) y `nuevo@example.com` (MECANICO, único con el cambio de contraseña obligatorio).

#### Scenario: Usuarios y roles
- **WHEN** se leen los usuarios con sus asignaciones de rol vigentes
- **THEN** están los siete correos, cada uno con exactamente el rol indicado, todos activos y con `password_cambiada_en` vacío

#### Scenario: Cambio obligatorio
- **WHEN** se lee `debe_cambiar_password` de cada usuario
- **THEN** es verdadero sólo para `nuevo@example.com`

#### Scenario: Identificadores estables
- **WHEN** se leen los usuarios por `id`
- **THEN** el orden es admin (1), admin2 (2), recepcion (3), mecanico (4), mecanico2 (5), cliente (6) y nuevo (7)

### Requirement: Contraseñas de prueba con bcrypt
Cada usuario SHALL tener como `password_hash` un hash bcrypt de su contraseña de prueba, calculado con el costo de la configuración. Las contraseñas de prueba MUST vivir sólo en `seed.py`, ocupar a lo sumo 72 bytes y no ser credenciales reales.

#### Scenario: La contraseña verifica
- **WHEN** se verifica con bcrypt la contraseña de prueba de cada usuario contra su `password_hash`
- **THEN** la verificación da verdadero, y con cualquier otra contraseña da falso

#### Scenario: Costo de la configuración
- **WHEN** se ejecuta `seed.py` con `BCRYPT_COST=4` y después con `BCRYPT_COST=5`
- **THEN** los hashes de la primera corrida usan costo 4 y los de la segunda costo 5

#### Scenario: Ningún hash en texto claro
- **WHEN** se lee la columna `password_hash`
- **THEN** ningún valor coincide con una contraseña de prueba y todos tienen formato bcrypt

### Requirement: Clientes y vehículos
`seed.py` SHALL crear a Laura, con el usuario `cliente@example.com` y dos vehículos vigentes, y a Jorge, sin usuario y con un vehículo vigente. El segundo vehículo de Laura MUST tener `id` 2 y patente `AC456EF` (los usa la respuesta de ejemplo de la consigna).

#### Scenario: Laura con usuario y dos vehículos
- **WHEN** se lee el cliente asociado a `cliente@example.com` con sus vehículos
- **THEN** es Laura, con dos vehículos de `id` 1 y 2, el segundo con patente `AC456EF`

#### Scenario: Jorge sin usuario
- **WHEN** se lee el otro cliente
- **THEN** es Jorge, con `usuario_id` vacío y un único vehículo, de `id` 3

### Requirement: Repuestos con stock inicial como movimiento
`seed.py` SHALL crear, en este orden de `id`: `FIL-001` "Filtro de aceite" (8500.00, stock 10), `FRE-010` "Pastillas de freno delanteras" (32000.00, stock 4), la bujía (stock 2) y `ACE-530` "Aceite 5W30 por litro" (12000.00, stock 20). Cada stock MUST quedar registrado con un movimiento "Stock inicial" de la misma cantidad.

#### Scenario: Repuestos iniciales
- **WHEN** se leen los repuestos por `id`
- **THEN** son los cuatro indicados, vigentes, con esos códigos, descripciones, precios y stocks

#### Scenario: Stock igual a la suma de movimientos
- **WHEN** se suman los movimientos de cada repuesto
- **THEN** hay un único movimiento "Stock inicial" por repuesto, sin orden, y su cantidad es igual al stock

### Requirement: Órdenes iniciales
`seed.py` SHALL crear la orden 1, PENDIENTE, del primer vehículo de Laura, sin mecánico; y la orden 2, EN_REPARACION, del vehículo de Jorge, asignada a `mecanico@example.com`, con un ítem de 4 bujías cuando hay 2 en stock (para C-11). Cada orden MUST tener al menos un ítem, precios copiados del repuesto, total igual a la suma de subtotales e historial de estados coherente.

#### Scenario: Orden 1
- **WHEN** se lee la orden 1 con ítems e historial
- **THEN** está PENDIENTE, del vehículo 1, sin mecánico, con al menos un ítem y una línea de historial de nulo a PENDIENTE

#### Scenario: Orden 2 pide más bujías que las que hay
- **WHEN** se lee la orden 2 con ítems e historial
- **THEN** está EN_REPARACION, del vehículo 3, con mecánico `mecanico@example.com`, un ítem de 4 bujías (stock de la bujía: 2) y el historial de nulo a PENDIENTE y de PENDIENTE a EN_REPARACION

#### Scenario: Totales del servidor
- **WHEN** se compara el total de cada orden con la suma de cantidad por precio unitario de sus ítems
- **THEN** coinciden, y cada precio unitario es igual al precio del repuesto

#### Scenario: La próxima orden es la 3
- **WHEN** después del seed se inserta una orden nueva sin indicar `id`
- **THEN** recibe el `id` 3

### Requirement: Historiales iniciales
`seed.py` SHALL dejar una línea de historial de precios del filtro de aceite, de 8000.00 a 8500.00, y una línea de historial de seguridad con actor `SISTEMA` y acción "Carga de los datos iniciales".

#### Scenario: Historial de precios
- **WHEN** se lee `historial_precio_repuesto`
- **THEN** hay una sola línea, del repuesto `FIL-001`, con precio anterior 8000.00 y nuevo 8500.00

#### Scenario: Evento de seguridad
- **WHEN** se lee `evento_seguridad`
- **THEN** hay una sola línea, con actor `SISTEMA` y acción "Carga de los datos iniciales"

### Requirement: Seed sin secretos de infraestructura
`seed.py` SHALL conectarse con la misma configuración que la aplicación y MUST NOT contener la URL, el usuario ni la contraseña de la base, ni la clave de firma.

#### Scenario: Base de la configuración
- **WHEN** se ejecuta `seed.py` con `POSTGRES_DB=taller_test`
- **THEN** carga los datos en `taller_test`
