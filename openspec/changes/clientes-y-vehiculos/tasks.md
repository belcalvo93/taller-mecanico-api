# Tasks

> TDD estricto en cada tarea: **ROJO** (escribir primero el test, ejecutarlo y ver que falla por la razón esperada) → **VERDE** (código mínimo) → **TRIANGULAR** (otro caso con datos distintos) → **REFACTOR** (suite verde tras cada paso). Cada escenario de la spec tiene al menos un test.
> Tests en `tests/` contra `taller_test` (la fija `tests/conftest.py`). Comando: `python -m pytest` desde la raíz.
> Sin líneas de coautoría ni de sesión en los commits. El `.env` no se versiona.

## 0. Red de seguridad

- [x] 0.1 Correr la suite de `main` y anotar la línea base (263 passed; al cerrar: 403 passed)
- [x] 0.2 Confirmar qué falta en `main` para este change: núcleo de CH-03 y T1 de CH-04 (design D1)

## 1. Núcleo provisorio (commit aparte, se descarta al mergear CH-03 y la T1 de CH-04)

- [x] 1.1 ROJO→VERDE `tests/test_nucleo_provisorio.py`: `add` hace flush sin commit (otra sesión no ve la fila); `get_by_id` inexistente → `None`; `SoftDeleteRepository.get_by_id` excluye dados de baja y `get_by_id_including_deleted` no; `soft_delete` escribe `borrado_en`
- [x] 1.2 ROJO→VERDE UoW: confirma al salir, revierte con excepción y relanza, no cierra la sesión
- [x] 1.3 ROJO→VERDE dependencias: sin cookie → 401; token con firma inválida → 401; `requiere_rol` con rol vigente pasa, sin rol → 403, rol revocado o vencido → 403
- [x] 1.4 Commit: `chore(clientes-y-vehiculos): núcleo y dependencias PROVISORIOS hasta mergear CH-03 y T1 de CH-04`

## 2. `ClienteRepository` (T1, DD-13)

- [x] 2.1 ROJO→VERDE `ClienteRepository(session)` hereda de `BaseRepository[Cliente]`; `add` + `get_by_id` con un cliente nuevo
- [x] 2.2 ROJO→VERDE `get_con_vehiculos_vigentes(id)`: trae los vehículos vigentes precargados, excluye los dados de baja, `None` si no existe; TRIANGULAR: 2 consultas con 2 vehículos y con 5 (sin N+1); acceder a la relación sin precargar sigue prohibido
- [x] 2.3 Commit: `feat(clientes-y-vehiculos): ClienteRepository (DD-13)`

## 3. `VehiculoRepository` y UoW del módulo

- [x] 3.1 ROJO→VERDE `VehiculoRepository(session)` hereda de `SoftDeleteRepository[Vehiculo]`
- [x] 3.2 ROJO→VERDE `tiene_ordenes_abiertas`: sin órdenes → falso; PENDIENTE → verdadero; EN_REPARACION → verdadero; TRIANGULAR: sólo TERMINADA y CANCELADA → falso
- [x] 3.3 ROJO→VERDE `listar_vigentes_de_usuario(usuario_id)`: los de Laura, no los de Jorge, sin los dados de baja, `[]` para un usuario sin ficha
- [x] 3.4 ROJO→VERDE `ClientesUnitOfWork(session)`: `clientes` y `vehiculos` comparten la sesión del UoW

## 4. Contratos

- [x] 4.1 ROJO→VERDE `ClienteCrear`: `extra="forbid"` (rechaza `usuario_id`), textos vacíos/solo espacios → error, `strip`, largo máximo, NUL rechazado
- [x] 4.2 ROJO→VERDE `VehiculoCrear`: `anio` 1949/2101 rechazados y 1950/2100 aceptados; patente normalizada a mayúsculas sin espacios; patente inválida rechazada
- [x] 4.3 Salidas sin `borrado_en`

## 5. Servicio y rutas (TDD por endpoint, contra la app con el seed)

- [x] 5.1 ROJO→VERDE `POST /clientes`: 201; 422 por campo extra y por vacío; documento repetido (también con espacios) → 409 con mensaje propio y sin texto de la base, sin fila nueva
- [x] 5.2 ROJO→VERDE `GET /clientes/{id}`: 200 con los vehículos de Laura ordenados; 404 inexistente; vehículo dado de baja no aparece
- [x] 5.3 ROJO→VERDE `POST /clientes/{id}/vehiculos`: 201; 404 cliente inexistente (aunque la patente esté repetida); 409 patente vigente repetida (de otro cliente); 422 por año 1949/2101; 201 en 1950/2100
- [x] 5.4 ROJO→VERDE `DELETE /vehiculos/{id}`: 204 sin cuerpo y `borrado_en` escrito; 404 inexistente y ya dado de baja; 409 con orden PENDIENTE (vehículo 1) y EN_REPARACION (vehículo 3) y `borrado_en` sigue nulo; 204 con órdenes sólo finales
- [x] 5.5 ROJO→VERDE C-19 completo: baja del vehículo 2 → 204; `AC456EF` para Jorge → 201; otra vez `AC456EF` → 409
- [x] 5.6 ROJO→VERDE `GET /mis-vehiculos`: Laura ve sólo los suyos; personal sin ficha → `[]`; el dado de baja no aparece
- [x] 5.7 ROJO→VERDE permisos: sin cookie → 401 en las cinco rutas (con la dependencia real); MECANICO y CLIENTE → 403 en las cuatro de personal; ADMIN y RECEPCION pasan
- [x] 5.8 ROJO→VERDE C-01 y RN-18: id no entero → 422 sin ejecutar el servicio; id 3000000000 → 422; NUL en un texto → 422
- [x] 5.9 Registrar el router en el grupo protegido de `main.py` (una línea, la de CH-06) y ajustar `tests/test_grupos_de_rutas.py` (design D10)
- [x] 5.10 Commits: `feat(clientes-y-vehiculos): ...` por capa, cada uno con sus tests

## 6. Caso C-19 y cierre

- [x] 6.1 `test/C-19_baja_y_reuso_de_patente.http` con la respuesta esperada en un comentario y el login de recepción (`# @name`)
- [x] 6.2 Correrlo contra el servidor real (`alembic upgrade head`, `python seed.py`, `uvicorn`) — con la autenticación provisoria
- [x] 6.3 Suite completa verde y comparación con la línea base
- [x] 6.4 Verificar contra RN-01, RN-16, RN-17, RN-18, C-01 (parte) y C-19, y contra las reglas 6, 13, 14, 16 y 17 de `CLAUDE.md`
- [x] 6.5 `docs/bitacora.md` (sección Joaquín): qué se le pidió al agente, qué se corrigió a mano y por qué
- [x] 6.6 `git status` sin `.env` ni archivos fuera del alcance

## Workflow follow-up

- PR `feat/clientes-y-vehiculos` → `main` con `Closes #6`, revisión de un compañero (ideal: Hernán, por DD-13 y las dependencias).
- Si CH-03 o la T1 de CH-04 ya están en `main`: `git rebase -i main` y descartar el commit provisorio antes de abrir el PR.
- Tras el merge: `/opsx:archive clientes-y-vehiculos` y marcar CH-06 en `CHANGES.md`.
