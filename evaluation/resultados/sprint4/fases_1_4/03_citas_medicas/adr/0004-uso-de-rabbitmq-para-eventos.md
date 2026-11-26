<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0004: Uso de RabbitMQ para eventos

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-25 |
| Origen | Decisión D-04 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere una arquitectura orientada a eventos para desacoplar los microservicios y garantizar la tolerancia a fallos, especialmente cuando el laboratorio externo no responde. RabbitMQ permite publicar y suscribirse a eventos de dominio como pagos aprobados y resultados de laboratorio, cumpliendo con los requisitos de disponibilidad y comunicación asíncrona.

## Decisión

Se implementa RabbitMQ como broker de eventos para publicar y suscribirse a eventos de dominio (pago aprobado, resultado disponible, recordatorio de cita, acceso urgente).

## Justificación

Facilita la arquitectura orientada a eventos requerida por RF-23 (tolerancia a fallos del laboratorio) y permite que servicios reaccionen sin acoplamiento directo.

## Consecuencias

Positivas:

- Facilita la escalabilidad horizontal de los servicios al permitir que cada microservicio procese eventos de forma independiente.
- Mejora la resiliencia del sistema, ya que los eventos se almacenan y se procesan cuando el consumidor esté disponible, evitando bloqueos por dependencias externas.
- Simplifica la integración de nuevos servicios, ya que solo necesitan suscribirse a los tópicos relevantes sin modificar la lógica de los productores.
- Reduce el acoplamiento entre dominios, lo que facilita el mantenimiento y la evolución de cada servicio de forma aislada.

Negativas:

- Requiere una capa adicional de infraestructura (RabbitMQ) que debe ser monitoreada, respaldada y escalada, aumentando la complejidad operativa.
- El manejo de la persistencia y la entrega de mensajes introduce latencia y posibles retrasos en la notificación de eventos críticos.
- Si la configuración de colas y exchanges no se gestiona correctamente, puede haber pérdida de mensajes o duplicados, afectando la consistencia de datos.
- El desarrollo y pruebas de los consumidores de eventos demandan más esfuerzo, ya que deben manejar casos de reintentos y estados intermedios.

## Trazabilidad

Servicios afectados: `citas`, `laboratorio`, `pagos`, `gestion`

| Requisito | Texto del documento |
|---|---|
| RF-21 | El laboratorio externo envía al sistema los resultados de cada examen, y el sistema solo acepta envíos autenticados del laboratorio con archivos PDF de hasta 5 MB. |
| RF-22 | Cuando llega un resultado, el médico que pidió el examen recibe un aviso, y el paciente lo ve en su cuenta solo después de que el médico lo haya revisado. |
| RF-23 | Si el laboratorio no responde, el resto del sistema sigue funcionando y los resultados se reciben cuando vuelva a estar disponible. |
| RF-25 | Una cita reservada en línea solo queda confirmada cuando se aprueba su pago, y si no se paga en 15 minutos el horario vuelve a quedar libre. |
| RF-27 | La pasarela avisa de cada pago aprobado o devuelto, y el sistema solo acepta los avisos que demuestren venir de la pasarela. |
| RF-28 | El paciente recibe un recordatorio por correo y por mensaje de texto 24 horas antes de su cita. |
| RF-29 | Los recordatorios y los correos nunca incluyen el motivo de la consulta, el diagnóstico ni la especialidad, solo la fecha, la hora y la sede. |
| RF-36 | La agenda, la historia clínica, el laboratorio y los pagos deben poder actualizarse por separado, cada uno con sus propios datos, y a los datos de la historia clínica solo accede su propio servicio. |
