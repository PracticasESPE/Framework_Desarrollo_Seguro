<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0002: Comunicación síncrona vs asíncrona

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-25 |
| Origen | Decisión D-02 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere que las validaciones de seguridad y autorización se realicen de forma inmediata, mientras que los procesos de pagos, resultados de laboratorio y auditoría deben ser tolerantes a fallos y desacoplados. Para cumplir con los requisitos de alta disponibilidad y resiliencia, se decide usar comunicación síncrona (HTTP) para las validaciones y comunicación asíncrona (RabbitMQ) para los eventos.

## Decisión

Se usa comunicación síncrona (HTTP) para validaciones de seguridad y autorización; se usa comunicación asíncrona (RabbitMQ) para eventos de pagos, resultados de laboratorio, notificaciones y auditoría.

## Justificación

Requisitos de alta disponibilidad y resiliencia (RF-23, RF-25, RF-27, RF-22) requieren desacoplamiento; la validación de tokens y permisos (RF-03, RF-04, RF-06) necesita respuesta inmediata.

## Consecuencias

Positivas:

- La comunicación asíncrona permite que el laboratorio envíe resultados sin bloquear el resto del sistema, cumpliendo RF-23 y RF-22, y garantiza que las citas se confirmen solo cuando el pago sea aprobado, satisfaciendo RF-25.
- El uso de HTTP para validaciones asegura respuestas inmediatas a los requisitos RF-03, RF-04 y RF-06, reduciendo la latencia en la autenticación y mejorando la experiencia del usuario.
- El desacoplamiento de eventos facilita la escalabilidad y la resiliencia, permitiendo que el sistema reciba avisos de pagos (RF-27) y recordatorios (RF-28) sin depender de la disponibilidad de los servicios externos.

Negativas:

- La arquitectura asíncrona introduce complejidad operativa adicional, requiriendo monitoreo y gestión de colas RabbitMQ para evitar cuellos de botella y garantizar la entrega de mensajes.
- Existe un riesgo de pérdida o duplicación de eventos si la persistencia de mensajes no se configura correctamente, lo que podría afectar la trazabilidad de auditoría y la visibilidad de resultados para los pacientes.
- El uso de HTTP para validaciones aumenta la carga en los servicios de autenticación, lo que puede requerir escalado horizontal y generar costos operativos mayores en el entorno de contenedores.

## Trazabilidad

Servicios afectados: `auth`, `citas`, `laboratorio`, `pagos`, `gestion`

| Requisito | Texto del documento |
|---|---|
| RF-03 | El paciente se registra con su correo, su número de cédula y su fecha de nacimiento; la cuenta se activa cuando confirma el correo, y una misma cédula no puede tener dos cuentas. |
| RF-04 | Si alguien falla cinco veces seguidas la contraseña de una cuenta, el sistema le pide además un código que se envía al correo del paciente. |
| RF-06 | El personal médico y administrativo entra con su contraseña y además con un código de un solo uso que le da una aplicación de autenticación en el móvil. |
| RF-21 | El laboratorio externo envía al sistema los resultados de cada examen, y el sistema solo acepta envíos autenticados del laboratorio con archivos PDF de hasta 5 MB. |
| RF-22 | Cuando llega un resultado, el médico que pidió el examen recibe un aviso, y el paciente lo ve en su cuenta solo después de que el médico lo haya revisado. |
| RF-23 | Si el laboratorio no responde, el resto del sistema sigue funcionando y los resultados se reciben cuando vuelva a estar disponible. |
| RF-25 | Una cita reservada en línea solo queda confirmada cuando se aprueba su pago, y si no se paga en 15 minutos el horario vuelve a quedar libre. |
| RF-27 | La pasarela avisa de cada pago aprobado o devuelto, y el sistema solo acepta los avisos que demuestren venir de la pasarela. |
| RF-28 | El paciente recibe un recordatorio por correo y por mensaje de texto 24 horas antes de su cita. |
| RF-29 | Los recordatorios y los correos nunca incluyen el motivo de la consulta, el diagnóstico ni la especialidad, solo la fecha, la hora y la sede. |
