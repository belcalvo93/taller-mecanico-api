# Proposal

## Why

La entrega es el viernes 30/10 y el repositorio todavía no tiene lo que la consigna exige para corregirlo: el `README.md` es un placeholder de 9 líneas, no hay evidencia de C-14 ni de C-15, los casos `.http` escritos por cada integrante nunca se corrieron todos juntos contra una base recién sembrada, y la bitácora y los checks de `requirements.txt`, `env.example`, `alembic.ini` y `migrations/` no se revisaron de punta a punta. Un proyecto que no levanta desde cero o que lleva credenciales no se corrige, así que este change cierra la entrega.

CH-08 (`ordenes`) todavía no está en `main`, y de ella dependen C-06, C-10 a C-13, C-15 y C-17. Por eso el change se hace en **dos fases**: la Fase A se ejecuta ya con lo que está mergeado (CH-01 a CH-07) y la Fase B queda planificada para cuando entre CH-08.

## What Changes

**Fase A (ahora, sobre CH-01..CH-07):**
- Verificar que existen los `.http` de C-01 a C-05, C-07, C-08, C-09, C-16, C-18 y C-19 y `test/solo_agregado.sql` (C-14), correrlos contra el servidor después de `python seed.py` y anotar el resultado de cada uno (esperado vs. obtenido).
- Preparar la evidencia de C-14: guion de psql y salida con los siete rechazos (seis del disparador y uno de la clave foránea), listo para que Belén saque la captura.
- Reescribir `README.md` con los pasos desde cero: venv, dependencias, usuario y bases `taller` y `taller_test`, `env.example` → `.env`, generación única de `JWT_SECRET_KEY`, `alembic upgrade head` (más `downgrade base` y `upgrade head`), `python seed.py`, servidor, `SQL_ECHO`, `tests/` contra `test/` y cómo correr la suite.
- Checklist de entrega: `requirements.txt`, `env.example` sin secretos, `alembic.ini` sin credenciales, `migrations/` con 2 versiones y comentario de lectura, `test/`, `.env` fuera del repositorio.
- Revisar `docs/bitacora.md`: una sección por integrante con fecha, qué pidió al agente y qué corrigió a mano.
- Correr la suite `pytest` completa sobre `taller_test` y anotar el resultado.

**Fase B (cuando se mergee CH-08):**
- Correr los `.http` de C-06, C-10 a C-13, C-15 y C-17 y la corrida completa de C-01 a C-19.
- Evidencia de C-15 con `SQL_ECHO=true`: el detalle de una orden con 2 ítems y el de otra con 4.
- Verificación final de RN-01 a RN-20 contra el código.
- Archivar `autorizacion-y-roles`, `repuestos-y-stock` y `ordenes` (ya están completos o lo estarán; hoy siguen en `openspec/changes/`).

**Reglas de trabajo del change:** no se reescribe ningún `.http` ni código de los compañeros: cada falla se lista con su caso y su dueño para avisarle. No se hacen commits ni se agregan líneas de atribución. Los únicos archivos del repositorio que este change crea o modifica son `README.md`, `docs/bitacora.md` (sólo la sección de revisión de Belén) y una carpeta de evidencias.

## Capabilities

### New Capabilities
- `puesta-en-marcha`: el repositorio se levanta desde cero con el README (entorno, bases, `.env` con clave fija, migraciones, seed, servidor, diagnóstico de SQL, tests) y trae todos los archivos de entrega sin credenciales.
- `evidencias-de-entrega`: los casos C-01..C-19 se corren contra una base sembrada y su resultado queda registrado; la evidencia de C-14 y C-15 está en el repositorio; la bitácora y la verificación RN-01..RN-20 quedan revisadas.

### Modified Capabilities
<!-- Ninguna: no cambia el comportamiento de ninguna capacidad existente. -->

## Impact

- **Código de la aplicación**: ninguno. No se toca `app/`, `main.py`, `seed.py`, `migrations/` ni `test/*.http`.
- **Archivos que cambian**: `README.md` (reescrito), `docs/bitacora.md` (sección de cierre de Belén), `docs/evidencias/` (nuevo: resultado de cada caso, salida de C-14 y, en la Fase B, la de C-15 y la verificación de RN).
- **Se lee y se corre** (sin modificarlo): `test/*.http`, `test/solo_agregado.sql`, `seed.py`, `alembic`, `pytest`.
- **Riesgos**: (1) CH-08 puede no llegar a tiempo y dejar C-06, C-10..C-13, C-15 y C-17 sin correr; (2) los `.http` están pensados para REST Client y la CLI no lo trae, así que se corren con un script que reproduce cada pedido y deja el resultado por escrito (ver `design.md`); (3) `taller_test` debe quedar vacía tras `seed.py` manual (nota de CH-02 en la bitácora).
- **Governance**: BAJO (consolidación y documentación, sin lógica nueva).
