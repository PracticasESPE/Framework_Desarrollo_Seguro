<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0005: Bases de datos aisladas

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-10 |
| Origen | Decisión D-05 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Para cumplir con RNF-09, cada microservicio debe manejar su propia base de datos PostgreSQL. Esto permite que el catálogo, los pedidos y los pagos escalen y fallen de forma independiente. La separación de esquemas evita que la caída de un servicio afecte a los demás. Así se garantiza la disponibilidad continua del sistema.

## Decisión

Cada microservicio posee su propia base PostgreSQL, sin compartir esquemas.

## Justificación

RNF-09 exige que cada componente pueda escalar y fallar independientemente.

## Consecuencias

Positivas:

- Escalabilidad independiente: cada servicio puede aumentar su capacidad de almacenamiento sin afectar a los demás.
- Resiliencia mejorada: fallos en una base de datos no provocan caídas en otros servicios.
- Seguridad de datos: la separación de esquemas reduce el riesgo de exposición de información sensible entre servicios.
- Mantenimiento simplificado: cambios de esquema se realizan localmente sin requerir coordinación global.

Negativas:

- Mayor consumo de recursos: cada microservicio necesita su propia instancia de PostgreSQL, aumentando el uso de CPU y memoria.
- Complejidad operativa: la gestión de múltiples bases de datos requiere más tareas de monitoreo, backup y actualización.
- Limitaciones en consultas transaccionales: no se pueden realizar transacciones distribuidas entre servicios sin mecanismos adicionales.
- Duplicación de costos de backup y replicación: cada base necesita su propio esquema de respaldo, incrementando el esfuerzo y el almacenamiento.

## Trazabilidad

Servicios afectados: todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-09 | El catálogo, los pedidos y los pagos deben poder actualizarse y crecer por separado, cada uno con sus propios datos, sin que la caída de uno detenga a los demás. |
