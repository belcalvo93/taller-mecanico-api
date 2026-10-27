# Bitácora del equipo

Cada integrante anota en su sección las decisiones que tomó trabajando con el agente. Una entrada por change o sesión, con esta plantilla:

```
### YYYY-MM-DD · CH-NN <nombre-del-change>
- **Fecha:**
- **Qué le pidió al agente:**
- **Qué corrigió a mano y por qué:**
```

## Belén

### 2026-10-25 · CH-01 infra-base
- **Fecha:** 2026-10-25
- **Qué le pidió al agente:** implementar `/opsx:apply infra-base` con TDD estricto: estructura del proyecto, `requirements.txt`, configuración con `pydantic-settings` sin secretos por defecto, `env.example`, motor y sesiones async, lifespan con hash ficticio y `dispose()`, `/health/live` y `/health/ready`, y la fixture de la base de tests con Alembic. Se trabajó en un venv con Python 3.14.7 (la consigna pide 3.12 o superior).
- **Qué corrigió a mano y por qué:**
  - Exigí rojo primero desde el grupo 6, después de detectar que los tests del lifespan se escribieron después del código.
  - Pedí que el agente no haga commits ni agregue líneas de atribución; los commits los hice yo.
  - Corregí la propuesta de commits: `router.py` tenía que ir en el mismo commit que `main.py` para que el commit arranque.

**Versiones instaladas en Python 3.14** (resultado de `pip install -r requirements.txt`; `pip check` sin conflictos):

| Paquete | Versión | Piso en `requirements.txt` |
|---|---|---|
| fastapi[standard] | 0.162.0 | >=0.111 |
| sqlmodel | 0.0.48 | >=0.0.24 |
| SQLAlchemy | 2.1.6 | >=2.0 |
| asyncpg | 0.32.0 | **>=0.31** (subido, ver abajo) |
| alembic | 1.20.1 | >=1.13 |
| pydantic-settings | 2.16.1 | >=2.0 |
| bcrypt | 5.0.0 | >=4.0 |
| PyJWT | 2.15.1 | >=2.8 |
| pytest / pytest-asyncio / httpx | 9.1.1 / 1.4.1 / 0.28.1 | sin piso |

**Notas de la sesión**
- asyncpg 0.30 no tiene wheel para Python 3.14; se usa asyncpg>=0.31 (0.32.0 instalada). Es compatible con 3.12 y 3.13, así que no afecta al resto del equipo.
- En la tarea 2.6 no se pudo forzar el rojo porque que el entorno pise al .env es comportamiento nativo de pydantic-settings; se dejó el test como verificación.
- Con FastAPI 0.162 el orden de include_router es perezoso y ya no importa; el test de rutas usa app.openapi()["paths"].
- Los tests del lifespan (grupo 5) se escribieron después de `main.py`; se compensó con mutaciones (sacar `dispose()`, cambiar el semáforo y el costo de bcrypt) que hicieron fallar 5 tests, y se restauró el código. Desde el grupo 6 exigí rojo primero.
- bcrypt 5.x lanza `ValueError` con contraseñas de más de 72 bytes (la 4.x truncaba). No afecta a CH-01 (la contraseña ficticia tiene 32 bytes), pero CH-04 debe validar los 72 bytes en el contrato (regla 9).

**Decisiones no obvias del design (D1 a D9)**
- **D1:** `Settings` nunca se instancia al importar; se obtiene con `get_settings()` (con `lru_cache`) desde el lifespan. Los secretos son `SecretStr` sin default, con `min_length` (1 y 32), así un `.env` copiado de `env.example` con valores vacíos tampoco arranca. `DATABASE_URL` es un campo calculado con `URL.create` (escapa `@`, `:` y `/`).
- **D2:** `database.py` solo tiene fábricas puras (`crear_motor`, `crear_fabrica_sesiones`) y `get_session`; el motor no se crea al importar (regla 7) y el commit es del UoW (CH-03).
- **D3:** el lifespan guarda `settings`, `engine`, `session_factory`, `bcrypt_semaforo` y `hash_ficticio` en `app.state` (contrato para CH-04), no hace `SELECT 1` al arrancar y hace `dispose()` en un `finally`.
- **D4:** dos grupos de rutas (`rutas_abiertas`, `rutas_protegidas`) con un punto de inserción comentado por change.
- **D5:** `/health/ready` usa `get_session`, `SELECT 1` con `asyncio.wait_for` de 3 s y cualquier falla da 503 con cuerpo fijo; solo se registra el nombre de la clase de la excepción (SQLAlchemy envuelve el error de asyncpg, por eso aparece como `DBAPIError`).
- **D6:** `conftest.py` fija `POSTGRES_DB=taller_test` al importarse; la fixture `base_migrada` corre `alembic upgrade head` en un subproceso, se saltea sin `alembic.ini` y rechaza bases que no terminan en `_test`.
- **D7:** `requirements.txt` con pisos (`>=`), no pins, para que instale en 3.12 y 3.14.
- **D8:** `env.example` lista las 13 variables con los dos secretos vacíos; el `.env` real no se versiona y la clave JWT se genera una sola vez.
- **D9:** CH-01 no crea `migrations/` ni `alembic.ini` (`alembic init -t async` de CH-02 falla si el directorio existe).

### 2026-10-25 · CH-02 esquema-y-migraciones
- **Fecha:** 2026-10-25
- **Qué le pidió al agente:** implementar `/opsx:apply esquema-y-migraciones` con TDD estricto y checkpoints de aprobación (modelos, migración 1, migración 2, seed). Sin commits del agente; los hago yo.
- **Qué corrigió a mano y por qué:**
  - Revisé línea por línea la migración 0001 contra la consigna (13 tablas, sin Enum de PostgreSQL, índices parciales, FK al catálogo) y agregué el comentario de lectura.
  - Revisé la migración 0002 y pedí reemplazar los f-strings por SQL literal para cumplir la regla 17; agregué el comentario de lectura.
  - Revisé seed.py contra los datos iniciales de la consigna y los ids del ejemplo de respuesta (vehículo 2 = AC456EF, repuestos 2 y 4, usuario 3 = recepción).
  - Pedí que el agente no hiciera commits ni agregara líneas de atribución; los commits los hice yo.

**Notas de la sesión**
- Las tareas 2.7 y 2.8 pasaron sin rojo natural porque el código ya existía; 2.8 se verificó con una mutación (quitar `lazy="raise"` de `Vehiculo.cliente` hizo fallar el test).
- **Aviso para CH-04, CH-06 y CH-07:** los nombres de las FK no están en la metadata (`fk.name` es `None`; se asignan al generar el DDL). Para traducir `IntegrityError` a 409 usen el nombre del constraint que viene en el error de PostgreSQL (asyncpg `constraint_name`). Los nombres de UNIQUE, CHECK e índices sí están en la metadata.
- Para poder correr la suite sin aplicar una migración que todavía espera aprobación, `tests/conftest.py` acepta la variable `ALEMBIC_DESTINO_TESTS` (por defecto `head`). Ejemplo antes de aprobar 0002: `ALEMBIC_DESTINO_TESTS=0001 .venv/Scripts/python -m pytest`.
- **Corrección de Belén en 0002 (regla 17):** el agente había escrito los `CREATE TRIGGER` y `DROP TRIGGER` con f-strings sobre una tupla de tablas. Belén pidió SQL literal: ahora hay tres `CREATE TRIGGER` y tres `DROP TRIGGER IF EXISTS` completos, sin interpolación. Quedó un test (`test_ninguna_migracion_arma_sql_por_interpolacion`, con un detector por AST de f-strings, `.format`, `%` y `+` sobre texto) que falla si una migración vuelve a armar SQL así.
- **Decisión (RN-15):** el trigger de sólo agregado es `FOR EACH STATEMENT` y rechaza siempre `UPDATE` y `DELETE` sobre las 3 tablas (`historial_estado_orden`, `movimiento_stock`, `historial_precio_repuesto`), aunque no coincida ninguna fila. `TRUNCATE` queda permitido a propósito: la consigna exige que `seed.py` vacíe las tablas, y lo hace con `TRUNCATE ... RESTART IDENTITY CASCADE`. La aplicación nunca usa `TRUNCATE`, así que para la API las tablas siguen siendo de sólo agregado.
- **Pendiente para CH-08:** C-13 necesita una orden TERMINADA (para el 409) y el seed no trae ninguna. En el `.http` se obtiene terminando la orden 2 después de reponer el stock de bujías.
- **Tests del seed:** `tests/test_seed.py` deja las 13 tablas vacías al terminar (TRUNCATE en la fixture), porque otros tests (`test_esquema.py`, `test_solo_agregado.py`) esperan una base sin datos. Es un ajuste respecto de la idea del design, que decía que quedaba sembrada.

**Datos del seed aprobados** (Checkpoint 4, tal cual `design.md`): usuarios 1 a 7 (admin, admin2, recepcion, mecanico, mecanico2, cliente, nuevo) con contraseñas de prueba sólo en `seed.py`; Laura (usuario 6, documento 30111222) con los vehículos AB123CD y AC456EF, y Jorge Gómez (sin usuario, documento 25333444) con AD789GH; repuestos 1 FIL-001, 2 FRE-010, 3 BUJ-100 (bujía de encendido, 6500.00, stock 2), 4 ACE-530; orden 1 PENDIENTE (56500.00) y orden 2 EN_REPARACION con 4 bujías cuando hay 2 (26000.00). Los ids de usuarios y repuestos salen del orden en que los lista la consigna y quedan fijados por un test.

**Decisiones del design aprobadas:** D4, `asignacion_rol.otorgada_por` es FK a `usuario.id` (NULL = lo otorgó el sistema); D5, relaciones en los dos extremos con `lazy="raise"` (hay que precargar con `selectinload`/`joinedload`); D6, el registro `app/modules/modelos.py` y su import en `main.py`; D9, trigger por sentencia y `TRUNCATE` permitido (ver arriba). Además: `intento_acceso.ip` es texto y las revisiones se llaman `0001` y `0002`.

## Elías

_(sin entradas todavía)_

## Hernán

### 2026-10-27 · CH-04 autenticacion (Gate T1: dependencias provisorias)
- **Fecha:** 2026-10-27
- **Qué le pidió al agente:** Generar la propuesta SDD para CH-04 (autenticacion) con especificaciones, decisiones de diseño y tareas. Implementar con TDD estricto el Gate T1 de la ola 2: funciones de seguridad (hashear_password, verificar_password, crear_access_token, decodificar_access_token) en app/core/security.py y dependencias de acceso (get_usuario_actual y requiere_rol) en app/core/dependencies.py con las firmas definitivas, lectura exclusiva de cookie access_token, validación de iat < password_cambiada_en sin truncar microsegundos y validación de roles vigentes.
- **Qué corrigió a mano y por qué:**
  - Se verificó que get_usuario_actual ignore la cabecera Authorization y lea sólo la cookie access_token (caso C-03 y regla 10 de CLAUDE.md).
  - Se aseguró que iat en el JWT se preserve como float con fracciones de segundo (sin truncar a entero) para que la comparación contra password_cambiada_en invalide tokens anteriores de forma exacta (RN-07).
  - Se ajustaron los tests unitarios de AsyncClient pasando cookies en el cliente para mantener la suite limpia sin advertencias de deprecación.

### 2026-10-27 · CH-04 autenticacion (Contratos, repositorios y auto-registro de cliente)
- **Fecha:** 2026-10-27
- **Qué le pidió al agente:** Implementar con TDD estricto los contratos de entrada/salida (schemas.py), repositorios (UsuarioRepository, AsignacionRolRepository, IntentoAccesoRepository, EventoSeguridadRepository), UsuarioUnitOfWork y el endpoint de auto-registro de cliente (POST /auth/registro) con cálculo de bcrypt antes de abrir la transacción, unicidad garantizada por la base (409 ante correo o documento duplicado con rollback total sin filas huérfanas, incluso contra clientes sin usuario como Jorge Gómez), y validación estricta de contratos (422 con extra="forbid" y contraseñas mayores a 72 bytes en UTF-8).
- **Qué corrigió a mano y por qué:**
  - Se verificó que PasswordBcryptStr calcule la longitud en bytes codificados en UTF-8 (no caracteres), garantizando que contraseñas como 37 letras 'ñ' (74 bytes) respondan 422 antes de llegar a bcrypt y eviten errores 500.
  - Se comprobó que el rollback atómico en UsuarioUnitOfWork ante colisión de documento conserve la ficha preexistente intacta (usuario_id=None) y no deje registros sueltos en usuario ni asignacion_rol.
  - Se configuró la base de datos PostgreSQL local creando el rol taller y las bases taller y taller_test, ejecutando alembic upgrade head y validando la suite completa en verde.

## Bruno

_(sin entradas todavía)_

## Joaquín

_(sin entradas todavía)_

## Pendientes para CH-09 (README)

- Cada integrante crea su propio `.env` a partir de `env.example`, su usuario de PostgreSQL y las bases `taller` y `taller_test`.
- Documentar cómo generar la clave de firma (`python -c "import secrets; print(secrets.token_urlsafe(64))"`) y que no se comparte ni se versiona.
- Avisar a Hernán (CH-04) del contrato `app.state.hash_ficticio` / `app.state.bcrypt_semaforo` y del cambio de bcrypt 5.x con más de 72 bytes.
- (CH-02) Alembic y `python seed.py` se corren **desde la raíz del repo**: el `.env` se lee relativo al directorio actual y, si no lo encuentra, falla con un error de configuración (no deja un esquema a medias). Orden de arranque: `alembic upgrade head` y después `python seed.py`.
- (CH-02) Captura del caso C-14: con la base migrada y sembrada, `psql -U taller -d taller -f test/solo_agregado.sql` muestra los siete errores (seis del trigger de sólo agregado y uno de la FK `fk_orden_trabajo_estado_estado_orden`). El texto del último error depende del idioma del servidor.
- (CH-02) Los tests dejan `taller_test` vacía; si se corre `seed.py` a mano sobre `taller_test`, hay que vaciarla antes de correr la suite (o volver a correrla desde `alembic downgrade base` y `upgrade head`).