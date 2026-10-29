# Spec Delta

## Purpose

Define el límite transaccional de cada operación de la API: un único lugar que confirma o revierte todas las escrituras de un bloque, sin hacerse cargo de la vida de la sesión, y quién lo construye y quién lo abre.

## ADDED Requirements

### Requirement: Confirma al salir del bloque sin error
El Unit of Work base SHALL ser un gestor de contexto asincrónico construido con una sesión. Al salir del bloque `async with` sin excepción MUST confirmar la transacción, de modo que todas las escrituras hechas en el bloque por cualquier repositorio de esa sesión queden guardadas juntas.

#### Scenario: Varias escrituras confirmadas juntas
- **WHEN** dentro de un bloque del Unit of Work se agregan filas con dos repositorios que comparten su sesión y el bloque termina sin error
- **THEN** las dos filas son visibles desde otra sesión

#### Scenario: Entidades legibles después de confirmar
- **WHEN** termina sin error un bloque que agregó una entidad, con la sesión creada por la fábrica de la aplicación
- **THEN** los atributos de la entidad se pueden leer después del bloque sin consultar la base de nuevo

### Requirement: Revierte si el bloque sale con una excepción
Si el bloque sale con una excepción, el Unit of Work SHALL revertir la transacción y MUST dejar propagar la misma excepción, sin suprimirla ni reemplazarla. Ninguna escritura del bloque queda en la base.

#### Scenario: Excepción después de varias escrituras
- **WHEN** dentro de un bloque se agregan dos filas y después se lanza una excepción
- **THEN** la excepción sale del bloque tal cual y ninguna de las dos filas existe en la base

#### Scenario: Error de integridad dentro del bloque
- **WHEN** dentro de un bloque una escritura viola una restricción de la base
- **THEN** el error de integridad sale del bloque, la transacción queda revertida y las escrituras anteriores del bloque no existen

#### Scenario: Falla al confirmar
- **WHEN** la confirmación al salir del bloque falla por una restricción que la base verifica al confirmar
- **THEN** el error sale del bloque y la sesión queda revertida y utilizable

### Requirement: No cierra la sesión
El Unit of Work MUST NOT cerrar la sesión que recibió, ni al confirmar ni al revertir: la sesión la creó otro (la dependencia de sesión por petición) y es quien la cierra.

#### Scenario: Sesión utilizable después de revertir
- **WHEN** un bloque del Unit of Work sale con una excepción
- **THEN** la misma sesión sigue abierta y permite ejecutar una consulta nueva

#### Scenario: Sesión utilizable después de confirmar
- **WHEN** un bloque termina sin error
- **THEN** la misma sesión sigue abierta y permite abrir otro bloque del Unit of Work

### Requirement: Único punto de confirmación
El Unit of Work SHALL ser el único componente del código de la aplicación que confirma una transacción: ni los repositorios ni los servicios ni los routers MUST llamar a `commit`. La única excepción permitida es la escritura de `intento_acceso` en sesión y transacción propias (Ejercicio 7), que la declara su change.

#### Scenario: Nadie más confirma
- **WHEN** se revisa el código de `app/` y `main.py` en busca de llamadas a `commit`
- **THEN** la única aparece en el Unit of Work base, salvo la de `intento_acceso` cuando exista y esté comentada

### Requirement: Unit of Work por módulo con una sola sesión
Un Unit of Work concreto SHALL heredar del base y componer los repositorios que su módulo necesita, todos construidos con la misma sesión que recibió el Unit of Work.

#### Scenario: Repositorios compartiendo la sesión
- **WHEN** se construye un Unit of Work concreto de prueba con dos repositorios
- **THEN** ambos repositorios usan la sesión del Unit of Work y lo que escriben se confirma o se revierte junto

### Requirement: El router construye y el servicio abre
El Unit of Work de una petición SHALL construirse con una dependencia de la API a partir de la sesión de esa petición y entregarse al servicio sin abrir. El servicio MUST abrirlo con `async with` y nunca construirlo.

#### Scenario: Petición que escribe
- **WHEN** una ruta de prueba recibe por dependencia un Unit of Work, se lo pasa a un servicio que lo abre y agrega una fila, y la petición termina bien
- **THEN** la fila queda confirmada y la sesión de la petición se cerró al terminar

#### Scenario: Petición que falla
- **WHEN** el servicio lanza una excepción dentro del bloque y la ruta la traduce a un código de error
- **THEN** la respuesta tiene ese código y la fila no existe en la base
