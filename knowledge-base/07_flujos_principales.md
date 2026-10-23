# Flujos Principales

Cada flujo se documenta extremo a extremo con la cadena Router → Service → UoW → Repository. Los flujos que escriben en varias tablas (registro, terminar orden, cambiar precio) se ejecutan en UN solo bloque de UoW.

## Flujo 1: Registro de cliente (RN-02)

**Disparador**: `POST /auth/registro`
**Actor**: visitante anónimo

**Pasos**:
1. Router valida el contrato (`extra="forbid"`, contraseña ≤ 72 bytes) y construye el UoW de `usuarios`.
2. Service calcula el hash con bcrypt (`to_thread` + semáforo) ANTES de abrir la transacción.
3. Service abre `async with uow`.
4. Se agregan en el mismo bloque: `usuario`, `asignacion_rol` (CLIENTE) y `cliente` (con `usuario_id`), cada una con `flush()`.
5. Se anota el alta en `evento_seguridad`.
6. Al salir del bloque, el UoW hace commit. Responde 201.

**Casos de error**:
- Correo repetido → `IntegrityError` en el flush → rollback → 409 con mensaje propio.
- Documento repetido (ya es de un cliente del taller) → `IntegrityError` → rollback → 409; no se apropia la ficha; no quedan filas sueltas.
- Contraseña de más de 72 bytes o campo no declarado → 422 antes de tocar la base.

## Flujo 2: Login (RN-08, RN-09)

**Disparador**: `POST /auth/login`
**Actor**: cualquier usuario

**Pasos**:
1. Router valida el contrato (contraseña ≤ 72 bytes).
2. Service cuenta los fallos recientes del par (email, IP) en `intento_acceso` desde el último éxito, dentro de los últimos 60 segundos.
3. Si hay 5 o más → responde 429 con `Retry-After`, SIN calcular ningún hash.
4. Si no, busca al usuario por correo y verifica con bcrypt contra su hash real o, si no existe, contra el hash ficticio calculado en el lifespan (mismo tiempo, mismo mensaje).
5. Escribe el intento (éxito o fallo) en `intento_acceso` desde una sesión y una transacción PROPIAS que se confirman siempre (comentado en el código con su costo: deja filas aunque la petición falle).
6. Si fue correcto: consulta los roles vigentes, emite el JWT (`sub`, `iat` con fracciones, `exp`, roles) y lo pone en `Set-Cookie` `access_token` (HttpOnly, SameSite=Lax, Max-Age, Secure configurable). Cuerpo: `{"mensaje", "debe_cambiar_password", "expira_en_segundos"}`.

**Casos de error**:
- Contraseña mala o correo inexistente → 401 con el mismo cuerpo.
- Más de 5 fallos en 60 s → 429 en pocos milisegundos.

## Flujo 3: Petición autenticada y autorizada (RN-04, RN-06, RN-07)

**Disparador**: cualquier ruta del grupo protegido
**Actor**: usuario con sesión

**Pasos**:
1. `get_usuario_actual` lee `request.cookies["access_token"]`, valida firma y vigencia.
2. Carga el usuario de la base: inexistente o inactivo → 401.
3. Compara `iat` con `password_cambiada_en` sin truncar: token anterior → 401.
4. El control del cambio obligatorio (montado una vez en el grupo protegido): si `debe_cambiar_password` → 403.
5. `requiere_rol(...)` consulta `asignacion_rol` vigente en la base (no revocada, sin vencer): sin rol → 403.
6. El handler llama al servicio con el UoW construido por la dependencia.

**Casos de error**:
- Sin cookie, o con `Authorization: Bearer` → 401.
- Rol revocado con la sesión abierta → misma cookie, 403 en la petición siguiente.

## Flujo 4: Cambio obligatorio de contraseña (RN-06, RN-07)

**Disparador**: `POST /auth/cambiar-password`
**Actor**: usuario con `debe_cambiar_password=true` (por ejemplo `nuevo@example.com`)

**Pasos**:
1. Tras el login, toda ruta protegida da 403; sólo se permiten `/auth/*` y salud.
2. Router valida contraseña actual y nueva (≤ 72 bytes).
3. Service verifica la actual y calcula el hash nuevo ANTES de la transacción.
4. En un bloque de UoW: actualiza `password_hash`, `password_cambiada_en`, `debe_cambiar_password=false` y registra el evento.
5. Emite un token NUEVO después de anotar el cambio; responde con la cookie nueva.

**Resultado**: la cookie nueva vale; la anterior da 401, aunque sea del mismo segundo (sin esperar entre el login y el cambio).

## Flujo 5: Asignar y revocar rol (RN-03, RN-05)

**Disparador**: `POST /usuarios/{id}/roles` o `DELETE /usuarios/{id}/roles/{rol}`
**Actor**: ADMIN

**Pasos (asignar)**:
1. Valida `vence_en`: con zona horaria y en el futuro, si no 422.
2. En un bloque de UoW: si hay una fila vencida del mismo rol, la cierra; abre una nueva (índice único parcial garantiza una abierta por rol); registra el evento.
3. Responde 201.

**Pasos (revocar)**:
1. Service comprueba la autoprotección: si el ADMIN se revoca a sí mismo, o si fuera el último ADMIN vigente → 409.
2. Escribe `revocada_en` (la fila no se borra) y registra el evento. Responde 200.

**Casos de error**: usuario inexistente → 404; rol ya abierto → 409.

## Flujo 6: Alta de vehículo y baja con reutilización de patente (RN-01, RN-16)

**Disparador**: `POST /clientes/{id}/vehiculos` y `DELETE /vehiculos/{id}`
**Actor**: RECEPCION o ADMIN

**Pasos**:
1. Alta: `flush()` del vehículo; si la patente vigente ya existe, `IntegrityError` → 409.
2. Baja: Service verifica que el vehículo no tenga órdenes abiertas (estado no final según el catálogo, `es_final`); si las tiene → 409.
3. Si no, `soft_delete` escribe `borrado_en`; responde 204.
4. La misma patente se puede registrar luego para otro cliente: el índice único parcial sólo cuenta vigentes.

## Flujo 7: Crear orden (RN-10, RN-19)

**Disparador**: `POST /ordenes`
**Actor**: RECEPCION o ADMIN

**Pasos**:
1. Router valida el contrato: `vehiculo_id`, `falla`, `items` (≥ 1, sin repuestos repetidos); no acepta precio, total, estado ni fecha.
2. Service abre el UoW de `ordenes`.
3. Verifica el vehículo vigente y que el catálogo tenga PENDIENTE (catálogo vacío → 409).
4. Para cada ítem toma el repuesto vigente y copia su precio a `precio_unitario`; repuesto inexistente o dado de baja → 409.
5. Calcula el total (Decimal) y escribe `orden_trabajo` (PENDIENTE), los `item_orden` y la primera línea de `historial_estado_orden` (desde nulo → PENDIENTE).
6. Commit al salir; recarga el detalle con precarga declarada y responde 201.

**Casos de error**: repuesto inexistente → 409 y la orden no queda creada (C-10).

## Flujo 8: Iniciar orden (RN-11)

**Disparador**: `POST /ordenes/{id}/iniciar`
**Actor**: MECANICO

**Pasos**: en un bloque de UoW, PENDIENTE → EN_REPARACION, asigna `mecanico_id` al usuario actual y agrega la línea de historial. Si la orden no está PENDIENTE → 409; inexistente → 404.

## Flujo 9: Terminar orden (RN-13, RN-14)

**Disparador**: `POST /ordenes/{id}/terminar`
**Actor**: el mecánico asignado, o ADMIN

**Pasos**:
1. Service carga la orden con sus ítems; decide permiso (no es el asignado ni ADMIN → 403) antes que estado (no está EN_REPARACION → 409).
2. En UN solo bloque de UoW:
   1. para cada ítem, descuenta el stock por el punto único de escritura de stock;
   2. escribe un `movimiento_stock` por cada salida;
   3. pasa la orden a TERMINADA;
   4. agrega la línea de `historial_estado_orden`.
3. Si algún repuesto no alcanza (el CHECK `stock >= 0` o la comprobación del servicio) → excepción → rollback total → 409; estado, stock, movimientos e historial quedan exactamente como estaban (C-11).
4. Si se confirmó, agenda con `BackgroundTasks` el aviso al cliente (`await asyncio.sleep(0.5)` + mensaje en el registro), que corre DESPUÉS de enviar la respuesta.

**Diagrama de secuencia** (ASCII):
```
Router ─▶ Service ─▶ async with UoW ─┬─▶ StockRepo.descontar (flush)
                                     ├─▶ MovimientoRepo.add  (flush)
                                     ├─▶ OrdenRepo.update    (flush)
                                     └─▶ HistorialRepo.add   (flush)
                       commit al salir ◀─┘   (rollback si hay excepción)
Router ◀─ respuesta ─▶ BackgroundTasks: aviso simulado
```

## Flujo 10: Cancelar orden (RN-12)

**Disparador**: `POST /ordenes/{id}/cancelar`
**Actor**: RECEPCION, ADMIN o el dueño del vehículo (la ruta NO lleva `requiere_rol`)

**Pasos**:
1. Service determina quién es el usuario y qué relación tiene con la orden: personal con rol vigente, o dueño del vehículo; si no → 403.
2. Recién después verifica el estado: sólo PENDIENTE → CANCELADA; otro estado (por ejemplo TERMINADA) → 409.
3. En un bloque de UoW cambia el estado y agrega la línea de historial.

## Flujo 11: Reponer stock y cambiar precio (RN-14, RN-20)

**Disparador**: `POST /repuestos/{id}/reponer` y `PATCH /repuestos/{id}`
**Actor**: ADMIN

**Pasos (reponer)**: en un bloque de UoW suma stock por el punto único de escritura y escribe un `movimiento_stock`.
**Pasos (PATCH)**:
1. El contrato acepta sólo descripción y precio (`extra="forbid"`, `exclude_unset`).
2. En un solo bloque de UoW actualiza el repuesto; SI el precio cambió, escribe una línea en `historial_precio_repuesto` (precio anterior y nuevo).
3. Un PATCH que no cambia el precio no deja línea.

## Flujo 12: Detalle de orden sin N+1 (Ejercicio 8)

**Disparador**: `GET /ordenes/{id}`
**Actor**: personal o dueño del vehículo

**Pasos**: el repositorio de órdenes carga, dentro del propio método, vehículo, cliente, ítems, repuesto de cada ítem e historial con carga anticipada (`selectinload` / `joinedload`). El número de consultas es fijo e independiente de la cantidad de ítems: se verifica con `SQL_ECHO=true` comparando 2 y 4 ítems (C-15).

## Flujo 13: Puesta en marcha desde cero

**Actor**: integrante del equipo

**Pasos**:
1. Crear el entorno virtual e instalar `requirements.txt`.
2. Crear las dos bases en el PostgreSQL local (desarrollo y tests, p. ej. `taller_test`).
3. Copiar `env.example` a `.env` y completar variables, incluida la clave de firma FIJA (cómo generarla, en el README).
4. `alembic upgrade head`, luego verificar `alembic downgrade base` y otra vez `upgrade head`.
5. `python seed.py`.
6. Levantar el servidor (uvicorn / `fastapi dev`).
7. Antes de cada archivo `.http`: `python seed.py`.
