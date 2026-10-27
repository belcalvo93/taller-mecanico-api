-- Caso C-14: las tablas de sólo agregado rechazan UPDATE y DELETE (RN-15).
--
-- Cómo correrlo (desde la raíz del repo, con la base migrada y sembrada):
--     alembic upgrade head
--     python seed.py
--     psql -U taller -d taller -f test/solo_agregado.sql
-- (en las pruebas automáticas se usa taller_test en lugar de taller)
--
-- Son SIETE sentencias y las siete tienen que fallar. psql no se detiene en el primer
-- error (ON_ERROR_STOP off) y, sin BEGIN/COMMIT, cada sentencia es su propia
-- transacción: un error no arrastra a las siguientes. Ninguna modifica datos.

\set ON_ERROR_STOP off
\encoding UTF8

-- 1. UPDATE sobre historial_estado_orden
-- Esperado: ERROR:  La tabla historial_estado_orden es de sólo agregado: no se permite UPDATE
UPDATE historial_estado_orden SET hasta_estado = 'CANCELADA' WHERE id = 1;

-- 2. DELETE sobre historial_estado_orden
-- Esperado: ERROR:  La tabla historial_estado_orden es de sólo agregado: no se permite DELETE
DELETE FROM historial_estado_orden WHERE id = 1;

-- 3. UPDATE sobre movimiento_stock
-- Esperado: ERROR:  La tabla movimiento_stock es de sólo agregado: no se permite UPDATE
UPDATE movimiento_stock SET cantidad = 999 WHERE id = 1;

-- 4. DELETE sobre movimiento_stock
-- Esperado: ERROR:  La tabla movimiento_stock es de sólo agregado: no se permite DELETE
DELETE FROM movimiento_stock WHERE id = 1;

-- 5. UPDATE sobre historial_precio_repuesto
-- Esperado: ERROR:  La tabla historial_precio_repuesto es de sólo agregado: no se permite UPDATE
UPDATE historial_precio_repuesto SET precio_nuevo = 1 WHERE id = 1;

-- 6. DELETE sobre historial_precio_repuesto
-- Esperado: ERROR:  La tabla historial_precio_repuesto es de sólo agregado: no se permite DELETE
DELETE FROM historial_precio_repuesto WHERE id = 1;

-- 7. Una orden llevada a un estado que no está en el catálogo estado_orden (RN-19)
-- Esperado: ERROR:  inserción o actualización en la tabla «orden_trabajo» viola la llave foránea «fk_orden_trabajo_estado_estado_orden»
-- (el idioma del texto depende de lc_messages del servidor, el nombre de la restricción no)
UPDATE orden_trabajo SET estado = 'DEMORADA' WHERE id = 1;
