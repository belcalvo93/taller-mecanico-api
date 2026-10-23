# Visión y Objetivos

## Propósito del sistema

API asincrónica para el trabajo diario de un taller mecánico: gestiona clientes y vehículos, órdenes de trabajo, stock de repuestos y el acceso del personal y de los clientes por roles.

Es el trabajo práctico integrador de Programación III (UTN, Tecnicatura Universitaria en Programación), Unidades 1 a 6: fundamentos de FastAPI, contratos y CRUD, ejecución asincrónica, persistencia relacional con migraciones, autenticación y autorización, y repositorios + Unit of Work + transacciones. La evaluación es una demo en vivo donde cada integrante del equipo explica lo suyo.

**Fuente de verdad**: `docs/consigna-tp.md`. Si algo de esta KB o del `CLAUDE.md` la contradice, manda la consigna.

## Objetivos por actor

| Actor | Objetivo principal | Objetivos secundarios |
|---|---|---|
| RECEPCION | Dar de alta clientes y vehículos y abrir una orden por cada ingreso, con la falla y los repuestos previstos | Cancelar órdenes pendientes; consultar repuestos y órdenes |
| MECANICO | Tomar una orden (iniciarla) y darla por terminada | Consultar repuestos y órdenes |
| ADMIN | Mantener el catálogo de repuestos, reponer stock y administrar personal y roles | Auditar eventos de seguridad; ver movimientos e historial de precios; terminar o cancelar cualquier orden |
| CLIENTE | Registrarse solo y consultar el estado de sus vehículos y órdenes | Cancelar sus órdenes pendientes |

## Objetivos técnicos (lo que el TP debe demostrar)

1. API en capas Router → Service → UoW → Repository → Model, donde cada capa sabe lo suyo y nada más.
2. Esquema relacional versionado con Alembic (una migración autogenerada y una escrita a mano), con asociación, composición, uno a uno, catálogo, borrado lógico e índices únicos parciales.
3. Autenticación con bcrypt y token en cookie HttpOnly, sin frenar el servidor y sin revelar qué cuentas existen.
4. Autorización con roles consultados en la base en cada petición, con vigencia, distinguiendo siempre 401 de 403.
5. Operaciones de negocio con todas sus escrituras en una sola transacción.
6. Delegar en la base lo que la base garantiza: unicidad, claves foráneas, CHECK y el sólo agregado (trigger).

## Alcance v1.0

- Los 8 ejercicios de la consigna, las 20 reglas de negocio (RN-01 a RN-20) y todos los endpoints de referencia.
- `seed.py` con los datos iniciales (catálogo primero).
- Dos migraciones de Alembic; `upgrade head` → `downgrade base` → `upgrade head` debe funcionar.
- Casos de prueba C-01 a C-19 como archivos `.http` más `test/solo_agregado.sql`.
- Tests automatizados de TDD (pytest + pytest-asyncio + httpx.AsyncClient) contra una base PostgreSQL de prueba creada con `alembic upgrade head`.
- README con los pasos para levantar el proyecto desde cero y evidencias de C-14 y C-15.
- Aviso al cliente simulado (BackgroundTasks) al terminar una orden.

## Fuera de alcance

- Concurrencia (cap. 7): dos órdenes terminadas a la vez pueden producir una actualización perdida de stock; el bloqueo que la evita es tema de la próxima clase. No se evalúa.
- Colas de tareas con Redis (cap. 8): el aviso al cliente corre en el mismo proceso; si se reinicia, se pierde sin reintento. Se acepta porque es simulado.
- El segundo mecanismo del sólo agregado (que el rol de base de la app no tenga permiso sobre esas tablas): no se pide.
- Docker, CI, linter y cualquier extra fuera de la consigna (decisión del equipo).
- Frontend: sólo se entrega la API (se prueba con Swagger y archivos `.http`).
- `create_all`: el esquema se crea exclusivamente con Alembic.

## Métricas de éxito

Los criterios de evaluación de la consigna son la métrica oficial:

| Criterio | Peso |
|---|---|
| Proyecto, configuración y ciclo de vida | 8 % |
| Modelos, relaciones y migraciones | 14 % |
| Contratos y CRUD | 10 % |
| Autenticación | 16 % |
| Autorización | 14 % |
| Repositorios y Unit of Work | 20 % |
| Integridad (sólo agregado, historial de precios, intento de acceso) | 10 % |
| Lecturas sin N+1 y asincronía | 8 % |

Condición eliminatoria: un proyecto que no levanta, que no crea su esquema con `alembic upgrade head` sobre una base vacía o que contiene credenciales reales en el repositorio NO SE CORRIGE hasta que se subsane.

Éxito operativo del equipo: los 19 casos C-01 a C-19 pasan, la suite de tests está en verde y queda evidencia de que los 5 integrantes trabajaron y revisaron (PRs con revisión y bitácora).
