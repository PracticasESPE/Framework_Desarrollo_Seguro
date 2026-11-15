<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0002: Patrón de comunicación

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Decisión D-02 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Para garantizar que los clientes obtengan precios y validaciones de pago en tiempo real, se opta por comunicación síncrona HTTP entre los microservicios de pedidos‑usuarios y pedidos‑catalogo. Al mismo tiempo, la confirmación de pagos se maneja de forma asíncrona mediante RabbitMQ entre pedidos y pagos, lo que permite desacoplar y hacer más resiliente el proceso de cobro.

## Decisión

Comunicación síncrona HTTP entre pedidos‑usuarios y pedidos‑catalogo; eventos asíncronos vía RabbitMQ entre pedidos y pagos.

## Justificación

La validación de cliente y precios necesita respuesta inmediata (RF-02, RF-11). La notificación de pago es mejor manejarla de forma desacoplada y resiliente (RF-15, RF-16).

## Consecuencias

Positivas:

- Respuesta inmediata al cliente al validar precios y disponibilidad de stock a través de HTTP.
- Mayor resiliencia en el procesamiento de pagos, ya que los eventos de pago se manejan de forma desacoplada y pueden ser reintentados sin bloquear la solicitud del cliente.
- Facilidad de escalado de los servicios de pagos sin afectar la latencia de la validación de pedidos.

Negativas:

- Aumento de la latencia en la solicitud de pedido debido a la dependencia de la respuesta HTTP del catálogo.
- Necesidad de implementar mecanismos de circuit breaker y timeout para evitar cuellos de botella en la comunicación síncrona.
- Complejidad adicional en la gestión de eventos RabbitMQ, incluyendo la garantía de entrega y la idempotencia de los mensajes.

## Trazabilidad

Servicios afectados: `pedidos`, `pagos`

| Requisito | Texto del documento |
|---|---|
| RF-01 | La empresa quiere que sus clientes compren a cualquier hora, que el stock se actualice solo y que el cobro con tarjeta sea inmediato. Trabajan en ella cuatro personas: dos atienden los pedidos y dos gestionan el catálogo. Ninguna tiene conocimientos técnicos. |
| RF-11 | Al confirmar el pedido, el precio de cada producto y el total se calculan con los precios del catálogo, sin aceptar los importes que envíe el navegador. |
| RF-15 | La pasarela avisa a la tienda del resultado de cada pago, y la tienda solo acepta los avisos que demuestren venir de la pasarela; con un aviso válido de pago aprobado, el pedido pasa a «pagado». |
| RF-16 | Un pedido que no se paga en 30 minutos se cancela solo y sus unidades vuelven al stock disponible. |
| RF-20 | Como cliente, quiero cancelar un pedido mientras todavía no se haya enviado, para no pagar algo que ya no necesito. |
