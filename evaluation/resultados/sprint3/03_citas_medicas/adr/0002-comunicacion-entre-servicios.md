<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0002: Comunicación entre servicios

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Decisión D-02 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere que la reserva de citas se confirme solo tras el pago y que los resultados de laboratorio se notifiquen al médico antes de mostrarse al paciente. Para cumplir con la consistencia inmediata en estos casos críticos, se opta por comunicación síncrona HTTP. Para el resto de interacciones, se emplean eventos asíncronos RabbitMQ, garantizando resiliencia y desacoplamiento. Esta combinación satisface los requisitos RNF‑06 y RNF‑10.

## Decisión

Se utiliza comunicación síncrona (HTTP) solo para validaciones críticas (p.ej. usuarios‑pagos) y eventos asíncronos vía RabbitMQ para todo lo demás (p.ej. confirmación de pago, notificaciones de resultados).

## Justificación

Los requisitos de consistencia inmediata son pocos (validar cuenta antes de pagar); el resto se beneficia de la resiliencia y desacoplamiento de eventos, cumpliendo RNF‑06 y RNF‑10.

## Consecuencias

Positivas:

- Garantiza consistencia inmediata en flujos críticos como la validación de pago, evitando estados inconsistentes.
- Reduce acoplamiento entre microservicios, permitiendo que cada uno escale y se recupere de forma independiente.
- Mejora la tolerancia a fallos; si el laboratorio está caído, los demás servicios continúan operando y los resultados se procesan cuando esté disponible.
- Cumple con la limitación de 60 peticiones/minuto y 20 búsquedas de horarios, evitando sobrecarga en la infraestructura.

Negativas:

- Introduce complejidad adicional al manejar dos patrones de comunicación, requiriendo más código y pruebas.
- La comunicación síncrona puede generar cuellos de botella y latencia en los flujos críticos, afectando la experiencia del usuario.
- Se necesita implementar mecanismos de idempotencia y reintentos para evitar duplicados en los eventos asíncronos.
- Requiere monitoreo y alertas específicas para detectar fallos en los canales RabbitMQ y HTTP, aumentando la carga operativa.

## Trazabilidad

Servicios afectados: `pagos`, `laboratorio`, `administracion`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RF-21 | Una cita reservada en línea solo queda confirmada cuando se aprueba su pago, y si no se paga en 15 minutos el horario vuelve a quedar libre. |
| RF-19 | Cuando llega un resultado, el médico que pidió el examen recibe un aviso, y el paciente lo ve en su cuenta solo después de que el médico lo haya revisado. |
| RNF-06 | Si el laboratorio no responde, el resto del sistema sigue funcionando y los resultados se reciben cuando vuelva a estar disponible. |
| RNF-10 | Ninguna persona ni ningún equipo puede hacer más de 60 peticiones por minuto, y como máximo 20 de ellas pueden ser búsquedas de horarios libres. |
