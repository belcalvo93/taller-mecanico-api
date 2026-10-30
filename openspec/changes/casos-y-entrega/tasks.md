# Tasks

Governance BAJO: consolidación y documentación, sin lógica nueva. No se reescriben `.http` ni código de los compañeros (cada falla se lista con caso y dueño), no se hacen commits y no se agregan líneas de atribución. Strict TDD no aplica porque no hay código de producción; cada tarea declara cómo se verifica.

## FASE A (ahora, con CH-01..CH-07 en `main`)

## 1. Estado de partida y entorno

- [x] 1.1 Confirmar la rama `feat/casos-y-entrega`, que `main` tiene los merges de CH-01..CH-07 y que CH-08 todavía no está; verificar con `git branch --show-current` y `git log --oneline main`
- [x] 1.2 Confirmar que PostgreSQL responde y que existen las bases `taller` y `taller_test` y el usuario `taller`; verificar con `pg_isready` y `psql -l`
- [x] 1.3 Aplicar `alembic upgrade head` sobre `taller`, y probar `alembic downgrade base` + `alembic upgrade head`; verificar que los tres comandos terminan sin error (queda como evidencia para el README)
- [x] 1.4 Crear `docs/evidencias/` con el esqueleto de `resultados-fase-a.md` (tabla: caso, archivo, esperado, obtenido, resultado, dueño si falla); verificar que el archivo existe

## 2. Casos `.http` disponibles (C-01..C-05, C-07, C-08, C-09, C-16, C-18, C-19)

- [x] 2.1 Verificar que cada uno de los 11 archivos existe en `test/` y tiene la respuesta esperada en un comentario por pedido; verificar con una lista archivo → cantidad de `# Esperado:` y anotar cualquier archivo sin comentario
- [x] 2.2 Escribir en el directorio temporal de la sesión (fuera del repo) el script que ejecuta un `.http` con `httpx` (separa por `###`, resuelve `{{base}}` y `{{nombre.response.headers.Set-Cookie}}`, respeta `# @no-cookie-jar`); verificar con C-01, que debe dar lo que dice su comentario
- [x] 2.3 Levantar el servidor con `uvicorn main:app` y correr `python seed.py` antes de cada archivo, ejecutar C-01 a C-05 y anotar el resultado de cada pedido en `resultados-fase-a.md`; verificar que cada fila tiene esperado y obtenido
- [x] 2.4 Ejecutar C-07, C-08 y C-09 (varias sesiones a la vez con `# @name`), con `python seed.py` antes de cada uno, y anotar los resultados; verificar que cada fila está completa
- [x] 2.5 Ejecutar C-16, C-18 y C-19, con `python seed.py` antes de cada uno, y anotar los resultados; verificar que cada fila está completa
- [x] 2.6 Marcar para confirmar a mano con REST Client los casos cuyo resultado depende del tiempo (C-04 tiempo parecido, C-05 sexto intento en pocos milisegundos); verificar que quedan señalados en el registro
- [x] 2.7 Registrar cada fallo con el caso, lo esperado, lo obtenido y el dueño según `CHANGES.md` (C-01..C-05 Hernán, C-07..C-09 Hernán (CH-05), C-16 y C-18 Bruno, C-19 Joaquín); verificar que no se modificó ningún archivo de `test/` con `git status --short test/`
- [x] 2.8 Agregar al registro las filas de C-06, C-10, C-11, C-12, C-13, C-15 y C-17 como "pendiente de CH-08"; verificar que las 19 filas (C-01..C-19) están en la tabla

## 3. Evidencia de C-14 (captura de psql)

- [x] 3.1 Con la base migrada y `python seed.py`, anotar los conteos de `historial_estado_orden`, `movimiento_stock` e `historial_precio_repuesto`; verificar que el seed los dejó con filas
- [x] 3.2 Ejecutar `psql -U taller -d taller -f test/solo_agregado.sql` y guardar la salida en `docs/evidencias/C-14_salida_psql.txt`; verificar que muestra siete errores (seis "es de sólo agregado" y uno por la FK `fk_orden_trabajo_estado_estado_orden`)
- [x] 3.3 Volver a contar las tres tablas; verificar que los conteos no cambiaron
- [x] 3.4 Dejar en `docs/evidencias/C-14_salida_psql.txt` el comando exacto para repetirlo, de modo que Belén saque la captura de pantalla; verificar que está el comando y que la captura queda anotada como pendiente de Belén

## 4. README y checklist de entrega

- [x] 4.1 Reescribir `README.md` con los pasos desde cero: requisitos (Python 3.12+, PostgreSQL 16+), venv, `pip install -r requirements.txt`, creación del usuario y de las bases `taller` y `taller_test`, `env.example` → `.env`, tabla de variables, generación única de `JWT_SECRET_KEY`, `alembic upgrade head` y `downgrade base` + `upgrade head`, `python seed.py`, servidor, `SQL_ECHO=true`; verificar que cada comando se corre desde la raíz del repo
- [x] 4.2 Agregar al README la explicación de `tests/` (pytest, `taller_test`, queda vacía) contra `test/` (`.http` y `solo_agregado.sql`), cómo correr la suite, cómo correr los `.http` con `python seed.py` antes de cada uno y cómo sacar la evidencia de C-14 y C-15; verificar que esas secciones existen y enlazan a `docs/evidencias/`
- [x] 4.3 Probar los comandos del README sobre una base descartable `taller_readme` (usuario, `.env` temporal, `alembic upgrade head`, `python seed.py`, `GET /health/live` = 200) y borrarla al terminar; verificar la respuesta 200 y que `taller` y el `.env` real no cambiaron
- [x] 4.4 Revisar el checklist de entrega: `requirements.txt`, `env.example` (sin secretos), `alembic.ini` (sin URL ni contraseña), `migrations/versions/` con 2 versiones y comentario de lectura, `test/`, `.env` ignorado y no versionado, ningún secreto en `git ls-files`; verificar con `git ls-files`, `git check-ignore .env` y una búsqueda de credenciales, y anotar el resultado de cada ítem en `resultados-fase-a.md`
- [x] 4.5 Listar los hallazgos del checklist con archivo y dueño (por ejemplo, si algo falta o difiere de la consigna) sin corregir código ajeno; verificar que cada hallazgo tiene dueño

## 5. Bitácora y suite

- [x] 5.1 Revisar `docs/bitacora.md`: una sección por integrante (Belén, Elías, Hernán, Bruno, Joaquín) y en cada entrada fecha, qué pidió al agente y qué corrigió a mano y por qué; verificar con una tabla integrante → entradas y anotar las faltantes (por ejemplo CH-08 de Elías) a su nombre
- [x] 5.2 Pasar la lista "Pendientes para CH-09" de la bitácora al README y reemplazarla por una entrada de Belén para CH-09 (fecha, qué pidió al agente, qué corrigió a mano); verificar que cada pendiente figura en el README
- [x] 5.3 Correr la suite `pytest` completa sobre `taller_test` creada con `alembic upgrade head` y anotar cantidad de tests y resultado; verificar que está en verde y que `taller_test` queda vacía
- [x] 5.4 Cerrar `resultados-fase-a.md` con un resumen (casos aprobados, fallados con dueño, pendientes de CH-08, hallazgos del checklist, suite); verificar que el resumen suma 19 casos

## FASE B (cuando CH-08 esté mergeado en `main`)

## 6. Casos de órdenes

- [ ] 6.1 Actualizar la rama con `main` (CH-08 incluido) y confirmar que `ordenes` está activa en `main.py`; verificar con `git log --oneline` y `GET /openapi.json`
- [ ] 6.2 Verificar que existen en `test/` los `.http` de C-06, C-10, C-11, C-12, C-13 y C-17 con su respuesta esperada en comentario; si falta alguno, listarlo con el dueño (Elías) sin escribirlo
- [ ] 6.3 Correr cada uno con `python seed.py` antes (C-12 y C-13 dependen de reponer y terminar la orden 2) y anotar los resultados en `resultados-fase-b.md`; verificar las 6 filas con esperado y obtenido
- [ ] 6.4 Correr de nuevo la suite `pytest` completa y anotar el resultado; verificar que está en verde

## 7. Evidencia de C-15 y corrida completa

- [ ] 7.1 Levantar el servidor con `SQL_ECHO=true`, crear con los endpoints reales una orden de 2 ítems y otra de 4, pedir el detalle de cada una y guardar los dos fragmentos de consola en `docs/evidencias/C-15_consola.txt`; verificar que cuentan las mismas consultas
- [ ] 7.2 Correr de nuevo C-01 a C-19 completos, cada uno con `python seed.py` antes, y consolidar las 19 filas en `resultados-fase-b.md`; verificar que ningún caso queda "pendiente"
- [ ] 7.3 Repetir `solo_agregado.sql` con la base de la corrida final; verificar que sigue dando siete errores

## 8. Verificación final y archivado

- [ ] 8.1 Recorrer RN-01..RN-20 contra el código y su evidencia (test, caso C o consulta) en `docs/evidencias/verificacion-rn.md` (RN-15 con C-14; RN-19 y el diseño sin N+1 con C-15); verificar las 20 filas y listar los hallazgos con dueño
- [ ] 8.2 Revisar que cada PR de los cinco integrantes tiene su aprobación (evidencia para la demo, AP-07) con `gh pr list --state merged` y anotar los que no; verificar que cada PR figura en el registro
- [ ] 8.3 Archivar `autorizacion-y-roles` con `/opsx:archive`; verificar que pasa a `openspec/changes/archive/` y sus specs se sincronizan en `openspec/specs/`
- [ ] 8.4 Archivar `repuestos-y-stock` con `/opsx:archive`; verificar lo mismo
- [ ] 8.5 Archivar `ordenes` con `/opsx:archive`; verificar lo mismo
- [ ] 8.6 Actualizar la bitácora de Belén y marcar CH-09 como hecho en `CHANGES.md` (campo Estado); verificar que `openspec list` ya no muestra changes pendientes salvo este

## Workflow follow-up

- Abrir el PR de `feat/casos-y-entrega` a `main` con `Closes #9` y la aprobación de un compañero.
- Tras el merge, archivar este change con `/opsx:archive casos-y-entrega`.
- Belén saca la captura de pantalla de psql (C-14) y la del detalle con 2 y 4 ítems (C-15) para adjuntar a la entrega.
