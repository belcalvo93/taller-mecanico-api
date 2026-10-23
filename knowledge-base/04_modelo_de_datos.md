# Modelo de Datos

Los nombres de tablas y columnas son OBLIGATORIOS (los usan los casos de prueba y la corrección). Se pueden agregar columnas, no quitar ni renombrar.

Reglas generales: todas las fechas son `timestamptz`; el dinero es `NUMERIC` y en Python `Decimal`, nunca `float`; cada clave foránea lleva su índice (PostgreSQL no lo crea solo).

## Dominios

| Módulo | Entidades |
|---|---|
| `usuarios` | Usuario, AsignacionRol, IntentoAcceso, EventoSeguridad |
| `clientes` | Cliente, Vehiculo |
| `repuestos` | Repuesto, MovimientoStock, HistorialPrecio |
| `ordenes` | EstadoOrden (catálogo), OrdenTrabajo, ItemOrden, HistorialEstadoOrden |
| `health` | (sin entidades; sólo `router.py`) |

## ERD (relaciones)

```
Usuario 1 ───< AsignacionRol            (roles; 1 usuario, 0..* asignaciones)
Usuario 0..1 ─── 0..1 Cliente           (uno a uno opcional: cliente.usuario_id UNIQUE, nulo permitido)
Cliente 1 ───< Vehiculo                 (asociación)
Vehiculo 1 ───< OrdenTrabajo            (asociación)
Usuario 0..1 ───< OrdenTrabajo          (mecánico: 0..* órdenes, 0..1 mecánico)
EstadoOrden 1 ───< OrdenTrabajo         («catalog», FK a estado_orden.codigo)
OrdenTrabajo 1 ◆───< ItemOrden          (composición: 1 orden, 1..* ítems)
Repuesto 1 ───< ItemOrden               (asociación)
OrdenTrabajo 1 ◆───< HistorialEstadoOrden  (composición, «appendOnly»)
Repuesto 1 ───< MovimientoStock         («appendOnly»)
Repuesto 1 ───< HistorialPrecio         («appendOnly»)
IntentoAcceso, EventoSeguridad          (sin relación con ninguna otra tabla)
```

## Entidades

### usuario
- Columnas: `id`, `email`, `nombre`, `password_hash`, `activo`, `debe_cambiar_password`, `password_cambiada_en` (timestamptz, nulo permitido).
- Constraints: `email` UNIQUE.
- No tiene columna `rol`. `Usuario.cliente` devuelve un objeto (no una lista).

### asignacion_rol
- Columnas: `id`, `usuario_id`, `rol`, `desde`, `vence_en` (nulo), `revocada_en` (nulo), `otorgada_por` (nulo).
- Constraints: CHECK `rol` IN (`ADMIN`, `RECEPCION`, `MECANICO`, `CLIENTE`); ÍNDICE ÚNICO PARCIAL `(usuario_id, rol) WHERE revocada_en IS NULL`.
- Revocar escribe `revocada_en`; la fila no se borra nunca. Reasignar un rol vencido cierra la fila anterior y abre una nueva.
- Índice por FK: `usuario_id` (y `otorgada_por` si es FK a usuario).

### intento_acceso
- Columnas: `id`, `cuando`, `email`, `ip`, `exito`.
- Constraints: índice `(email, ip, cuando)`.
- Se escribe desde una sesión y una transacción propias, que se confirman siempre.

### evento_seguridad
- Columnas: `id`, `cuando`, `actor` (texto), `accion`.
- Constraints: ninguna extra. `actor` es texto, no FK (el actor SISTEMA no es un usuario).

### cliente
- Columnas: `id`, `usuario_id` (nulo permitido), `nombre`, `documento`, `telefono`.
- Constraints: `usuario_id` UNIQUE; `documento` UNIQUE.

### vehiculo
- Columnas: `id`, `cliente_id`, `patente`, `marca`, `modelo`, `anio`, `borrado_en` (nulo).
- Constraints: ÍNDICE ÚNICO PARCIAL `(patente) WHERE borrado_en IS NULL`; CHECK `anio BETWEEN 1950 AND 2100`.
- Borrado lógico: un vehículo vendido se da de baja y el comprador puede registrarlo con la misma patente; las órdenes viejas siguen.
- Índice por FK: `cliente_id`.

### repuesto
- Columnas: `id`, `codigo`, `descripcion`, `precio` (NUMERIC 10,2), `stock`, `borrado_en` (nulo).
- Constraints: ÍNDICE ÚNICO PARCIAL `(codigo) WHERE borrado_en IS NULL`; CHECK `precio > 0`; CHECK `stock >= 0`.
- El stock no se edita por PATCH; sólo cambia por movimientos (RN-14).

### estado_orden (catálogo)
- Columnas: `codigo` (clave primaria), `descripcion`, `posicion`, `es_final`.
- Constraints: `posicion` UNIQUE.
- La migración la crea VACÍA; las filas las carga `seed.py`. En el código los estados se nombran con un enum (un estado no declarado da 422). El enum y el catálogo tienen que coincidir; agregar un estado obliga a tocar los dos y el servicio.

### orden_trabajo
- Columnas: `id`, `vehiculo_id`, `mecanico_id` (nulo), `estado`, `falla`, `creada_en`, `total` (NUMERIC 12,2).
- Constraints: `estado` es FK a `estado_orden.codigo` (nunca CHECK con lista); CHECK `total >= 0`.
- Índices por FK: `vehiculo_id`, `mecanico_id`, `estado`.

### item_orden
- Columnas: `id`, `orden_id`, `repuesto_id`, `cantidad`, `precio_unitario` (NUMERIC 10,2).
- Constraints: CHECK `cantidad > 0`; CHECK `precio_unitario > 0`; UNIQUE `(orden_id, repuesto_id)`.
- Composición: un ítem no existe sin su orden. El precio se copia del repuesto al crear.
- Índices por FK: `orden_id`, `repuesto_id`.

### historial_estado_orden (sólo agregado)
- Columnas: `id`, `orden_id`, `desde_estado` (nulo), `hasta_estado`, `usuario_id`, `cuando`.
- Constraints: `desde_estado` y `hasta_estado` son FK a `estado_orden.codigo`; SÓLO AGREGADO (trigger).
- Índices por FK: `orden_id`, `desde_estado`, `hasta_estado`, `usuario_id`.

### movimiento_stock (sólo agregado)
- Columnas: `id`, `repuesto_id`, `orden_id` (nulo), `usuario_id`, `cantidad`, `motivo`, `cuando`.
- Constraints: CHECK `cantidad <> 0`; SÓLO AGREGADO (trigger).
- Índices por FK: `repuesto_id`, `orden_id`, `usuario_id`.

### historial_precio_repuesto (sólo agregado)
- Columnas: `id`, `repuesto_id`, `usuario_id`, `precio_anterior` (NUMERIC 10,2), `precio_nuevo` (NUMERIC 10,2), `cuando`.
- Constraints: CHECK `precio_nuevo > 0`; CHECK `precio_nuevo <> precio_anterior`; SÓLO AGREGADO (trigger).
- Índices por FK: `repuesto_id`, `usuario_id`.

## Migraciones

1. **Migración 1** — generada con `alembic revision --autogenerate`, con todas las tablas. Crea `estado_orden` vacía.
2. **Migración 2** — escrita a mano: función y trigger que rechazan cualquier `UPDATE` o `DELETE` sobre `historial_estado_orden`, `movimiento_stock` e `historial_precio_repuesto` (RN-15). La comparación automática de Alembic no ve funciones ni triggers.

Cada migración lleva un comentario que dice que se leyó antes de aplicarla. `upgrade head` → `downgrade base` → `upgrade head` debe andar. Los modelos los escribe sólo el change `esquema-y-migraciones`.

## Seed data inicial (`seed.py`)

`seed.py` vacía las tablas y carga, como mínimo, lo siguiente. El catálogo de estados se carga PRIMERO. Las contraseñas son de mentira y viven sólo en ese archivo.

- **Catálogo de estados**: PENDIENTE (posición 1), EN_REPARACION (2), TERMINADA (3, final), CANCELADA (4, final), cada uno con su descripción.
- **Usuarios**: `admin@example.com` y `admin2@example.com` (ADMIN), `recepcion@example.com` (RECEPCION), `mecanico@example.com` y `mecanico2@example.com` (MECANICO), `cliente@example.com` (CLIENTE) y `nuevo@example.com` (MECANICO, con el cambio de contraseña obligatorio).
- **Clientes**: Laura (con usuario `cliente@example.com`, dos vehículos) y Jorge (sin usuario, un vehículo).
- **Repuestos** (cada stock cargado como un movimiento "Stock inicial"): filtro de aceite `FIL-001` (stock 10, precio 8500.00), pastillas de freno delanteras `FRE-010` (stock 4, precio 32000.00), bujía (stock 2) y aceite 5W30 por litro `ACE-530` (stock 20, precio 12000.00).
- **Órdenes**: la 1, PENDIENTE, del primer vehículo de Laura; la 2, EN_REPARACION, del vehículo de Jorge, asignada a `mecanico@example.com`, con 4 BUJÍAS CUANDO HAY 2 (a propósito, para el caso C-11).
- **Historial de precios**: una línea del filtro de aceite, de 8000 a 8500.
- **Historial de seguridad**: una línea con actor `SISTEMA`: "Carga de los datos iniciales".

Los datos que la consigna no fija (patentes, precio de la bujía, documentos, teléfonos, contraseñas) los define quien escribe el seed; ver `10_preguntas_abiertas.md`.
