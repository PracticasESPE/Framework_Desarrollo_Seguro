<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0002: Comunicación entre microservicios

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-10 |
| Origen | Decisión D-02 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Para garantizar que el precio calculado al confirmar un pedido sea siempre el actual del catálogo, se requiere una llamada síncrona. Al mismo tiempo, los cambios de estado y las notificaciones deben ser desacoplados para evitar dependencias y ciclos. Por ello, se decide usar HTTP síncrono para lecturas críticas y RabbitMQ para eventos asíncronos.

## Decisión

Usar HTTP síncrono para lecturas críticas (precio del catálogo) y RabbitMQ eventos asíncronos para cambios de estado (pedido creado, pago result, notificaciones).

## Justificación

Requisitos de consistencia al crear pedidos requieren precios actuales (RF-10) → sincrono. Otros requisitos como notificaciones (RF-16) y actualización de stock (RF-12) se benefician de desacoplamiento y evitan ciclos.

## Consecuencias

Positivas:

- Garantiza la consistencia de precios al confirmar pedidos, cumpliendo RF-10.
- Desacopla los servicios de notificación y actualización de stock, mejorando la resiliencia y permitiendo que cada microservicio crezca de forma independiente (RNF-09).
- Reduce la latencia de los flujos críticos al evitar la sobrecarga de eventos para lecturas de precio.
- Facilita la trazabilidad de eventos de estado a través de RabbitMQ, mejorando la observabilidad.

Negativas:

- Introduce latencia adicional en la confirmación de pedidos debido a la llamada HTTP síncrona, lo que puede afectar la experiencia del usuario.
- Requiere manejo de timeouts y circuit breakers para evitar bloqueos cuando el catálogo no responde, aumentando la complejidad del código.
- La dependencia de RabbitMQ añade un punto de fallo y requiere monitoreo y mantenimiento de la cola.
- El uso de dos patrones de comunicación complica la arquitectura y la documentación de los flujos de datos.

## Trazabilidad

Servicios afectados: `inventario`, `pedidos`, `pagos`, `avisos`, todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RF-10 | Al confirmar el pedido, el precio de cada producto y el total se calculan con los precios del catálogo, sin aceptar los importes que envíe el navegador. |
| RF-12 | Al aceptarse un pedido, sus unidades se descuentan del stock disponible. |
| RF-14 | La pasarela avisa a la tienda del resultado de cada pago, y la tienda solo acepta los avisos que demuestren venir de la pasarela; con un aviso válido de pago aprobado, el pedido pasa a «pagado». |
| RF-16 | El cliente recibe un correo cuando su pedido se acepta, cuando se paga y cada vez que cambia de estado. |
| RNF-09 | El catálogo, los pedidos y los pagos deben poder actualizarse y crecer por separado, cada uno con sus propios datos, sin que la caída de uno detenga a los demás. |
| RNF-06 | Un mismo cliente o una misma dirección IP no puede hacer más de 100 peticiones por minuto; si las supera, la tienda le pide que espere. |
