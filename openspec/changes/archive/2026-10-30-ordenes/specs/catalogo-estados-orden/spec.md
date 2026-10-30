# Spec Delta

## Purpose

Expone el catálogo de estados de una orden como una lista de sólo lectura, ordenada por posición, y garantiza que los estados que acepta el contrato de la API coinciden exactamente con las filas del catálogo.

## ADDED Requirements

### Requirement: Consulta del catálogo por posición
`GET /estados-orden` SHALL responder 200 con la lista de los estados del catálogo, cada uno con `codigo`, `descripcion`, `posicion` y `es_final`, ordenada por `posicion` ascendente. Sólo MUST pedir estar autenticado (cualquier rol, o ninguno).

#### Scenario: Los cuatro estados del seed por posición (C-17)
- **WHEN** un usuario autenticado pide `GET /estados-orden` con la base sembrada
- **THEN** responde 200 con PENDIENTE (1), EN_REPARACION (2), TERMINADA (3) y CANCELADA (4), en ese orden, y sólo TERMINADA y CANCELADA tienen `es_final` verdadero

#### Scenario: Un cliente sin rol de personal también lo ve
- **WHEN** el usuario del cliente (sólo rol CLIENTE) pide el catálogo
- **THEN** responde 200 con los cuatro estados

#### Scenario: Sin sesión (C-17)
- **WHEN** se pide `GET /estados-orden` sin la cookie de sesión
- **THEN** responde 401

### Requirement: El catálogo no se escribe desde la API
La API MUST NOT exponer ninguna ruta para crear, editar ni borrar estados (AP-02, RN-19). El acceso a datos del catálogo SHALL ser de sólo lectura y no ofrecer operaciones de escritura.

#### Scenario: No hay rutas de escritura del catálogo
- **WHEN** se piden `POST`, `PUT`, `PATCH` o `DELETE` sobre `/estados-orden`
- **THEN** ninguna de esas operaciones está declarada (405) y el catálogo no cambia

#### Scenario: El acceso a datos del catálogo no escribe
- **WHEN** se inspecciona el repositorio del catálogo
- **THEN** no hereda del repositorio genérico y no ofrece `add`, `update` ni `delete`

### Requirement: El enum del contrato coincide con el catálogo
Los estados que el contrato acepta como parámetro o devuelve SHALL ser exactamente los códigos de las filas del catálogo cargado por `seed.py`. Un estado que el contrato no declara MUST rechazarse con 422 sin consultar la base.

#### Scenario: Enum y catálogo iguales
- **WHEN** se comparan los valores del enum de estados con los códigos de `estado_orden` después de sembrar
- **THEN** son el mismo conjunto de cuatro códigos

#### Scenario: Estado no declarado (C-17)
- **WHEN** se pide `GET /ordenes?estado=ENTREGADA`
- **THEN** responde 422
