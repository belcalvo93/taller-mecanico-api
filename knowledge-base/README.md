# Taller mecánico (API) — Base de Conocimiento

Base de conocimiento generada a partir de `docs/consigna-tp.md` (fuente de verdad) y del Discovery del 2026-10-23 (`discovery/discovery.md`: reparto del equipo, plazos y aclaraciones del profesor en clase). No se consultaron fuentes externas.

## Índice de Archivos

| Archivo | Contenido |
|---------|-----------|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, objetivos por actor, alcance, fuera de alcance, criterios de evaluación |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack, arquitectura en capas, integraciones y los 33 endpoints de referencia |
| [03_actores_y_roles.md](03_actores_y_roles.md) | Actores, matriz RBAC, reglas 401/403, rutas públicas |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | 13 tablas, ERD, restricciones, migraciones, seed data |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | RN-01 a RN-20, reglas técnicas transversales y aclaraciones del profesor (AP-01..AP-08) |
| [06_funcionalidades.md](06_funcionalidades.md) | 9 épicas (una por change) con historias US-001..US-023 y criterios de aceptación |
| [07_flujos_principales.md](07_flujos_principales.md) | 13 flujos extremo a extremo: registro, login, autorización, órdenes, stock, puesta en marcha |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Patrones, estructura de directorios, seguridad, variables de entorno, estrategia de tests |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | Decisiones (DD-01..DD-11) y supuestos (SU-01..SU-07), reparto en olas |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | Inconsistencias detectadas y preguntas abiertas priorizadas |

## Quick Start para Desarrolladores

1. Entender el dominio → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. Entender los datos → [04](04_modelo_de_datos.md)
3. Entender las reglas → [05](05_reglas_de_negocio.md)
4. Entender la arquitectura → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. Implementar → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. Antes de codificar → [10](10_preguntas_abiertas.md), [09](09_decisiones_y_supuestos.md)

## Resumen Ejecutivo

API asincrónica (FastAPI + SQLModel + PostgreSQL) para un taller mecánico: clientes y vehículos, órdenes de trabajo, stock de repuestos y acceso por 4 roles con vigencia, en capas Router → Service → UoW → Repository → Model. Es el TP integrador de Programación III (UTN, Unidades 1 a 6), a entregar el viernes 30/10/2026 por un equipo de 5 en 4 olas, con SDD y TDD estricto y evaluación por demo en vivo.

Las garantías que se evalúan más fuerte: el esquema levanta con `alembic upgrade head` (incluido el trigger de sólo agregado y el ciclo up/down/up), la autenticación por cookie HttpOnly sin enumeración de cuentas, los roles consultados en la base en cada petición, y las operaciones de negocio en una sola transacción (registro, terminar orden, cambiar precio).
