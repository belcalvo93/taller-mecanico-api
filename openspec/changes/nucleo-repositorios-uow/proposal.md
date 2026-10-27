# Proposal

## Why

Los cuatro changes de la ola 2 (CH-04 a CH-07) y `ordenes` (CH-08) escriben sus repositorios y Unit of Work concretos encima de un núcleo común que todavía no existe: sin él, cada módulo repetiría el CRUD, decidiría por su cuenta dónde se confirma la transacción y armaría su propio envoltorio de listados. El Ejercicio 6 de la consigna (20 %) evalúa exactamente ese núcleo —dos jerarquías de repositorios, la clase del modelo en el constructor, `flush` y nunca `commit`, quién crea/abre/confirma/cierra— y el Ejercicio 3 fija el envoltorio y las reglas de paginación. CH-03 es la mitad de la ola 1 (DD-12) y su cierre, junto con CH-02, abre el GATE 2.

## What Changes

- `app/core/repository.py` (nuevo):
  - `BaseRepository[T]`, que recibe en el constructor la sesión y **la clase del modelo**, y ofrece `get_by_id`, `get_all`, `count`, `add`, `update` y `delete`. Las escrituras hacen `flush()` y **nunca** `commit()`. Suma un listado paginado protegido que cuenta `total` con la misma consulta (los mismos filtros) que trae la página.
  - `SoftDeleteRepository[T]`, que hereda de `BaseRepository[T]`, excluye en todas las lecturas heredadas las filas con `borrado_en` no nulo y suma `get_by_id_including_deleted` y `soft_delete`.
  - Convención de precarga: los métodos genéricos no precargan nada; cada método de un repositorio concreto que necesita una relación declara su carga anticipada adentro. La carga perezosa está prohibida (los modelos de CH-02 ya tienen `lazy="raise"`).
- `app/core/unit_of_work.py` (nuevo): `UnitOfWork` base como gestor de contexto async que recibe la sesión. Confirma al salir del bloque sin error, revierte si sale con una excepción (y la deja propagar) y **no cierra la sesión**. Es el único lugar del código con `commit()`. Se documenta el patrón para los UoW concretos (todos sus repositorios con la misma sesión) y la dependencia con la que el router lo construye; el servicio lo abre con `async with` y nunca lo construye.
- `app/core/paginacion.py` (nuevo): parámetros `page` (≥ 1, por defecto 1) y `size` (1..100, por defecto 20) validados en el contrato (422), envoltorio `{items, total, page, size, pages}`, cálculo de `pages` (cero resultados = una página vacía) y error de página inexistente con mensaje propio (`"La página 3 no existe: hay 2"`) que la API responde como 422.
- `main.py`: registro del manejador del error de página inexistente (una línea), para que ningún listado termine en 500 (RN-18). Ver la pregunta abierta en `design.md`.
- `tests/`: modelos mínimos de prueba declarados sobre una metadata **propia** (no `SQLModel.metadata`) en un esquema de PostgreSQL aparte dentro de `taller_test`, y los tests del núcleo contra la base real (nunca `create_all` del esquema de la app; DD-12, D13 de CH-02).
- Fuera de alcance: los repositorios y UoW concretos de cada módulo (los escribe el change del módulo), el repositorio de sólo lectura del catálogo `estado_orden` (CH-08; sólo se garantiza que no necesita heredar de `BaseRepository`), la traducción de `IntegrityError` a 409 (la hace el router de cada módulo), endpoints y archivos `.http`.

## Capabilities

### New Capabilities
- `repositorios`: acceso genérico a datos — `BaseRepository[T]` y `SoftDeleteRepository[T]`, escrituras con `flush` sin confirmar, filtro de los dados de baja, listado paginado con el mismo filtro para `total` y los ítems, y la convención de precarga declarada en el método.
- `unidad-de-trabajo`: límite transaccional de cada operación — confirma, revierte, no cierra la sesión, único punto de `commit`, y quién lo construye (router) y quién lo abre (servicio).
- `paginacion`: contrato de los listados — parámetros `page`/`size`, envoltorio estándar, cálculo de páginas y 422 por página inexistente.

### Modified Capabilities
<!-- Ninguna: `ciclo-de-vida` ya fija la sesión por petición con expire_on_commit=False y su cierre; este change la usa sin cambiar sus requisitos. -->

## Impact

- **Código nuevo**: `app/core/repository.py`, `app/core/unit_of_work.py`, `app/core/paginacion.py`; una línea en `main.py` (manejador del 422 de paginación).
- **Tests nuevos**: `tests/nucleo_modelos.py` (modelos mínimos de prueba), `tests/test_repository.py`, `tests/test_unit_of_work.py`, `tests/test_paginacion.py`, y fixtures en `tests/conftest.py` para el esquema de prueba.
- **Dependencias**: ninguna nueva. Usa `get_session`/`crear_fabrica_sesiones` de CH-01 y `ahora_utc` de `app/core/database.py` (CH-02).
- **Habilita**: CH-04, CH-05, CH-06, CH-07 y CH-08 (heredan de estos repositorios, componen sus UoW sobre el base y devuelven el envoltorio de paginación). Las firmas públicas fijadas acá son un contrato con esos changes.
- **Governance**: ALTO (CHANGES.md): de este núcleo dependen todos los módulos y fija dónde se hace el commit. Las decisiones no obvias quedan como preguntas abiertas en `design.md` para que Elías las confirme antes del apply.
