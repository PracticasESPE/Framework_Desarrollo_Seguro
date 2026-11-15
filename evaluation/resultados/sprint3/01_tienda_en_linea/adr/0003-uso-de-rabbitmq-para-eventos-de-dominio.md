<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0003: Uso de RabbitMQ para eventos de dominio

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Decisión D-03 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere desacoplar los microservicios de pagos, pedidos y notificaciones para evitar dependencias circulares y garantizar la resiliencia ante fallos. Se decide usar RabbitMQ como bus de eventos para publicar y consumir eventos de dominio como "pedido creado", "pago recibido", "pedido cancelado" y "estado actualizado".

## Decisión

Se emplea RabbitMQ para publicar eventos de "pedido creado", "pago recibido", "pedido cancelado" y "estado actualizado".

## Justificación

Los eventos permiten que pagos, notificaciones y auditoría reaccionen sin crear dependencias circulares y cumplen con la necesidad de independencia de fallos (RNF-09).

## Consecuencias

Positivas:

- Mejora la escalabilidad y la independencia de fallos al permitir que cada servicio se actualice y crezca de forma autónoma.
- Facilita la auditoría y trazabilidad de eventos, ya que cada evento queda registrado en el broker.
- Permite la integración de nuevos servicios sin modificar la lógica existente, ya que se suscriben a los eventos relevantes.
- Reduce la latencia de comunicación síncrona al delegar la interacción entre servicios en un bus asíncrono.

Negativas:

- Incrementa la complejidad operativa al gestionar un broker adicional que requiere despliegue, configuración y mantenimiento.
- Introduce latencia adicional en la entrega de eventos, ya que el mensaje debe pasar por RabbitMQ antes de ser procesado.
- Requiere manejo de errores y reintentos en la capa de consumidor para garantizar la entrega eventual de los eventos.
- Necesita monitoreo y métricas específicas para RabbitMQ, lo que añade carga al equipo de operaciones.

## Trazabilidad

Servicios afectados: `pedidos`, `pagos`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RF-15 | La pasarela avisa a la tienda del resultado de cada pago, y la tienda solo acepta los avisos que demuestren venir de la pasarela; con un aviso válido de pago aprobado, el pedido pasa a «pagado». |
| RF-17 | El cliente recibe un correo cuando su pedido se acepta, cuando se paga y cada vez que cambia de estado. |
| RF-16 | Un pedido que no se paga en 30 minutos se cancela solo y sus unidades vuelven al stock disponible. |
| RNF-09 | El catálogo, los pedidos y los pagos deben poder actualizarse y crecer por separado, cada uno con sus propios datos, sin que la caída de uno detenga a los demás. |
