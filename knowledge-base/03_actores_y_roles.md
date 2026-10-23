# Actores y Roles

## Actores del sistema

| Actor | Descripción | Cómo interactúa |
|---|---|---|
| RECEPCION | Personal de mostrador del taller | Da de alta clientes y vehículos, abre órdenes (con la falla y los repuestos), cancela órdenes pendientes |
| MECANICO | Personal técnico | Inicia una orden (queda asignado), la repara y la termina; consulta repuestos y órdenes |
| ADMIN | Administrador del taller | Mantiene el catálogo de repuestos, repone stock, administra personal y roles, consulta eventos de seguridad, puede terminar o cancelar cualquier orden |
| CLIENTE | Dueño de vehículos | Se registra solo en la web; consulta sus vehículos y órdenes; cancela sus órdenes pendientes |
| SISTEMA | Actor de texto (no es un usuario) | Aparece como `actor` en `evento_seguridad` para los datos iniciales ("Carga de los datos iniciales") |

Los roles viven en su propia tabla (`asignacion_rol`): `usuario` no tiene columna `rol`. Un usuario puede tener varios roles; los vigentes son las filas no revocadas y sin vencer. Los cuatro roles válidos son `ADMIN`, `RECEPCION`, `MECANICO`, `CLIENTE` (CHECK en la base).

## RBAC — Matriz de permisos

Fuente: endpoints de referencia. "Aut." = sólo pide estar autenticado. "Servicio" = no lleva `requiere_rol`; la decisión la toma el servicio.

| Recurso / acción | ADMIN | RECEPCION | MECANICO | CLIENTE |
|---|---|---|---|---|
| Alta de personal (`POST /usuarios`) | ✔ | — | — | — |
| Ver / asignar / revocar roles | ✔ | — | — | — |
| Eventos de seguridad (`GET /eventos`) | ✔ | — | — | — |
| Alta de cliente, ver cliente con vehículos | ✔ | ✔ | — | — |
| Alta de vehículo, baja de vehículo | ✔ | ✔ | — | — |
| `GET /mis-vehiculos`, `GET /mis-ordenes` | Aut. | Aut. | Aut. | Aut. |
| Listar / ver repuestos | ✔ | ✔ | ✔ | — |
| Alta, PATCH, baja de repuesto; reponer; movimientos; precios | ✔ | — | — | — |
| Crear orden | ✔ | ✔ | — | — |
| Listar órdenes (filtro por estado) | ✔ | ✔ | ✔ | — |
| Ver detalle de orden | ✔ | ✔ | ✔ | sólo si es dueño del vehículo (403 si no) |
| Iniciar orden | — | — | ✔ | — |
| Terminar orden | ✔ | — | sólo el mecánico asignado | — |
| Cancelar orden | ✔ | ✔ | — | sólo el dueño del vehículo (Servicio) |
| Catálogo `GET /estados-orden` | Aut. | Aut. | Aut. | Aut. |
| `/auth/yo`, `/auth/cambiar-password`, `/auth/logout` | Aut. | Aut. | Aut. | Aut. |

Reglas de decisión:

- **401** = no autenticado: sin cookie, token inválido o vencido, usuario inexistente o inactivo, o token anterior al último cambio de contraseña (RN-07).
- **403** = sin permiso: lo decide `requiere_rol` consultando los roles vigentes en la base en cada petición (RN-04), o el servicio para lo propio y para cancelar/terminar.
- Cancelar orden: primero se evalúa quién es y qué relación tiene con la orden (403), después si el estado lo permite (409) — RN-12.
- Terminar orden: lo hace el mecánico asignado o un ADMIN (403 si no).
- Los roles del token son informativos; el permiso real es el de la base. `GET /auth/yo` devuelve los roles vigentes y los que dice el token, para mostrar la diferencia.
- Con el cambio de contraseña pendiente (`debe_cambiar_password`), el usuario sólo puede usar `/auth/*` y las rutas de salud; el resto da 403 (RN-06).
- Autoprotección (RN-05): un ADMIN no puede revocarse su propio rol ADMIN y el sistema nunca queda sin administradores vigentes (409).

## Rutas públicas

Accesibles sin autenticación:

- `GET /health/live`
- `GET /health/ready`
- `POST /auth/registro`
- `POST /auth/login`
- `POST /auth/logout`

`GET /auth/yo` y `POST /auth/cambiar-password` pertenecen al grupo abierto (sin el control del cambio obligatorio) pero requieren sesión (401 sin ella).
