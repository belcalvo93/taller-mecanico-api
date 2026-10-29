# Spec Delta

## Purpose

Fija el contrato común de todos los listados de la API: qué parámetros de página aceptan, la forma del envoltorio que devuelven, cómo se calcula la cantidad de páginas y qué pasa al pedir una página que no existe.

## ADDED Requirements

### Requirement: Parámetros de página validados en el contrato
Los listados SHALL aceptar los parámetros de consulta `page` (entero ≥ 1, por defecto 1) y `size` (entero de 1 a 100, por defecto 20). Un valor fuera de rango o no entero MUST responderse con 422 por el contrato, sin ejecutar el listado ni terminar en 500.

#### Scenario: Valores por defecto
- **WHEN** se pide un listado sin `page` ni `size`
- **THEN** se usa la página 1 con tamaño 20

#### Scenario: Límites aceptados
- **WHEN** se pide un listado con `size=1` y con `size=100`
- **THEN** ambos pedidos se aceptan

#### Scenario: Tamaño fuera de rango
- **WHEN** se pide un listado con `size=0`, `size=101` o `size=500`
- **THEN** la respuesta es 422 y el listado no se ejecuta

#### Scenario: Página menor que uno o no entera
- **WHEN** se pide un listado con `page=0`, `page=-1` o `page=abc`
- **THEN** la respuesta es 422 y el listado no se ejecuta

### Requirement: Envoltorio estándar de los listados
Todo listado SHALL responder un objeto con exactamente las claves `items` (los elementos de la página), `total` (cantidad de elementos que cumplen los filtros en todas las páginas), `page`, `size` y `pages`.

#### Scenario: Forma del envoltorio
- **WHEN** hay 4 elementos y se pide la página 1 con tamaño 2
- **THEN** la respuesta tiene `items` con 2 elementos, `total` 4, `page` 1, `size` 2 y `pages` 2, y ninguna otra clave

### Requirement: Cálculo de la cantidad de páginas
`pages` SHALL ser la cantidad de páginas de tamaño `size` necesarias para `total` elementos, redondeando hacia arriba, con un mínimo de 1: con cero resultados hay una página, vacía.

#### Scenario: Cero resultados
- **WHEN** `total` es 0 con cualquier `size`
- **THEN** `pages` es 1 y la página 1 tiene `items` vacío

#### Scenario: Un resultado
- **WHEN** `total` es 1 y `size` es 1 o 20
- **THEN** `pages` es 1

#### Scenario: Varios resultados
- **WHEN** `total` es 40 con `size` 20, y `total` es 41 con `size` 20
- **THEN** `pages` es 2 en el primer caso y 3 en el segundo

### Requirement: Página inexistente
Pedir una página mayor que `pages` MUST responderse con 422 y un mensaje propio que diga la página pedida y cuántas hay (por ejemplo `La página 3 no existe: hay 2`), sin texto interno de la base ni traza.

#### Scenario: Más allá de la última
- **WHEN** hay 4 elementos y se pide `page=3` con `size=2`
- **THEN** la respuesta es 422 con el mensaje `La página 3 no existe: hay 2`

#### Scenario: Segunda página sin resultados
- **WHEN** no hay elementos y se pide `page=2`
- **THEN** la respuesta es 422 con el mensaje `La página 2 no existe: hay 1`

#### Scenario: La última página existe
- **WHEN** hay 4 elementos y se pide `page=2` con `size=2`
- **THEN** la respuesta es 200 con los dos últimos elementos
