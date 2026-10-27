# Tasks

> TDD estricto en cada tarea: **ROJO** (escribir primero el test indicado, ejecutarlo y verificar que falla por la razón esperada) → **VERDE** (código mínimo, ejecutado) → **TRIANGULAR** (otro caso con datos distintos) → **REFACTOR** (tests verdes después de cada paso). Cada escenario de las specs tiene al menos un test; el nombre del escenario va en el docstring del test.
> Tests en `tests/` (pytest) contra la base real `taller_test` creada con `alembic upgrade head` (fixture `base_migrada`); los modelos de prueba viven en el esquema `nucleo_prueba` con metadata propia (design D6), nunca en `SQLModel.metadata` ni con `create_all` del esquema de la app. Comando: `python -m pytest` desde la raíz, con el venv del equipo activado.
> Governance ALTO: en cada **[CHECKPOINT]** se frena y se le muestra a Elías lo hecho; no se sigue sin su OK. Antes de empezar, confirmar las "Decisiones a confirmar por Elías" de `design.md`.
> Commits chicos y en español con el nombre del change, en la rama `feat/nucleo-repositorios-uow`. Ninguna contraseña de la base en archivos versionados, en el chat ni en logs.

## 0. Red de seguridad

- [x] 0.1 Correr la suite completa actual y anotar la línea base (`N passed`). Si algo falla, PARAR y reportarlo como falla previa (no arreglarlo acá)
- [x] 0.2 Verificar que `taller_test` no tiene el esquema `nucleo_prueba` (consulta a `information_schema.schemata`); si existe, PARAR y preguntar antes de borrarlo

## 1. Modelos y esquema de prueba (`tests/nucleo_modelos.py`, fixtures)

- [x] 1.1 ROJO `tests/test_repository.py::test_los_modelos_de_prueba_no_ensucian_la_metadata_de_la_app`: tras importar `tests.nucleo_modelos`, `SQLModel.metadata.tables` sigue teniendo exactamente las 13 tablas y la metadata de prueba tiene `nucleo_prueba.cosa_prueba` y `nucleo_prueba.detalle_prueba`. Ejecutar: falla (no existe el módulo)
- [x] 1.2 VERDE: `tests/nucleo_modelos.py` con `BasePrueba` sobre `registry()` y `MetaData(schema="nucleo_prueba")` propios, `CosaPrueba` (`id`, `nombre` UNIQUE, `etiqueta`, `borrado_en timestamptz NULL`, `detalles` con `lazy="raise"`) y `DetallePrueba` (`id`, `cosa_id` FK con índice, `texto`, `codigo` UNIQUE `DEFERRABLE INITIALLY DEFERRED`, `cosa` con `lazy="raise"`) según design D6. Si el registro propio no aísla la metadata, aplicar el plan B de "Risks". Ejecutar 1.1 y `tests/test_modelos.py`: verdes
- [x] 1.3 ROJO→VERDE fixtures en `tests/conftest.py`: `esquema_nucleo` (depende de `motor`; `DROP SCHEMA IF EXISTS nucleo_prueba CASCADE`, `CREATE SCHEMA`, `CreateTable` de las dos tablas; al terminar `DROP SCHEMA ... CASCADE`) y `sesiones` (= `crear_fabrica_sesiones(motor)`). Test: con la fixture, las dos tablas existen en `information_schema.tables`; TRIANGULAR: después del test el esquema ya no existe (verificarlo en un test siguiente o con un finalizador). Ejecutar: verdes
- [x] 1.4 Correr toda la suite: `test_modelos.py` (13 tablas) y `test_migraciones.py` (`alembic check`) siguen verdes

## 2. Paginación pura (`app/core/paginacion.py`)

- [x] 2.1 ROJO `tests/test_paginacion.py` (spec paginacion, "Cálculo de la cantidad de páginas"): `calcular_paginas` con (0,20)→1, (0,1)→1, (1,1)→1, (1,20)→1, (40,20)→2, (41,20)→3, parametrizado. Ejecutar: falla (no existe el módulo)
- [x] 2.2 VERDE: `calcular_paginas(total, size)` = `max(1, ceil(total/size))`. Ejecutar: verde
- [x] 2.3 ROJO→VERDE `PaginaInexistente(page=3, pages=2)`: su mensaje es exactamente `La página 3 no existe: hay 2`; TRIANGULAR con (2,1) → `La página 2 no existe: hay 1`. Ejecutar: verdes
- [x] 2.4 ROJO→VERDE `Pagina[T]` (escenario "Forma del envoltorio"): serializada tiene exactamente las claves `items`, `total`, `page`, `size`, `pages`; TRIANGULAR: con `items` vacío y `total` 0 serializa `pages` 1 tal como se le pasó. Ejecutar: verdes
- [x] 2.5 ROJO→VERDE parámetros (requirement "Parámetros de página validados en el contrato") con una mini `FastAPI()` de prueba que declara `Depends(parametros_pagina)` y devuelve los valores recibidos: sin parámetros → `page` 1, `size` 20; `size=1` y `size=100` → 200; `size=0`, `101`, `500` → 422; `page=0`, `-1`, `abc` → 422; en los 422 el handler no se ejecutó (contador en el test). Ejecutar: verdes
- [x] 2.6 ROJO→VERDE manejador (requirement "Página inexistente"): la mini app registra `responder_pagina_inexistente`; una ruta que lanza `PaginaInexistente(3, 2)` responde 422 con `{"detail": "La página 3 no existe: hay 2"}` y sin traza. TRIANGULAR: sin registrar el manejador la misma ruta daría 500 (documenta por qué se registra en `main.py`). Ejecutar: verdes
- [x] 2.7 ROJO→VERDE registro en `main.py`: test de que `app.exception_handlers` de la app real tiene `PaginaInexistente` → `responder_pagina_inexistente`; agregar la línea `app.add_exception_handler(...)` en `main.py` con comentario (RN-18). Ejecutar: verde
- [x] 2.8 REFACTOR: docstrings del módulo (envoltorio, `pages` mínimo 1, mensaje); suite verde

## 3. `BaseRepository[T]` (`app/core/repository.py`)

- [x] 3.1 ROJO `tests/test_repository.py` ("Identificador inexistente"): `BaseRepository(sesion, CosaPrueba).get_by_id(999)` devuelve `None` sin excepción. Ejecutar: falla (no existe el módulo)
- [x] 3.2 VERDE: clase genérica con constructor `(session, modelo)`, PK por introspección (falla con PK compuesta) y `get_by_id` con `select().where(pk == id)` sobre `_consulta_base()` (design D1). TRIANGULAR "Identificador existente": tras insertar una fila con SQL Core, `get_by_id` la devuelve con sus columnas. Ejecutar: verdes
- [x] 3.3 ROJO→VERDE `add` ("add asigna la clave y no confirma"): tras `add` la entidad tiene `id`; desde otra sesión de `sesiones`, `get_by_id` da `None`. TRIANGULAR ("Lo agregado se pierde si nadie confirma"): `add` + `rollback` → la fila no existe desde otra sesión. Ejecutar: verdes
- [x] 3.4 ROJO→VERDE ("Una violación de restricción aparece en la escritura"): `add` de dos `CosaPrueba` con el mismo `nombre` → el segundo `add` lanza `IntegrityError` (no la confirmación). Ejecutar: verde
- [x] 3.5 ROJO→VERDE `update` ("update aplica sólo los campos indicados"): `update(cosa, {"etiqueta": "b"})` cambia `etiqueta` en la base dentro de la transacción (leída con `SELECT` directo) y `nombre` sigue igual; TRIANGULAR: `update(cosa, {"no_existe": 1})` lanza `ValueError`; `update(cosa)` sin cambios sincroniza un atributo modificado a mano. Ejecutar: verdes
- [x] 3.6 ROJO→VERDE `delete` ("delete borra de verdad"): tras `delete`, `get_by_id` da `None` y un `SELECT count(*)` directo da 0 en la misma transacción. Ejecutar: verde
- [x] 3.7 ROJO→VERDE `get_all`/`count` ("Tabla vacía"): lista vacía y 0; TRIANGULAR ("Desplazamiento y límite"): con 5 filas insertadas en orden no correlativo con su `id`, `get_all(offset=2, limit=2)` trae la 3.ª y 4.ª por `id` y `count()` da 5. Ejecutar: verdes
- [x] 3.8 ROJO→VERDE ("Dos repositorios de clases distintas sobre la misma sesión"): repos de `CosaPrueba` y `DetallePrueba` con la misma sesión; cada `count` cuenta sólo lo suyo y un `rollback` deshace ambas escrituras. Ejecutar: verde
- [x] 3.9 ROJO→VERDE `_paginar` ("Total con el filtro aplicado"): 5 filas, 3 con `etiqueta="x"`; una subclase de prueba con `listar_por_etiqueta(etiqueta, pagina)` que arma la consulta con parámetro ligado y llama a `_paginar` → ítems = las 2 primeras `x`, `total` 3, `pages` 2. TRIANGULAR ("Filtro sin coincidencias"): etiqueta inexistente → `items` vacío, `total` 0, `pages` 1; página 3 de las `x` con size 2 → `PaginaInexistente(3, 2)` sin ejecutar la consulta de ítems (contador de sentencias). Ejecutar: verdes
- [x] 3.10 ROJO→VERDE precarga ("Relación no precargada"): `get_by_id` de una cosa con detalles y acceso a `.detalles` lanza el error de `lazy="raise"` y el contador de `before_cursor_execute` no sube. TRIANGULAR ("Relación precargada por el método"): una subclase de prueba con `get_con_detalles(id)` que declara `selectinload` adentro; con 1 y con 5 detalles se ejecuta el mismo número de sentencias (2) y `.detalles` se lee sin consultas extra. Ejecutar: verdes
- [x] 3.11 ROJO→VERDE test de texto ("Las escrituras sincronizan sin confirmar"): `app/core/repository.py` no contiene `.commit(`. Ejecutar: verde
- [x] 3.12 REFACTOR: docstrings (por qué la clase del modelo en el constructor, por qué `select` y no `session.get`, convención de precarga y de `_paginar` con una fila por entidad); suite verde

## 4. `SoftDeleteRepository[T]`

- [x] 4.1 ROJO ("El dado de baja deja de aparecer"): 3 cosas, una con `borrado_en` cargado por SQL Core → `SoftDeleteRepository(sesion, CosaPrueba)`: `get_all` trae 2, `count` 2, `get_by_id` de la dada de baja `None`. Ejecutar: falla (no existe la clase)
- [x] 4.2 VERDE: subclase que redefine `_consulta_base()` con `borrado_en IS NULL` (design D2). Ejecutar: verde
- [x] 4.3 ROJO→VERDE ("Modelo sin columna de baja"): `SoftDeleteRepository(sesion, DetallePrueba)` lanza `TypeError` con un mensaje que menciona `borrado_en`. Ejecutar: verde
- [x] 4.4 ROJO→VERDE `soft_delete` ("La fila se conserva"): tras `soft_delete`, un `SELECT` directo encuentra la fila con sus datos y `borrado_en` con zona (`utcoffset()` no nulo), y las lecturas del repo ya no la devuelven; TRIANGULAR ("Baja repetida"): segunda `soft_delete` conserva el instante de la primera. Ejecutar: verdes
- [x] 4.5 ROJO→VERDE `get_by_id_including_deleted` ("Entidad dada de baja" y "Entidad inexistente"): devuelve la dada de baja con `borrado_en` cargado; con un id inexistente, `None`. Ejecutar: verdes
- [x] 4.6 ROJO→VERDE ("Paginado con borrado lógico"): repetir el escenario de 3.9 con una de las `x` dada de baja → no aparece en ítems y `total` es 2. Ejecutar: verde
- [x] 4.7 REFACTOR: docstring (lo usan vehículo y repuesto; `get_by_id_including_deleted` para terminar órdenes, DD-14); suite verde
- [ ] 4.8 **[CHECKPOINT 1 — repositorios y paginación]** Frenar y mostrarle a Elías `repository.py`, `paginacion.py`, la línea de `main.py`, `tests/nucleo_modelos.py`, las fixtures y los tests. No seguir sin su OK

## 5. `UnitOfWork` base (`app/core/unit_of_work.py`)

- [x] 5.1 ROJO `tests/test_unit_of_work.py` ("Varias escrituras confirmadas juntas"): un `UoWPrueba(UnitOfWork)` de test con `self.cosas` y `self.detalles` sobre la sesión recibida; `async with uow:` agrega una cosa y un detalle; desde otra sesión se ven las dos filas. Ejecutar: falla (no existe el módulo)
- [x] 5.2 VERDE: `UnitOfWork(session)` con `__aenter__` que devuelve `self` y `__aexit__` que confirma sin excepción (design D4). Ejecutar: verde
- [x] 5.3 ROJO→VERDE ("Excepción después de varias escrituras"): dos `add` y `raise ValueError("x")` dentro del bloque → `pytest.raises(ValueError)` con el mismo objeto de excepción, y ninguna fila existe desde otra sesión. Ejecutar: verde
- [x] 5.4 ROJO→VERDE ("Error de integridad dentro del bloque"): `add` válido y luego `add` con `nombre` repetido → sale `IntegrityError`, y la primera fila no existe. Ejecutar: verde
- [x] 5.5 ROJO→VERDE ("Falla al confirmar"): dos detalles con el mismo `codigo` (UNIQUE diferido: el `flush` pasa) → el error sale al confirmar, la sesión queda revertida (`session.in_transaction()` falso o una consulta nueva funciona) y no hay filas. Ejecutar: verde
- [x] 5.6 ROJO→VERDE ("Sesión utilizable después de revertir" y "después de confirmar"): tras un bloque con excepción la misma sesión ejecuta `SELECT 1`; tras un bloque OK se abre un segundo bloque con el mismo UoW, agrega otra fila y se confirma. Verificar además que el UoW nunca llamó a `close` (sesión envuelta con un espía o `session.is_active`). Ejecutar: verdes
- [x] 5.7 ROJO→VERDE ("Entidades legibles después de confirmar"): con la sesión de `crear_fabrica_sesiones(motor)`, tras el bloque se leen los atributos de la entidad agregada sin que el contador de sentencias suba. Ejecutar: verde
- [x] 5.8 ROJO→VERDE ("Repositorios compartiendo la sesión"): `uow.cosas.session is uow.detalles.session is sesion`; lo escrito por ambos se revierte junto con una excepción. Ejecutar: verde
- [x] 5.9 ROJO→VERDE ("Nadie más confirma"): test de texto sobre `app/` y `main.py`: la única `.commit(` está en `app/core/unit_of_work.py` (lista de excepciones vacía hoy, con un comentario que reserva la de `intento_acceso` de CH-04). Ejecutar: verde
- [x] 5.10 ROJO→VERDE ("Petición que escribe" y "Petición que falla"): mini `FastAPI()` con `lifespan` que guarda `crear_fabrica_sesiones(motor)` en `app.state.session_factory`; dependencia `get_uow_prueba(session=Depends(get_session))` que construye el `UoWPrueba`; ruta POST que se lo pasa a un servicio de prueba que lo abre con `async with`. Caso OK → 201 y la fila existe desde otra sesión; caso con excepción de dominio traducida por la ruta a 409 → 409 y la fila no existe; en ambos la sesión de la petición quedó cerrada (espía sobre la fábrica). Ejecutar: verdes
- [x] 5.11 REFACTOR: docstring del módulo con el patrón de UoW concreto, la dependencia del router y "el servicio lo abre, nunca lo construye" (design D4); suite verde
- [ ] 5.12 **[CHECKPOINT 2 — Unit of Work]** Frenar y mostrarle a Elías `unit_of_work.py` y sus tests. No seguir sin su OK

## 6. Cierre

- [x] 6.1 Correr la suite completa (`python -m pytest` desde la raíz) y comparar con la línea base de 0.1: todo verde, `nucleo_prueba` no existe al terminar y `alembic check` sigue verde
- [x] 6.2 Verificar a mano contra las reglas que toca el change y anotar el resultado en el PR: CLAUDE.md #13 (flush sin commit, clase del modelo, `SoftDeleteRepository` hereda, catálogo libre de heredar, precarga en el método), #14 (UoW confirma/revierte/no cierra, único commit, router construye/servicio abre), #16 (envoltorio, page/size, 422, total con filtros, página vacía), #17 (sin SQL concatenado, todo `async`); AP-04; soporte de RN-02, RN-13, RN-20 (un bloque) y RN-16 (baja lógica); RN-18 (página inexistente sin 500). Casos C: ninguno directo; anotar que C-16 (paginación con filtro, `page=2` → 422, `size=500` → 422) queda cubierto en su lógica por los tests de 2.x y 3.9
- [x] 6.3 Agregar en `docs/bitacora.md`, sección de Elías, la entrada `### 2026-10-XX · CH-03 nucleo-repositorios-uow` con la plantilla (fecha, qué se le pidió al agente, qué se corrigió a mano y por qué), incluyendo las decisiones confirmadas de `design.md`
- [ ] 6.4 Escribir en la descripción del PR (`Closes #3`) las firmas públicas de `BaseRepository`, `SoftDeleteRepository`, `UnitOfWork`, `parametros_pagina`, `Pagina` y `PaginaInexistente` para Hernán, Joaquín y Bruno, y el aviso a Belén del esquema `nucleo_prueba` (design D6)

## Workflow follow-up

- PR de `feat/nucleo-repositorios-uow` a `main` con `Closes #3` y aprobación de un compañero.
- Tras el merge: `/opsx:archive nucleo-repositorios-uow` y marcar CH-03 en `CHANGES.md`.
