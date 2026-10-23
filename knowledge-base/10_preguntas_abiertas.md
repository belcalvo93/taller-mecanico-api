# Preguntas Abiertas

Todas las preguntas e inconsistencias detectadas al armar la KB (IN-01 a IN-04 y las 11 preguntas priorizadas) se resolvieron con el equipo el 2026-10-23. Las resoluciones están registradas en `09_decisiones_y_supuestos.md` (DD-12 a DD-18 y los supuestos SU-01, SU-02, SU-03 y SU-06 confirmados), por lo que acá no queda nada pendiente.

## Inconsistencias detectadas

### IN-02 — "Abierto" contra "autenticado"
**Consigna dice**: `/auth/yo` y `/auth/cambiar-password` son del grupo "Abierto" pero su columna "Quién" dice "Autenticado".
**Impacto**: si se interpreta "abierto" como sin autenticación, `/auth/yo` no podría devolver el usuario.
**Resolución propuesta**: "abierto" = sin el control del cambio obligatorio; igual exigen cookie válida (401 sin ella). Ver SU-05.
**Estado**: se mantiene como supuesto SU-05; se valida con el caso C-09 durante `autorizacion-y-roles`.

## Preguntas abiertas (priorizadas)

| Prioridad | Pregunta | Bloquea | Decisor |
|-----------|----------|---------|---------|
| Baja | ¿Hace falta ajustar los supuestos SU-04, SU-05 y SU-07 al correr los casos C-01..C-19? Se validan durante la implementación. | Cada change que los toca | Responsable del change |

## Campos de discovery inferidos

[DISCOVERY] `scale` se infiere como `team` con confianza media: la consigna describe un taller con personal y clientes que se auto-registran, sin números de usuarios. Confirmar si importa más allá del TP.
