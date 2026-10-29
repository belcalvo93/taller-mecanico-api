# Spec Delta

## Purpose

Permite a un visitante registrarse como cliente (`POST /auth/registro`) creando en una sola transacción el usuario, su asignación de rol `CLIENTE`, su ficha de cliente y el evento de seguridad, garantizando unicidad por la base de datos sin dejar filas sueltas ni permitir escalamiento de roles.

## ADDED Requirements

### Requirement: Auto-registro atómico de cliente (RN-02)
`POST /auth/registro` SHALL calcular el hash `bcrypt` de la contraseña antes de abrir la transacción y luego, dentro de un único `UnitOfWork`, insertar el registro en `usuario`, su fila en `asignacion_rol` con rol `CLIENTE`, su ficha en `cliente` vinculada por `usuario_id` y una línea en `evento_seguridad`, respondiendo `201` sin incluir `password_hash`. Si cualquiera de las inserciones falla, MUST revertirse la transacción completa de modo que no quede ninguna fila creada.

#### Scenario: Registro exitoso crea usuario, rol CLIENTE, ficha de cliente y evento
- **WHEN** se envía `POST /auth/registro` con `email`, `nombre`, `password`, `documento` y `telefono` válidos y no registrados
- **THEN** responde `201` con los datos del cliente/usuario registrado (sin `password_hash`) y en la base existen el `usuario`, la `asignacion_rol` (`CLIENTE`), el `cliente` vinculado y el registro en `evento_seguridad` (C-02)

#### Scenario: Rollback total si falla la creación del cliente
- **WHEN** `POST /auth/registro` inserta el `usuario` y el rol pero la inserción de `cliente` falla (por ejemplo, por `documento` ya existente en la base)
- **THEN** responde `409` y no quedan filas nuevas ni en `usuario`, ni en `asignacion_rol`, ni en `evento_seguridad` (RN-02, C-02)

### Requirement: Unicidad de correo y documento garantizada por la base (RN-01, RN-02, RN-18)
El sistema SHALL delegar la verificación de unicidad de `usuario.email` y `cliente.documento` en las restricciones `UNIQUE` de PostgreSQL, traduciendo el `IntegrityError` a `409` con un mensaje propio y sin devolver texto interno de la base. Si el documento ya pertenece a un cliente del taller sin usuario (como Jorge en el seed), el registro MUST responder `409` sin apropiarse de esa ficha.

#### Scenario: Correo repetido
- **WHEN** se envía `POST /auth/registro` con un `email` que ya existe en `usuario`
- **THEN** responde `409` con mensaje propio, sin texto de PostgreSQL y sin crear filas nuevas (C-02)

#### Scenario: Documento repetido o perteneciente a un cliente existente del taller
- **WHEN** se envía `POST /auth/registro` con un `documento` que ya pertenece a otro cliente (con o sin usuario asociado)
- **THEN** responde `409` con mensaje propio, la ficha existente conserva su `usuario_id` original y el nuevo `usuario` no queda creado (RN-02, C-02)

### Requirement: Validación estricta del contrato de registro
El contrato de entrada de `POST /auth/registro` SHALL configurar `extra="forbid"` para rechazar cualquier campo no declarado (como `rol` o `activo`) con `422`, y MUST validar que la contraseña codificada en UTF-8 tenga entre el mínimo permitido y un máximo de **72 bytes** (no caracteres) antes de invocar `bcrypt`.

#### Scenario: Intento de inyectar rol o campos extra en el registro
- **WHEN** se envía `POST /auth/registro` incluyendo un campo adicional como `"rol": "ADMIN"`
- **THEN** responde `422` sin tocar la base de datos

#### Scenario: Contraseña que supera 72 bytes en UTF-8
- **WHEN** se envía `POST /auth/registro` con una contraseña cuya representación UTF-8 supera los 72 bytes (por ejemplo, 73 caracteres ASCII o 37 letras `ñ` que suman 74 bytes)
- **THEN** responde `422` antes de llamar a `bcrypt` (nunca `500`)
