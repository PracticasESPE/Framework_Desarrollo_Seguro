<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0002: Comunicación síncrona vs asíncrona

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Decisión D-02 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `16229f92f991`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema necesita garantizar que las operaciones críticas, como matrículas y registro de notas, se realicen con datos consistentes y bajo los límites de rendimiento establecidos, mientras que las notificaciones y auditorías pueden tolerar eventualidad. Para cumplir con los requisitos de rendimiento (RNF-04) y la independencia de fallos en certificados (RF-30), se opta por comunicación síncrona HTTP para flujos críticos y eventos asíncronos RabbitMQ para procesos secundarios.

## Decisión

Se usa comunicación síncrona (HTTP) entre servicios que requieren datos consistentes en tiempo real (p.ej., matriculas‑&gt;catalogo, notas‑&gt;catalogo) y eventos asíncronos (RabbitMQ) para notificaciones y auditorías.

## Justificación

Los requisitos de rendimiento (RNF-04) y la necesidad de que fallos en certificados no bloqueen matrículas (RF-30) favorecen el desacoplamiento mediante eventos. Las notificaciones (RF-24, RF-25) se implementan como consumidores de eventos para no afectar la latencia de los flujos críticos.

## Consecuencias

Positivas:

- Mejora la latencia de los flujos críticos al usar HTTP para operaciones que requieren datos consistentes en tiempo real.
- Facilita la resiliencia al desacoplar procesos de notificación y auditoría mediante eventos, evitando bloqueos por fallos en certificados.
- Permite escalar horizontalmente los consumidores de eventos sin afectar la lógica de negocio principal.
- Reduce la complejidad de las transacciones distribuidas al delegar la consistencia eventual a los eventos.

Negativas:

- Aumenta la complejidad operativa al gestionar dos modelos de comunicación y garantizar la coherencia eventual.
- Requiere mecanismos de compensación y reintentos para eventos perdidos, incrementando la carga de monitoreo.
- Puede introducir latencia adicional en la entrega de notificaciones si el broker RabbitMQ sufre cuellos de botella.
- El diseño híbrido exige más pruebas de integración y un mayor esfuerzo de documentación.

## Trazabilidad

Servicios afectados: `notificaciones`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RF-30 | La matrícula, las calificaciones y los certificados deben poder actualizarse por separado, y un fallo en los certificados no puede impedir matricularse ni registrar notas. |
| RNF-04 | Durante las dos semanas de matrícula, el sistema debe atender a 1.200 estudiantes conectados a la vez sin que una matrícula tarde más de tres segundos. |
| RF-24 | El estudiante recibe un correo cuando se publican sus notas y cuando su matrícula queda confirmada. |
| RF-25 | Los docentes reciben un recordatorio tres días antes de que cierre el plazo para registrar las notas. |
