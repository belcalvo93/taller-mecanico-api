# evidencias-de-entrega Specification

## Purpose
Deja registrado y comprobable que los casos C-01..C-19 se corrieron contra una base sembrada, que están las evidencias de C-14 y C-15 que pide la consigna y que la bitácora y las reglas RN-01..RN-20 se revisaron antes de entregar.

## Requirements

### Requirement: Un archivo por caso y resultado registrado
Para cada caso C-01..C-19 SHALL existir en `test/` un archivo `.http` (C-14 es `solo_agregado.sql`) con la respuesta esperada en un comentario. Cada corrida MUST empezar con `python seed.py` y su resultado (esperado, obtenido y aprobado o fallado) SHALL quedar escrito en `docs/evidencias/`. Los archivos de los compañeros MUST NOT modificarse.

#### Scenario: Casos disponibles en la Fase A
- **WHEN** se listan los archivos de `test/` con CH-08 todavía sin mergear
- **THEN** están C-01 a C-05, C-07, C-08, C-09, C-16, C-18 y C-19 y `solo_agregado.sql`, y cada uno tiene un registro de corrida

#### Scenario: Casos pendientes de CH-08
- **WHEN** se arma el registro de la Fase A
- **THEN** C-06, C-10, C-11, C-12, C-13, C-15 y C-17 figuran como "pendiente de CH-08", no como aprobados

#### Scenario: Un caso falla
- **WHEN** un `.http` devuelve algo distinto de lo que dice su comentario
- **THEN** el registro lista el caso, lo esperado, lo obtenido y el integrante dueño, sin cambiar el archivo

### Requirement: Evidencia de C-14 con los siete rechazos
Con la base migrada y sembrada, la ejecución de `test/solo_agregado.sql` en psql SHALL producir siete errores: un UPDATE y un DELETE sobre cada una de `historial_estado_orden`, `movimiento_stock` e `historial_precio_repuesto` rechazados por el disparador de sólo agregado, y la orden llevada a un estado fuera del catálogo rechazada por la clave foránea. La salida MUST guardarse en `docs/evidencias/` y no modificar ningún dato.

#### Scenario: Seis rechazos del disparador
- **WHEN** se ejecutan los seis UPDATE y DELETE sobre las tres tablas de sólo agregado
- **THEN** cada sentencia falla con el mensaje de que la tabla es de sólo agregado y las tablas conservan sus filas

#### Scenario: Rechazo por la clave foránea
- **WHEN** se ejecuta el UPDATE que pone el estado `DEMORADA` a una orden
- **THEN** PostgreSQL lo rechaza por la clave foránea `fk_orden_trabajo_estado_estado_orden`

### Requirement: Evidencia de C-15 con 2 y 4 ítems
Con `SQL_ECHO=true`, la consola SHALL mostrar las consultas del detalle de una orden con 2 ítems y las de otra con 4 ítems, y la cantidad de sentencias MUST ser la misma en los dos casos. El fragmento de consola SHALL guardarse en `docs/evidencias/`. Esta evidencia depende de CH-08.

#### Scenario: Misma cantidad de consultas
- **WHEN** se pide el detalle de la orden con 2 ítems y el de la orden con 4 ítems con el eco de SQL activo
- **THEN** la consola registra el mismo número de consultas para ambos

#### Scenario: Evidencia diferida
- **WHEN** CH-08 todavía no está en `main`
- **THEN** la evidencia de C-15 figura como pendiente y no se simula ni se escribe a mano

### Requirement: Bitácora con una sección por integrante
`docs/bitacora.md` SHALL tener una sección por cada uno de los cinco integrantes (Belén, Elías, Hernán, Bruno, Joaquín) y cada entrada MUST llevar fecha, qué se le pidió al agente y qué se corrigió a mano y por qué. La revisión SHALL informar las secciones o entradas que falten y qué integrante las tiene que completar.

#### Scenario: Entradas completas
- **WHEN** se revisa la bitácora
- **THEN** cada integrante con un change mergeado tiene su entrada con los tres datos

#### Scenario: Entrada faltante
- **WHEN** a un integrante le falta la entrada de un change mergeado, por ejemplo CH-08 de Elías
- **THEN** se lista como pendiente a su nombre y no se redacta por él

### Requirement: Verificación final de RN-01 a RN-20
Antes de entregar SHALL recorrerse cada regla RN-01..RN-20 contra el código y su evidencia (test, caso C o consulta) y dejarse una tabla con una fila por regla y su resultado. Esta verificación MUST hacerse con CH-08 mergeada, porque RN-02, RN-13, RN-19 y RN-20 dependen de las órdenes.

#### Scenario: Tabla completa
- **WHEN** termina la verificación
- **THEN** hay veinte filas, cada una con la evidencia que la respalda y el resultado

#### Scenario: Regla sin evidencia
- **WHEN** una regla no tiene evidencia que la respalde
- **THEN** se marca como hallazgo con su dueño y no se da por cumplida
