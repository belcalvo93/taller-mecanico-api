# Cómo trabajamos

Reglas del equipo (Belén, Elías, Hernán, Bruno, Joaquín) para el TP. El tablero está en el GitHub Project "Taller Mecánico API - Tablero" y cada change tiene su issue (CH-NN = issue #NN).

## Ramas y PRs
- Una rama por change: `feat/<nombre-del-change>`, y PR a `main`. **Nadie pushea directo a `main`.**
- El PR lleva `Closes #N` y necesita la aprobación de al menos un compañero antes del merge.
- Commits chicos y en español, con el nombre del change.

## Antes de arrancar un change
- Leer la sección del change en [CHANGES.md](CHANGES.md) y los archivos de `knowledge-base/` que figuran en "Leer antes".
- Verificar que las dependencias del change (sección "Bloqueado por" del issue) están mergeadas en `main`.

## Ciclo SDD
- Cada uno corre su ciclo SDD en su rama: `/opsx:propose <change>` y después `/opsx:apply <change>` (TDD estricto: rojo → verde → refactor).
- Tras el merge, se archiva con `/opsx:archive <change>`.

## Archivos compartidos
- `CLAUDE.md` es igual para todos y **no se toca sin avisar al grupo**.
- Los modelos (`app/modules/<mod>/models.py`) y las migraciones los escribe **sólo Belén** (change 2, `esquema-y-migraciones`). Si alguien necesita una columna extra, la pide.

## Casos `.http`
- Cada uno escribe en `test/` los `.http` de sus casos, con la respuesta esperada en un comentario.
- Belén los consolida en el change `casos-y-entrega`.

## Bitácora
- Cada uno anota sus decisiones en `docs/bitacora.md` (en su sección): qué le pidió al agente, qué corrigió a mano y por qué. El archivo lo crea el change `infra-base`.
