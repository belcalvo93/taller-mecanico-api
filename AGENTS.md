Las reglas del proyecto están en CLAUDE.md y son obligatorias; leelo antes de cualquier cambio.

# Taller mecánico (API) — Instrucciones para Agentes

API asincrónica para un taller mecánico (órdenes de trabajo, stock y acceso por roles). TP integrador de Programación III (UTN), entrega el viernes 30/10/2026. Stack, arquitectura y reglas duras: ver CLAUDE.md (no se repiten acá).

## Fuentes de verdad (en orden)

Si dos fuentes se contradicen, manda la primera de la lista:

1. `docs/consigna-tp.md`
2. `CLAUDE.md`
3. `knowledge-base/`
4. `CHANGES.md`

## Base de conocimiento

Armada solo desde `docs/consigna-tp.md` y el Discovery (`discovery/discovery.md`). Índice en `knowledge-base/README.md`.

| Archivo | Para qué leerlo |
|---|---|
| `01_vision_y_objetivos.md` | Propósito, alcance, fuera de alcance, pesos de la evaluación |
| `02_descripcion_general.md` | Stack, capas, los 33 endpoints y convenciones de respuesta |
| `03_actores_y_roles.md` | Roles, matriz RBAC, reglas 401/403 |
| `04_modelo_de_datos.md` | 13 tablas, restricciones, migraciones, datos del seed |
| `05_reglas_de_negocio.md` | RN-01..RN-20 y aclaraciones del profesor (AP-01..AP-08) |
| `06_funcionalidades.md` | Épicas (una por change) con historias y criterios de aceptación |
| `07_flujos_principales.md` | Flujos extremo a extremo (registro, login, órdenes, stock) |
| `08_arquitectura_propuesta.md` | Patrones, estructura de directorios, variables de entorno |
| `09_decisiones_y_supuestos.md` | Decisiones (DD-NN) y supuestos (SU-NN), reparto y calendario |
| `10_preguntas_abiertas.md` | Inconsistencias y preguntas pendientes |

## Roadmap

El detalle de cada change (alcance, tareas, RN, casos C, `.http`, dependencias) está en `CHANGES.md`. **CH-NN = issue #NN de GitHub.** No confundir los changes (`CH-01..CH-09`) con los casos de prueba (`C-01..C-19`).

| Ola | Change | Responsable | Fechas |
|---|---|---|---|
| 1 | CH-01 `infra-base` | Belén | vie 23/10 |
| 1 | CH-02 `esquema-y-migraciones` | Belén | vie 23 – lun 26/10 |
| 1 | CH-03 `nucleo-repositorios-uow` | Elías | vie 23 – lun 26/10 |
| 2 | CH-04 `autenticacion` | Hernán | lun 26 – mié 28/10 |
| 2 | CH-05 `autorizacion-y-roles` | Hernán | lun 26 – mié 28/10 |
| 2 | CH-06 `clientes-y-vehiculos` | Joaquín | lun 26 – mié 28/10 |
| 2 | CH-07 `repuestos-y-stock` | Bruno | lun 26 – mié 28/10 |
| 3 | CH-08 `ordenes` | Elías | mié 28 – jue 29/10 |
| 4 | CH-09 `casos-y-entrega` | Belén | jue 29 – vie 30/10 a la mañana |

- Primer change: CH-01 `infra-base`.
- Dentro de la ola 2 hay dos dependencias puntuales: la primera tarea de CH-04 (`get_usuario_actual` y `requiere_rol` provisorios) y la primera tarea de CH-06 (`ClienteRepository`). Ver "Coordinación obligatoria" en `CHANGES.md`.
- CH-08 depende de CH-04 y CH-05 completos, y de CH-06 y CH-07.

## Cómo trabajar en este repo

1. **Antes de cada change**: leer su sección en `CHANGES.md` (CH-NN = issue #NN) y los archivos de `knowledge-base/` que indica en "Leer antes". No se implementa nada que no esté en el alcance de ese change.
2. **Flujo por change**: rama `feat/<change>` → `/opsx:propose <change>` → `/opsx:apply <change>` → PR a `main` con `Closes #NN` y aprobación de un compañero → `/opsx:archive <change>` tras el merge.
3. **Tests**: las pruebas son los .http de `test/` (C-01 a C-19) y `test/solo_agregado.sql`, corridos contra el servidor real después de `python seed.py`. Cada integrante escribe en `test/` los `.http` de sus casos C.
4. **Bitácora**: cada uno anota sus decisiones en `docs/bitacora.md` (fecha, qué le pidió al agente, qué corrigió a mano y por qué).

## Skills

No hay skills de stack instaladas para este proyecto (decisión del equipo). Las skills disponibles y sus reglas compactas las resuelve el orquestador desde `.atl/skill-registry.md` (generado por `skill-registry`; no versionado — no está en el repo).
