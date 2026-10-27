# Spec Delta

## Purpose

Define el acceso genérico a datos que heredan los repositorios de todos los módulos: lecturas y escrituras básicas sin confirmar la transacción, el filtro de los registros dados de baja y la forma de declarar la precarga de relaciones.

## ADDED Requirements

### Requirement: Repositorio genérico construido con la sesión y la clase del modelo
El núcleo SHALL ofrecer un repositorio genérico (`BaseRepository[T]`) que reciba en su constructor la sesión y la clase del modelo con la que trabaja, porque el parámetro de tipo no existe en tiempo de ejecución. Las operaciones `get_by_id`, `get_all`, `count`, `add`, `update` y `delete` MUST operar sobre la tabla de esa clase y sobre esa sesión, sin abrir otra.

#### Scenario: Dos repositorios de clases distintas sobre la misma sesión
- **WHEN** se construyen dos repositorios genéricos con la misma sesión y dos clases de modelo distintas, y se agrega una fila con cada uno
- **THEN** cada repositorio cuenta y lista sólo las filas de su propia tabla, y ambas escrituras quedan en la misma transacción

### Requirement: Lectura por identificador
`get_by_id` SHALL devolver la entidad cuya clave primaria es el identificador pedido, o un valor nulo si no existe ninguna; nunca MUST lanzar una excepción por inexistencia.

#### Scenario: Identificador existente
- **WHEN** se pide por identificador una fila agregada previamente
- **THEN** se obtiene la entidad con sus columnas

#### Scenario: Identificador inexistente
- **WHEN** se pide un identificador que no corresponde a ninguna fila
- **THEN** el resultado es nulo y no se lanza ninguna excepción

### Requirement: Listado y conteo
`get_all` SHALL devolver las entidades de la tabla en un orden estable por clave primaria, con desplazamiento y límite opcionales; `count` SHALL devolver cuántas filas hay. Con la tabla vacía, `get_all` MUST devolver una lista vacía y `count` cero.

#### Scenario: Tabla vacía
- **WHEN** se lista y se cuenta una tabla sin filas
- **THEN** el listado es una lista vacía y el conteo es cero

#### Scenario: Desplazamiento y límite
- **WHEN** hay cinco filas y se lista con desplazamiento 2 y límite 2
- **THEN** se obtienen la tercera y la cuarta fila por orden de clave primaria, y el conteo sigue siendo cinco

### Requirement: Las escrituras sincronizan sin confirmar
`add`, `update` y `delete` SHALL sincronizar el cambio con la base dentro de la transacción en curso (`flush`), de modo que la clave primaria generada y los errores de restricción aparezcan en el momento, y MUST NOT confirmar la transacción: ningún repositorio hace `commit`.

#### Scenario: add asigna la clave y no confirma
- **WHEN** se agrega una entidad nueva y, sin confirmar, se la busca desde otra sesión
- **THEN** la entidad ya tiene su clave primaria asignada en la sesión que la agregó, y la otra sesión no la ve

#### Scenario: Lo agregado se pierde si nadie confirma
- **WHEN** se agrega una entidad y la transacción se revierte
- **THEN** la fila no existe en la base

#### Scenario: update aplica sólo los campos indicados
- **WHEN** se actualiza una entidad persistida indicando un único campo cambiado
- **THEN** ese campo cambia en la base dentro de la transacción y los demás conservan su valor

#### Scenario: Una violación de restricción aparece en la escritura
- **WHEN** se agrega una entidad que viola una restricción de unicidad de la base
- **THEN** la operación `add` misma lanza el error de integridad, sin esperar a la confirmación

#### Scenario: delete borra de verdad
- **WHEN** se borra una entidad con `delete` y luego se la busca por identificador en la misma transacción
- **THEN** el resultado es nulo y la fila ya no existe en la tabla

### Requirement: Repositorio con borrado lógico
El núcleo SHALL ofrecer un repositorio con borrado lógico (`SoftDeleteRepository[T]`) que herede del genérico, para modelos con la columna `borrado_en`. Todas sus lecturas heredadas (`get_by_id`, `get_all`, `count` y el listado paginado) MUST excluir las filas con `borrado_en` no nulo.

#### Scenario: El dado de baja deja de aparecer
- **WHEN** hay tres filas, una de ellas con `borrado_en` cargado
- **THEN** el listado trae dos, el conteo da dos y buscar por identificador la dada de baja da nulo

#### Scenario: Modelo sin columna de baja
- **WHEN** se construye un repositorio con borrado lógico para una clase de modelo que no tiene `borrado_en`
- **THEN** la construcción falla con un error que lo explica

### Requirement: Baja lógica
`soft_delete` SHALL marcar la entidad con el instante actual con zona horaria en `borrado_en` y sincronizarlo sin confirmar, conservando la fila y todos sus datos. Dar de baja una entidad ya dada de baja MUST conservar el instante de la primera baja.

#### Scenario: La fila se conserva
- **WHEN** se da de baja una entidad vigente
- **THEN** la fila sigue en la tabla con sus datos y con `borrado_en` igual a un instante con zona horaria, y las lecturas del repositorio ya no la devuelven

#### Scenario: Baja repetida
- **WHEN** se da de baja dos veces la misma entidad
- **THEN** `borrado_en` conserva el instante de la primera baja

### Requirement: Lectura incluyendo los dados de baja
`get_by_id_including_deleted` SHALL devolver la entidad por identificador esté vigente o dada de baja, y nulo sólo si la fila no existe.

#### Scenario: Entidad dada de baja
- **WHEN** se pide con esta operación una entidad dada de baja
- **THEN** se obtiene la entidad, con su `borrado_en` cargado

#### Scenario: Entidad inexistente
- **WHEN** se pide con esta operación un identificador que no existe
- **THEN** el resultado es nulo

### Requirement: Listado paginado con los mismos filtros
El repositorio genérico SHALL ofrecer a sus subclases un listado paginado que reciba una consulta (con los filtros que el repositorio concreto arme) y la página pedida, y devuelva el envoltorio de paginación. El `total` MUST contarse con exactamente los mismos filtros que los ítems de la página.

#### Scenario: Total con el filtro aplicado
- **WHEN** hay cinco filas, tres cumplen un filtro y se pide la página 1 de tamaño 2 con ese filtro
- **THEN** los ítems son las dos primeras que cumplen el filtro, `total` es 3 y `pages` es 2

#### Scenario: Filtro sin coincidencias
- **WHEN** ninguna fila cumple el filtro y se pide la página 1
- **THEN** se obtiene una página vacía con `total` 0 y `pages` 1

#### Scenario: Paginado con borrado lógico
- **WHEN** se pagina con un repositorio con borrado lógico y una de las filas que cumple el filtro está dada de baja
- **THEN** esa fila no aparece en los ítems ni cuenta en `total`

### Requirement: Precarga declarada en el método que la usa
Las operaciones genéricas MUST NOT precargar relaciones, y ninguna lectura SHALL depender de la carga perezosa. Un repositorio concreto que necesita una relación SHALL declarar la carga anticipada dentro del método que la trae.

#### Scenario: Relación no precargada
- **WHEN** se lee una entidad con `get_by_id` y se accede a una de sus relaciones
- **THEN** el acceso falla en el acto sin ejecutar ninguna consulta

#### Scenario: Relación precargada por el método
- **WHEN** un repositorio concreto define un método que trae la entidad con su relación declarada como carga anticipada
- **THEN** la relación se puede leer sin consultas adicionales, con un número fijo de consultas que no crece con la cantidad de elementos relacionados
