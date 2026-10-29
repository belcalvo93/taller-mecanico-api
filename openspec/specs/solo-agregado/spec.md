# solo-agregado Specification

## Purpose

Hace que el historial de estados de las órdenes, los movimientos de stock y el historial de precios sean inmutables por garantía de la base (RN-15), venga de donde venga la modificación, y deja el script del caso C-14 que lo demuestra.

## Requirements

### Requirement: Inserción permitida en las tablas de sólo agregado
`historial_estado_orden`, `movimiento_stock` e `historial_precio_repuesto` SHALL aceptar `INSERT` de filas válidas como cualquier otra tabla.

#### Scenario: Agregar una línea
- **WHEN** se inserta una fila válida en cada una de las tres tablas
- **THEN** las tres inserciones se aceptan y las filas quedan guardadas

### Requirement: UPDATE rechazado por la base
La base SHALL rechazar cualquier `UPDATE` sobre las tres tablas, sin importar el cliente que lo envíe (la API, psql o un script), con un error que nombra la tabla y aclara que es de sólo agregado. La fila MUST quedar como estaba.

#### Scenario: UPDATE en cada tabla
- **WHEN** se ejecuta un `UPDATE` sobre una fila existente de cada una de las tres tablas
- **THEN** las tres sentencias fallan con el mensaje de sólo agregado y los valores no cambian

#### Scenario: UPDATE que no toca filas
- **WHEN** se ejecuta un `UPDATE` cuyo `WHERE` no coincide con ninguna fila (o sobre una tabla vacía)
- **THEN** la sentencia también se rechaza

### Requirement: DELETE rechazado por la base
La base SHALL rechazar cualquier `DELETE` sobre las tres tablas, con el mismo tipo de error, y las filas MUST seguir existiendo.

#### Scenario: DELETE en cada tabla
- **WHEN** se ejecuta un `DELETE` sobre una fila existente de cada una de las tres tablas
- **THEN** las tres sentencias fallan con el mensaje de sólo agregado y la cantidad de filas no cambia

### Requirement: Las demás tablas no se ven afectadas
El sólo agregado MUST aplicarse sólo a esas tres tablas: el resto de las tablas SHALL seguir aceptando `UPDATE` y `DELETE`.

#### Scenario: Tabla común
- **WHEN** se actualiza el precio de un repuesto o la falla de una orden
- **THEN** la actualización se acepta

### Requirement: Vaciado para volver al estado inicial
Las tres tablas SHALL poder vaciarse por completo con `TRUNCATE` (lo usa `seed.py` para dejar la base en el estado inicial); `TRUNCATE` no es un `UPDATE` ni un `DELETE` de filas y queda fuera de RN-15.

#### Scenario: TRUNCATE permitido
- **WHEN** se vacían las tablas con `TRUNCATE`
- **THEN** la operación se acepta y las tres tablas quedan vacías

### Requirement: Script del caso C-14
El repositorio SHALL incluir `test/solo_agregado.sql`, ejecutable en psql sobre una base migrada y sembrada, con siete sentencias, cada una con su resultado esperado en un comentario: un `UPDATE` y un `DELETE` por cada tabla de sólo agregado (seis rechazos del disparador) y una orden llevada a un estado que no está en el catálogo (rechazo de la clave foránea).

#### Scenario: Siete rechazos
- **WHEN** se ejecuta cada sentencia del script sobre `taller_test` recién migrada y sembrada
- **THEN** las seis primeras fallan por el disparador de sólo agregado y la séptima falla por la clave foránea a `estado_orden`

#### Scenario: El script no modifica datos
- **WHEN** después de ejecutar el script se cuentan las filas y se leen los valores de las tablas tocadas
- **THEN** son los mismos que antes de ejecutarlo

#### Scenario: Ejecutable en psql de punta a punta
- **WHEN** se ejecuta el script completo en psql
- **THEN** psql no se detiene en el primer error: muestra los siete rechazos
