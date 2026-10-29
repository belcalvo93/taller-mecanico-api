# Design

## Context

- Estado actual (main tras PR #13): `app/core/` tiene `config.py` y `database.py` (`crear_motor`, `crear_fabrica_sesiones` con `expire_on_commit=False`, `get_session` que toma la fábrica de `app.state` y cierra la sesión al terminar, `ahora_utc()`). No existen `repository.py`, `unit_of_work.py` ni `paginacion.py`.
- La sesión es la `AsyncSession` de SQLModel (`sqlmodel.ext.asyncio.session`), con `exec()` además de `execute()`. Versiones instaladas en el equipo (bitácora): SQLModel 0.0.48 y SQLAlchemy 2.1.x; los pisos de `requirements.txt` son 0.0.24 y 2.0.
- Los 13 modelos de CH-02 ya están: todas las relaciones con `lazy="raise"` (D5 de CH-02); `vehiculo` y `repuesto` tienen `borrado_en timestamptz NULL`; `estado_orden` tiene PK `codigo` (no `id`).
- Tests: `tests/conftest.py` ya ofrece `base_migrada` (`alembic upgrade head` sobre `taller_test`), `motor` (uno por test, `dispose()` al final) y `conexion` (transacción revertida). `test_modelos.py` exige que `SQLModel.metadata` tenga **exactamente** las 13 tablas, y `test_migraciones.py` corre `alembic check`. Cualquier modelo de prueba que se registre en `SQLModel.metadata` o que deje una tabla en `public` rompe esos dos tests.
- `seed.py` confirma con `session.begin()` (fuera de la API; no es parte de "sólo el UoW confirma", que rige para `app/` y `main.py`).

## Goals / Non-Goals

**Goals:**
- Firmas públicas estables para que CH-04..CH-08 hereden sin tocar el núcleo.
- Que todo lo genérico se pruebe contra PostgreSQL real sin tocar el esquema de la app ni `SQLModel.metadata`.
- Que una petición de página inexistente nunca llegue a 500 aunque un router se olvide de traducirla.

**Non-Goals:**
- Repositorios/UoW concretos, el repositorio del catálogo (CH-08), la traducción de `IntegrityError` → 409 (la hace cada router con el nombre de la restricción de D3 de CH-02) y el punto único de escritura de stock (CH-07).
- Filtros genéricos por diccionario o "query builders": cada repositorio concreto arma su `select` con parámetros ligados.

## Decisions

### D1 — `BaseRepository[T]`: firma y semántica
```python
T = TypeVar("T", bound=SQLModel)

class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, modelo: type[T]) -> None
    async def get_by_id(self, id: Any) -> T | None
    async def get_all(self, *, offset: int = 0, limit: int | None = None) -> list[T]
    async def count(self) -> int
    async def add(self, entidad: T) -> T              # session.add + flush; devuelve la misma instancia con PK
    async def update(self, entidad: T, cambios: Mapping[str, Any] | None = None) -> T  # setattr + flush
    async def delete(self, entidad: T) -> None        # session.delete + flush
    def _consulta_base(self) -> Select              # select(modelo); punto de extensión de los filtros
    async def _paginar(self, consulta: Select, pagina: ParametrosPagina) -> Pagina[T]
```
- **Clave primaria por introspección** (`sqlalchemy.inspect(modelo).primary_key`), y `get_by_id` con `select(...).where(pk == id)` sobre `_consulta_base()`, **no** con `session.get()`: `session.get` devuelve lo que haya en el identity map sin aplicar filtros, y `SoftDeleteRepository` necesita que el filtro de `borrado_en` se aplique siempre. Sólo PK simple (todas las tablas con repositorio genérico tienen `id`); con PK compuesta el constructor falla.
- `get_all` ordena por la PK: sin `ORDER BY` el desplazamiento no es estable y la paginación repetiría o salteará filas.
- `update(entidad, cambios)` aplica sólo las claves recibidas: el servicio le pasa `datos.model_dump(exclude_unset=True)` del PATCH (regla 16). Rechaza (`ValueError`) una clave que no es columna del modelo, para que un error de programación no quede como atributo suelto. Sin `cambios`, sólo sincroniza lo que el servicio ya modificó en la entidad.
- `delete` también hace `flush()` (la consigna lo pide para `add`/`update`; se extiende para que un borrado que viola una FK falle dentro del bloque y no recién al confirmar).
- `_consulta_base` y `_paginar` son "protegidos" (prefijo `_`): los usan las subclases para armar métodos con nombre propio (`buscar_por_descripcion`, `listar_de_cliente`…), que es lo que pide la consigna ("métodos que se nombran por lo que traen").
- **Alternativa descartada**: `get_all(**filtros)` genérico por igualdad. No cubre `ILIKE` ni joins, invita a armar SQL desde nombres que vienen de afuera y duplica lo que `select()` ya expresa.

### D2 — `SoftDeleteRepository[T]`
- Hereda y redefine `_consulta_base()` como `select(modelo).where(modelo.borrado_en.is_(None))`. Como `get_by_id`, `get_all`, `count` y `_paginar` parten de `_consulta_base()`, el filtro aplica a todas sin repetirlo.
- `get_by_id_including_deleted(id)` usa `select(modelo)` sin el filtro.
- `soft_delete(entidad)`: si `borrado_en` es nulo lo pone en `ahora_utc()`; si ya tenía valor no lo pisa (se conserva la fecha de la primera baja). Luego `flush()`.
- El constructor verifica que el modelo tenga la columna `borrado_en` y si no lanza `TypeError` (un error de programación detectado al construir y no en la primera consulta).
- Lo usan `VehiculoRepository` (CH-06) y `RepuestoRepository` (CH-07); CH-08 llama a `get_by_id_including_deleted` al terminar una orden con un repuesto dado de baja (DD-14).

### D3 — Precarga
- Los métodos genéricos no aceptan ni aplican opciones de carga. Un método concreto declara `options(selectinload(...))` (colecciones) o `joinedload(...)` (muchos-a-uno) adentro, sobre `self._consulta_base()`. Con `lazy="raise"` en los modelos, olvidarse una precarga falla en el test en vez de generar N+1.
- Alternativa descartada: `get_by_id(id, *opciones)`. Deja que el servicio decida qué cargar (la consigna lo pone en el repositorio) y oculta la intención en la llamada.

### D4 — `UnitOfWork` base
```python
class UnitOfWork:
    def __init__(self, session: AsyncSession) -> None
    async def __aenter__(self) -> Self
    async def __aexit__(self, tipo, exc, tb) -> None   # devuelve None/False: nunca suprime
```
- `__aexit__` sin excepción → `await session.commit()`; si el commit falla → `await session.rollback()` y se relanza. Con excepción → `await session.rollback()` y la excepción sigue su camino. **Nunca** `session.close()`: la cierra `get_session` (spec `ciclo-de-vida`).
- No hay método `commit()` público: confirmar es salir del bloque. Así un servicio no puede confirmar a mitad de una operación (RN-02/RN-13/RN-20 en un solo bloque).
- Patrón para los UoW concretos (docstring del módulo y test con un UoW de prueba):
  ```python
  class ClientesUoW(UnitOfWork):
      def __init__(self, session):
          super().__init__(session)
          self.clientes = ClienteRepository(session)
          self.vehiculos = VehiculoRepository(session)

  def get_clientes_uow(session: AsyncSession = Depends(get_session)) -> ClientesUoW:
      return ClientesUoW(session)          # el router lo construye

  async def crear_vehiculo(uow: ClientesUoW, datos):  # el servicio lo abre
      async with uow:
          ...
  ```
  La dependencia vive en el `router.py` o `unit_of_work.py` de cada módulo; el núcleo no ofrece una genérica porque cada módulo devuelve su propia clase.
- Reentrada (abrir el mismo UoW dos veces anidado) no se soporta ni se prueba; abrirlo dos veces **seguidas** sí (segundo bloque = nueva transacción).

### D5 — Paginación (`app/core/paginacion.py`)
- `ParametrosPagina` (modelo Pydantic `page: int = Field(1, ge=1)`, `size: int = Field(20, ge=1, le=100)`) y una dependencia `parametros_pagina(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100))` que lo construye. FastAPI devuelve 422 por sí solo con valores fuera de rango o no enteros, sin ejecutar el handler.
- `Pagina[T]` (genérico Pydantic) con exactamente `items: list[T]`, `total`, `page`, `size`, `pages`. Los routers declaran `response_model=Pagina[RepuestoLeer]`; el repositorio devuelve `Pagina[Modelo]` y el router/servicio la convierte (`Pagina[Schema].model_validate(..., from_attributes=True)`), para que nunca salga un campo como `password_hash`.
- `calcular_paginas(total, size) = max(1, ceil(total / size))` (función pura).
- `PaginaInexistente(Exception)` con `page`, `pages` y mensaje `"La página {page} no existe: hay {pages}"`.
- `_paginar` (D1): 1) `total = SELECT count(*) FROM (consulta sin ORDER BY) AS sub`; 2) `pages = calcular_paginas(total, size)`; 3) si `page > pages` lanza `PaginaInexistente` **sin** pedir los ítems; 4) ítems con `consulta.order_by(pk)` (si la consulta no trae orden propio) `.offset((page-1)*size).limit(size)`. El conteo y los ítems salen de la **misma** `consulta`, que es lo que garantiza "total con los mismos filtros" (C-16).
- **Manejador**: `paginacion.py` expone `async def responder_pagina_inexistente(request, exc) -> JSONResponse` (422, `{"detail": exc.mensaje}`), y `main.py` lo registra con `app.add_exception_handler(PaginaInexistente, responder_pagina_inexistente)`. Así ningún listado termina en 500 por esto aunque el router no la traduzca (RN-18).
- **Alternativa descartada**: lanzar `HTTPException(422)` desde el repositorio. Mete HTTP en la capa de datos y rompe "cada capa sabe lo suyo".

### D6 — Modelos y esquema de prueba
- `tests/nucleo_modelos.py`: una base propia `class BasePrueba(SQLModel, registry=registry())` con su `MetaData(schema="nucleo_prueba")` y dos modelos mínimos:
  - `CosaPrueba` (`id`, `nombre` con UNIQUE, `etiqueta` para filtrar, `borrado_en timestamptz NULL`) — sirve para el genérico y para el de borrado lógico.
  - `DetallePrueba` (`id`, `cosa_id` FK con índice, `texto`, y un `codigo` con UNIQUE **DEFERRABLE INITIALLY DEFERRED** para probar la falla al confirmar) con relación `CosaPrueba.detalles` ↔ `DetallePrueba.cosa` con `lazy="raise"`.
- Fixture `esquema_nucleo` (sesión de pytest-asyncio por test, como `motor`): `DROP SCHEMA IF EXISTS nucleo_prueba CASCADE; CREATE SCHEMA nucleo_prueba;` y crea las dos tablas con `CreateTable` de **esa** metadata; al terminar, `DROP SCHEMA ... CASCADE`. Fixture `sesiones` = `crear_fabrica_sesiones(motor)` (la fábrica real de la app, para heredar `expire_on_commit=False`).
- Por qué un esquema aparte y no `public`: `alembic check` (autogenerate) sólo compara el esquema por defecto, así que una tabla de prueba que quedara colgada por un test abortado no lo rompe; y `DROP SCHEMA ... CASCADE` limpia todo de una vez.
- Por qué no `CREATE TEMP TABLE`: vive en una sola conexión y los tests de commit necesitan ver la fila desde **otra** sesión/conexión.
- Esto no viola "nunca `create_all`": el esquema **de la app** sigue saliendo sólo de Alembic; la metadata de prueba no es `SQLModel.metadata` y no tiene ninguna de las 13 tablas. Coincide con lo que CH-02 dejó acordado (su D13).
- Los tests de "nadie confirma" y "sólo el UoW confirma" son de texto (búsqueda de `.commit(` en `app/` y `main.py`) como el de `create_all` de CH-02.

### D7 — Organización de los tests
- `tests/test_paginacion.py`: funciones puras (`calcular_paginas`, mensaje de `PaginaInexistente`) sin base; parámetros y manejador con una mini `FastAPI()` de prueba montada en el test (no se agregan rutas a la app real).
- `tests/test_repository.py`: contra `taller_test` + `esquema_nucleo`. Para "sin consultas al acceder a una relación" y "número fijo de consultas" se cuenta con un listener `before_cursor_execute` sobre `motor.sync_engine` (mismo recurso que usó CH-02).
- `tests/test_unit_of_work.py`: bloque OK, excepción, `IntegrityError` en flush, falla en commit (UNIQUE diferido), sesión abierta después; y una mini `FastAPI()` con `lifespan` que guarda `session_factory` en `app.state`, ruta que recibe un UoW de prueba por `Depends` y un servicio que lo abre.

## Decisiones a confirmar por Elías (governance ALTO)

Son decisiones que fijan contrato con la ola 2; están tomadas así en specs y tareas, pero conviene confirmarlas antes del apply:

1. **`main.py` registra el manejador de `PaginaInexistente`** (D5). CHANGES.md dice "sólo `app/core/`"; es una línea y evita 500. Alternativa: que cada router la traduzca (más repetición, riesgo de olvido).
2. **`pages` = 1 con cero resultados** (no 0). Sale de "con cero resultados hay una página, vacía"; implica que `page=2` sin resultados da 422 ("hay 1").
3. **`update(entidad, cambios)`** recibe el diccionario del PATCH (`exclude_unset`) y rechaza claves que no son columnas (D1).
4. **`delete` hace `flush()`** igual que `add`/`update` (D1).
5. **`soft_delete` repetido conserva la primera fecha** (D2), en lugar de pisarla o lanzar error.
6. **Esquema `nucleo_prueba` dentro de `taller_test`** para los modelos de prueba (D6). Avisarle a Belén en la revisión del PR (lo acordado en su D13 decía "MetaData propia"; esto lo cumple y suma el esquema aparte).
7. **Mensaje de 422** como `{"detail": "La página 3 no existe: hay 2"}` (mismo formato que un `HTTPException`); los 422 del contrato quedan con el formato estándar de FastAPI (`detail` como lista).

## Risks / Trade-offs

- [`class X(SQLModel, registry=registry())` puede comportarse distinto entre SQLModel 0.0.24 y 0.0.48] → Se prueba primero (tarea 1.x) que los modelos de prueba no aparecen en `SQLModel.metadata`; si el registro propio falla, plan B: declarar las dos tablas con `Table(...)` de SQLAlchemy Core sobre la `MetaData` propia y mapearlas imperativamente con ese registro.
- [Una consulta paginada con `joinedload` de una colección multiplica filas y el `total` saldría inflado] → Convención documentada en el docstring de `_paginar`: recibe consultas de una fila por entidad, y las colecciones se precargan con `selectinload` (consulta aparte, no multiplica filas).
- [Generics de Pydantic `Pagina[T]` con modelos SQLModel `table=True` como `T`] → El repositorio devuelve `Pagina[Modelo]` con `arbitrary_types_allowed` o, más simple, un `dataclass` interno; el router valida contra `Pagina[Schema]`. Se decide en el apply con el test de forma del envoltorio, sin cambiar la spec.
- [Tests de commit dejan filas] → Todo vive en `nucleo_prueba`, que se borra con `CASCADE` al final de cada test.
- [Un servicio podría capturar una excepción dentro del `async with` y seguir] → Es su decisión explícita; el UoW confirma lo que haya. Se documenta en el docstring.

## Migration Plan

No hay migraciones ni cambios de esquema de la app. Despliegue = merge del PR a `main`; rollback = revert del PR (ningún otro change depende todavía del código). Después del merge se avisa a Hernán, Joaquín y Bruno de las firmas de D1, D2, D4 y D5.

## Open Questions

- Nombre exacto de la dependencia de paginación en los routers (`parametros_pagina` vs. `Depends(ParametrosPagina)`): se puede ajustar en el apply sin tocar specs ni tareas.
