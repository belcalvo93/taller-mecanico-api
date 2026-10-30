# Design

## Context

Estado observado en `feat/casos-y-entrega` (cortada de `main` con CH-01..CH-07 mergeados):

- `README.md` es un placeholder de 9 líneas que dice que los pasos se completan en este change.
- `test/` tiene 11 `.http` (C-01..C-05, C-07, C-08, C-09, C-16, C-18, C-19) y `solo_agregado.sql`. Usan `{{base}}`, `# @name` y `{{login….response.headers.Set-Cookie}}` (extensión REST Client); varios llevan `# @no-cookie-jar`.
- `solo_agregado.sql` tiene **siete** sentencias (seis del disparador y una de la FK), tal como pide C-14.
- `migrations/versions/` tiene `0001_esquema_inicial.py` y `0002_solo_agregado.py`. `env.example` trae `POSTGRES_PASSWORD=` y `JWT_SECRET_KEY=` vacíos y `SQL_ECHO=true`. `alembic.ini` no tiene URL de conexión.
- `.env` y `.venv` ya existen en este equipo; hay PostgreSQL 17 (`psql` 17.11) escuchando en el puerto 5432.
- `openspec/changes/` todavía tiene `autorizacion-y-roles` y `repuestos-y-stock` completos y sin archivar.
- La bitácora tiene sección para los cinco integrantes; Elías sólo tiene CH-03 (le falta CH-08) y hay una lista "Pendientes para CH-09" con las notas que el README tiene que recoger.
- CH-08 (`ordenes`) no está en `main`; ver `proposal.md` para el motivo de las dos fases.

## Goals / Non-Goals

**Goals:**
- Que un clon limpio levante siguiendo sólo el README, y que cada caso corrido tenga su resultado escrito.
- Dejar listas para sacar la captura (C-14) y para correr (C-15) las evidencias, sin inventar ni simular nada que dependa de CH-08.

**Non-Goals:**
- No se escribe lógica nueva, no se tocan modelos, migraciones, `seed.py`, `app/` ni los `.http` de los compañeros (CLAUDE.md y CHANGES.md).
- No se agrega Docker, CI ni linter (DD-04).
- No se hacen commits.

## Decisions

**D1. Correr los `.http` con un script descartable fuera del repositorio.**
REST Client es una extensión de VS Code y la CLI no la trae. Un script en el directorio temporal de la sesión (no en el repo) lee cada `.http`, separa los pedidos por `###`, resuelve `{{base}}` y las variables `{{nombre.response.headers.Set-Cookie}}` de los `# @name`, ejecuta los pedidos con `httpx` contra `uvicorn` y vuelca el estado y las cabeceras a un archivo. Compara a mano contra el comentario `# Esperado:` de cada pedido. *Alternativa:* que Belén corra los 11 archivos con REST Client y copie los resultados; se mantiene como respaldo para C-05 (el tiempo del 429) y cualquier caso donde el script no reproduzca bien REST Client. *Por qué no commitear el script:* sería código nuevo fuera del alcance (DD-04) y la consigna sólo pide los `.http`.

**D2. `python seed.py` antes de cada archivo, sobre la base de desarrollo `taller`.**
Es lo que dice la consigna. Se usa `taller` (no `taller_test`) para no dejar sembrada la base que la suite espera vacía. Antes de la suite no hace falta limpiar nada porque la suite usa `taller_test`.

**D3. Evidencia en `docs/evidencias/`.**
Un `resultados-fase-a.md` con una tabla (caso, archivo, esperado, obtenido, resultado, dueño si falla), `C-14_salida_psql.txt` con la salida de `psql -f test/solo_agregado.sql` y, en la Fase B, `C-15_consola.txt`, `resultados-fase-b.md` y `verificacion-rn.md`. Quedan versionados con el repositorio para la demo. La captura de pantalla de psql la saca Belén; el `.txt` es el respaldo.

**D4. C-14 con `psql` y `ON_ERROR_STOP` apagado.**
El script ya lo fija (`\set ON_ERROR_STOP off`), así que corre las siete sentencias aunque cada una falle. Se verifica además que, tras correrlo, los conteos de las tres tablas no cambian.

**D5. README como pasos ejecutables, no explicación.**
Se arma con las notas de la bitácora ("Pendientes para CH-09"): comandos desde la raíz del repo (el `.env` se lee relativo al directorio actual), orden `alembic upgrade head` → `python seed.py`, comando de la clave (`python -c "import secrets; print(secrets.token_urlsafe(64))"`), creación de usuario y bases con `psql`, tabla de variables de `.env` y que `taller_test` queda vacía tras la suite. Los comandos del README se verifican corriéndolos en una base descartable (`taller_readme`), sin tocar `taller`.

**D6. Checklist de entrega como comprobaciones de sólo lectura.**
`git ls-files`, `git check-ignore .env`, búsqueda de credenciales en `alembic.ini`, `env.example` y el árbol versionado, conteo de versiones en `migrations/versions/` y presencia del comentario de lectura. Cualquier hallazgo se lista con su dueño; no se corrige.

**D7. Fase B sólo cuando CH-08 esté en `main`.**
Se actualiza `main` en la rama, se corre `seed.py` y se ejecutan los `.http` pendientes. Para C-15 se levanta el servidor con `SQL_ECHO=true`, se crea (con los endpoints reales) una orden de 4 ítems además de una de 2 y se piden los dos detalles. Se archivan los tres changes pendientes con `/opsx:archive`, en el orden `autorizacion-y-roles`, `repuestos-y-stock`, `ordenes`.

**D8. Dos capacidades, ambas en español y con layout plano**, como el resto de `openspec/specs/`: `puesta-en-marcha` (README y entrega) y `evidencias-de-entrega` (casos, C-14, C-15, bitácora, RN).

## Risks / Trade-offs

- **CH-08 no llega a tiempo** → la Fase A queda completa y entregable salvo C-06, C-10..C-13, C-15, C-17; el registro lo dice explícitamente y la Fase B se corre lo antes posible tras el merge.
- **El script no reproduce exactamente REST Client** (por ejemplo, el tiempo de C-04/C-05) → se marcan esos casos para confirmarlos a mano con REST Client antes de la demo.
- **`seed.py` repetido deja `taller` en estado distinto de lo que esperan los `.http`** → siempre se corre `seed.py` antes de cada archivo, también si el archivo anterior falló.
- **Incumplimiento de las RN en código ajeno** → sólo se informa con caso y dueño (regla del change).
- **La bitácora no puede completarla Belén por sus compañeros** → se listan las entradas faltantes (hoy, CH-08 de Elías) a su nombre.
- **Versiones locales distintas de las del equipo** (Python 3.14, asyncpg>=0.31, PostgreSQL 17) → el README las menciona como válidas (la consigna pide 3.12+ y PostgreSQL 16+).

## Open Questions

- ¿Hay que corregir `requirements.txt` si la consigna fija asyncpg 0.30 y el archivo pide `>=0.31`? Es una decisión ya tomada en CH-01 (bitácora de Belén: 0.30 no tiene wheel para Python 3.14) y no cambia ninguna tarea; sólo se menciona en el README.
