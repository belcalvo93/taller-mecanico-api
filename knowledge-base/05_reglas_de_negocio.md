# Reglas de Negocio

Los códigos `RN-01` a `RN-20` son los de la consigna (`docs/consigna-tp.md`) y se mantienen tal cual, porque la corrección y el equipo las citan así ("verificar contra cada regla RN y cada caso C"). Por eso no se usa el formato `RN-{DOMINIO}-{NN}`; las reglas se agrupan por dominio sólo para leerlas. Cada regla indica cómo se implementa, el código HTTP de error y el caso de prueba que la ejercita.

## Dominio: Unicidad e integridad

- **RN-01** — El correo de un usuario y el documento de un cliente son únicos. La patente de un vehículo y el código de un repuesto son únicos entre los no dados de baja. → UNIQUE e índices únicos parciales; 409 con mensaje propio. La unicidad la garantiza la base: no se verifica con consulta previa, se traduce el `IntegrityError`. (C-02, C-19)
- **RN-15** — `historial_estado_orden`, `movimiento_stock` e `historial_precio_repuesto` son de sólo agregado: nadie puede modificar ni borrar sus filas. → Trigger en la base, instalado por la migración 2. (C-14)
- **RN-18** — Ningún error devuelve al cliente texto interno de la base. Ninguna entrada inválida termina en un 500. → Traducción del `IntegrityError`; validación en el contrato. (C-01, C-02, C-16)

## Dominio: Registro, usuarios y roles

- **RN-02** — El auto-registro crea el usuario, su rol CLIENTE y su ficha de cliente: o quedan las tres filas o ninguna. Si el documento ya es de un cliente del taller, da 409 y no se apropia de esa ficha. → Un solo Unit of Work. (C-02)
- **RN-03** — Un usuario tiene a lo sumo una asignación abierta por rol. → Índice único parcial; 409.
- **RN-04** — Los permisos se deciden con los roles vigentes en la base, en cada petición. Los roles del token son informativos. → Dependencia que consulta `asignacion_rol`. (C-06, C-07)
- **RN-05** — Un administrador no puede revocarse su propio rol ADMIN, y el sistema nunca queda sin administradores vigentes. → Comprobación en el servicio; 409. (C-08)

## Dominio: Sesión y contraseñas

- **RN-06** — Mientras un usuario tenga el cambio de contraseña pendiente, sólo puede usar las rutas de `/auth` y las de salud. → Dos grupos de rutas; 403. (C-09)
- **RN-07** — Al cambiar la contraseña, las sesiones emitidas antes dejan de valer, aunque sean del mismo segundo que el cambio; la que devuelve el propio cambio, no. → Comparación de `iat` con `password_cambiada_en`, sin truncar; 401. (C-09)
- **RN-08** — Después de 5 intentos fallidos con el mismo correo desde la misma IP en 60 segundos, el login responde 429 sin verificar la contraseña. Un login correcto reinicia la cuenta: los fallos anteriores siguen en la tabla pero dejan de contar. → Conteo sobre `intento_acceso`; `Retry-After`. (C-05)
- **RN-09** — El login responde lo mismo, y tarda lo mismo, exista o no el correo. → Mismo mensaje; verificación contra un hash ficticio. (C-04)

## Dominio: Órdenes de trabajo

- **RN-10** — Una orden nace PENDIENTE con al menos un ítem y sin repuestos repetidos. El precio de cada ítem se copia del repuesto y el total lo calcula el servidor. → DTO; el precio y el total nunca viajan en el cuerpo. (C-10)
- **RN-11** — Transiciones: PENDIENTE → EN_REPARACION (la inicia un mecánico, que queda asignado), EN_REPARACION → TERMINADA (la termina el mecánico asignado o un administrador), PENDIENTE → CANCELADA. → Servicio; 409 si el estado no lo permite.
- **RN-12** — Cancelan una orden la recepción, el administrador o el DUEÑO DEL VEHÍCULO. El permiso se evalúa antes que el estado. → Servicio; 403 antes que 409. (C-13)
- **RN-13** — Terminar una orden descuenta el stock de cada ítem, deja un movimiento por cada salida y una línea de historial. Si un repuesto no alcanza, no queda ninguna de esas escrituras. → Un solo Unit of Work; 409. (C-11, C-12)
- **RN-19** — Los estados posibles de una orden son las filas del catálogo `estado_orden`. El catálogo se consulta desde la API y no se edita desde ella. Si está vacío, crear una orden responde 409 con mensaje propio. → Clave foránea; repositorio de sólo lectura. (C-17)

## Dominio: Repuestos, vehículos y stock

- **RN-14** — El stock sólo cambia a través de movimientos: alta con stock inicial, reposición y terminación de órdenes. No se edita por PATCH. → Punto único de escritura de stock. (C-16)
- **RN-16** — Un vehículo o repuesto dado de baja deja de aparecer y no se puede usar en órdenes nuevas, pero sus datos se conservan. Un vehículo con órdenes abiertas (en un estado no final según el catálogo) no se da de baja. → Borrado lógico; `es_final`; 409. (C-19)
- **RN-20** — Cada cambio del precio de un repuesto deja una línea en `historial_precio_repuesto`, en la misma transacción. Un PATCH que no cambia el precio no deja línea. → Un solo Unit of Work; CHECK `precio_nuevo <> precio_anterior`. (C-18)

## Dominio: Acceso a lo propio

- **RN-17** — Lo propio sólo pide estar autenticado: un cliente ve sus vehículos y las órdenes de sus vehículos, y ninguna otra. → `/mis-*` y comprobación de dueño; 403. (C-06)

## Reglas técnicas transversales (CLAUDE.md)

Las 17 reglas "que NUNCA se rompen" de `CLAUDE.md` bajan la consigna a prácticas concretas. Las más citadas en las demos:

| Tema | Regla |
|---|---|
| Esquema | Sólo Alembic; migración 1 autogenerate, migración 2 a mano con comentario "leída antes de aplicar"; ciclo up/down/up funcional |
| Tipos | `timestamptz` en todas las fechas; `NUMERIC`/`Decimal` en dinero; índice en cada FK |
| Catálogo | `estado_orden` creada vacía por la migración, cargada por `seed.py`; estados como FK, nunca CHECK con lista |
| Unicidad | La garantiza la base; `IntegrityError` → 409 con mensaje propio |
| Secretos | Nada en el código, ni como default, ni en `alembic.ini`; la clave del JWT es FIJA y vive en `.env`; `env.example` sin secretos |
| bcrypt | `asyncio.to_thread` + semáforo, costo desde la config, ANTES de abrir la transacción; máximo 72 BYTES validado en el contrato (422) |
| Token | Sólo en cookie `access_token` HttpOnly, SameSite=Lax, Max-Age = duración, Secure configurable; nunca en el cuerpo ni leído de `Authorization` |
| Login | Primero límite de intentos (429 + Retry-After, sin hash), después verificación contra hash real o ficticio; `intento_acceso` en sesión y transacción PROPIAS, comentado con su costo |
| Repos / UoW | `add`/`update` hacen `flush()`; sólo el UoW hace commit; el router construye el UoW, el servicio lo abre; stock en un único punto; catálogo con repo de sólo lectura que NO hereda de BaseRepository; carga perezosa prohibida |
| Contratos | `extra="forbid"`; PATCH con `exclude_unset`; ninguna respuesta con `password_hash`; listados con envoltorio estándar |
| SQL | Nunca por concatenación; handlers `async def`; `SQL_ECHO=true` configurable |

## Aclaraciones del profesor en clase

Tan obligatorias como la consigna (fuente: Discovery del 2026-10-23):

- **AP-01** — Las tablas appendOnly (`historial_estado_orden`, `movimiento_stock`, `historial_precio_repuesto`) NO tienen endpoint propio: se escriben dentro del service de la operación que las genera.
- **AP-02** — El catálogo `estado_orden` funciona como un enum: sin endpoints de crear, editar ni borrar; se precarga con `seed.py` y sólo se lee.
- **AP-03** — La clave de firma del JWT es FIJA y vive en el `.env`. Nunca generarla al arrancar: si cambia en cada reinicio, todos los usuarios logueados quedan afuera.
- **AP-04** — El commit sólo lo hace el Unit of Work: ni el service ni los repositorios (usan `flush`).
- **AP-05** — `SQL_ECHO=true` para ver las consultas en consola.
- **AP-06** — Probar con Swagger alcanza; igual se entregan los `.http` de los casos C-01 a C-19.
- **AP-07** — La evaluación es una demo en vivo: tiene que quedar evidencia de que los 5 trabajaron y revisaron (PRs con revisión y bitácora).
- **AP-08** — No buscar soluciones similares: la knowledge-base se arma sólo desde `docs/consigna-tp.md`.

## Dominio: Excepciones globales

- Todo error de la base se traduce a un mensaje propio; nunca se devuelve texto de la base ni trazas.
- Todo campo que termina en bcrypt (contraseña del registro, del login, la actual y la nueva del cambio) acepta como máximo 72 BYTES (no caracteres); si no, 422.
- Fecha de vencimiento de un rol: debe llegar con zona horaria y en el futuro; sin zona o ya pasado son 422, no 409.
- El historial de seguridad registra las altas, los cambios de rol y de contraseña, y los datos iniciales con el actor `SISTEMA` (texto, no usuario).
- El aviso al cliente al terminar una orden corre con `BackgroundTasks` DESPUÉS de enviar la respuesta y sólo si la operación se confirmó.
