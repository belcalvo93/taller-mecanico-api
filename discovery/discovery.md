# Discovery — Taller mecánico (API)

**Fecha**: 2026-10-23
**Fuentes investigadas**: ninguna externa. La única fuente es `docs/consigna-tp.md` (por indicación del profesor, no se buscan soluciones similares).

## 1. Problema que resuelve

Un taller mecánico necesita una API asincrónica para su trabajo diario: órdenes de trabajo, stock de repuestos y control de acceso por roles. En lo académico, el TP integra los capítulos 1 a 6 de Programación III (UTN) y se evalúa con una demo en vivo donde cada integrante explica lo suyo.

## 2. Usuarios / roles

- **RECEPCION**: da de alta clientes y vehículos y abre una orden de trabajo por cada ingreso.
- **MECANICO**: toma la orden, la repara y la da por terminada.
- **ADMIN**: mantiene el catálogo de repuestos, repone stock y administra al personal y sus roles.
- **CLIENTE**: se registra solo en la web y consulta el estado de sus vehículos y órdenes.

## 3. Casos de uso

Son los casos de prueba C-01 a C-19 de la consigna. Los centrales:

1. Como cliente, quiero registrarme e iniciar sesión (cookie HttpOnly) para consultar mis vehículos y órdenes.
2. Como recepción, quiero abrir una orden con sus ítems para registrar el ingreso de un vehículo.
3. Como mecánico, quiero terminar una orden para que se descuente el stock de cada repuesto en una sola transacción.
4. Como dueño de un vehículo, quiero cancelar mi orden pendiente.
5. Como administrador, quiero revocar un rol y que la sesión abierta pierda el permiso en la petición siguiente.
6. Como personal con contraseña provisoria, quiero cambiarla (cambio obligatorio) y que las sesiones anteriores dejen de valer.

## 4. Competidores / soluciones existentes

No aplica. Es un trabajo práctico académico y no hay competidores que analizar. El único referente es la consigna. No hubo scraping.

## 5. Funcionalidades necesarias

Todo lo que pide la consigna:

- Los 8 ejercicios, las 20 reglas de negocio (RN-01 a RN-20) y los endpoints de referencia.
- `seed.py` con los datos iniciales.
- Dos migraciones de Alembic: una autogenerada y una escrita a mano con el trigger de sólo agregado.
- Los archivos `.http` de los casos C-01 a C-19 y `test/solo_agregado.sql`.
- README con los pasos para levantar el proyecto desde cero.
- Evidencias de C-14 (psql con los rechazos del trigger) y C-15 (consultas del detalle de una orden con 2 y con 4 ítems).

## 6. Funcionalidades opcionales

Ninguna. El alcance es estrictamente la consigna: sin Docker, sin CI y sin linter. Los tests de TDD con pytest sí van, porque lo exige `CLAUDE.md`.

## 7. Reglas de negocio

- RN-01 a RN-20 de `docs/consigna-tp.md`.
- Las 17 reglas "que NUNCA se rompen" del `CLAUDE.md` del proyecto.
- Si algo del `CLAUDE.md` contradice la consigna, manda la consigna. En el stack, `CLAUDE.md` fija asyncpg (la consigna acepta también psycopg 3 async).

### Aclaraciones del profesor en clase (tan obligatorias como la consigna)

- Las tablas appendOnly (`historial_estado_orden`, `movimiento_stock`, `historial_precio_repuesto`) NO tienen endpoint propio: se escriben dentro del service de la operación que las genera.
- El catálogo `estado_orden` funciona como un enum: sin endpoints de crear, editar ni borrar. Se precarga con `seed.py` y sólo se lee.
- La clave de firma del JWT es FIJA y vive en el `.env`. Nunca se genera al arrancar: si cambiara en cada reinicio, todos los usuarios logueados quedarían afuera.
- El commit sólo lo hace el Unit of Work: ni el service ni los repositorios (usan `flush`).
- `SQL_ECHO=true` para ver las consultas en consola.
- Probar con Swagger alcanza; igual se entregan los `.http` de los casos C-01 a C-19.
- La evaluación es una demo en vivo: tiene que quedar evidencia de que los 5 trabajaron y revisaron (PRs con revisión y bitácora).
- No buscar soluciones similares: la knowledge-base se arma sólo desde `docs/consigna-tp.md`.

## 8. Integraciones

Sólo PostgreSQL. El aviso al cliente al terminar una orden es simulado con `BackgroundTasks` y `asyncio.sleep(0.5)`. No hay colas, Redis ni APIs externas.

## 9. Restricciones

- **Plazo**: entrega el viernes 30/10/2026. Se trabaja en las clases del viernes 23/10, martes 27/10 y viernes 30/10.
- **Equipo**: 5 integrantes (Belén, Elías, Hernán, Bruno, Joaquín), trabajando en 4 olas en paralelo, con una rama `feat/<change>` por change.
- **Revisión**: cada PR necesita la aprobación de al menos un compañero antes del merge.
- **Base de datos**: PostgreSQL 16 o superior instalado en cada máquina (la de Belén es la 17), sin Docker. Hay dos bases separadas en el mismo servidor local: la de desarrollo y la de tests (ej. `taller_test`). Los tests crean la de tests con `alembic upgrade head`, nunca con `create_all`. El README explica cómo crear las dos.
- **Stack**: el de `CLAUDE.md` (Python 3.12, FastAPI 0.111, SQLModel 0.0.24, SQLAlchemy 2.0 async, asyncpg 0.30, Alembic 1.13, pydantic-settings 2.0, bcrypt 4.0, PyJWT 2.8), con versiones mínimas.

### Reparto y olas (decidido)

| Ola | Change | Responsable |
|---|---|---|
| 1 | infra-base | Belén |
| 1 | esquema-y-migraciones | Belén |
| 1 | nucleo-repositorios-uow | Elías |
| 2 | autenticacion | Hernán |
| 2 | autorizacion-y-roles | Hernán |
| 2 | clientes-y-vehiculos | Joaquín |
| 2 | repuestos-y-stock | Bruno |
| 3 | ordenes | Elías |
| 4 | casos-y-entrega | Belén |

- Las olas son sólo los changes de implementación. La fundación (discovery, knowledge-base, roadmap) va antes.
- Las tareas de cierre (README, evidencias C-14 y C-15, consolidar los `.http`) van dentro de `casos-y-entrega`. Cada integrante escribe los `.http` de sus casos en su propio change.

## 10. Riesgos

- **Esquema que no levanta**: si `alembic upgrade head` falla, el profe no corrige. Los puntos frágiles son los índices parciales, el trigger de sólo agregado y el ciclo `upgrade` → `downgrade base` → `upgrade`.
- **Camino crítico en la ola 3**: `ordenes` depende de autenticación, clientes y repuestos. Cualquier atraso en la ola 2 lo bloquea.
- **Coordinación del equipo**: 5 personas en paralelo. El change `esquema-y-migraciones` bloquea a todos, y los modelos los escribe sólo él.
- **Plazo**: una semana y tres clases de trabajo. Hay riesgo de llegar sin las evidencias de C-14 y C-15 ni el README.
- **Demo en vivo**: cada integrante explica lo suyo, así que cada uno tiene que entender el código que escribe y quedar con evidencia de revisión (PRs y bitácora).

## 11. Preguntas abiertas

No quedan abiertas. Las cuatro que había se resolvieron con el usuario:

- Reparto de changes y olas: resuelto, ver el cuadro del punto 9.
- Driver de base de datos: asyncpg, confirmado.
- Revisiones: al menos una aprobación de un compañero por PR antes del merge.
- Tareas de cierre: van dentro del change `casos-y-entrega`.
