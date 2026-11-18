<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0002: Comunicación entre microservicios

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Decisión D-02 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema necesita garantizar que el precio de cada producto se calcule con los valores actuales del catálogo al confirmar un pedido (RF-10), mientras que los cambios de estado de los pedidos (RF-12, RF-14) y las notificaciones al cliente (RF-16) deben manejarse de forma desacoplada para permitir la escalabilidad y la resiliencia de los microservicios.

## Decisión

Usar HTTP síncrono para lecturas críticas (precio del catálogo) y RabbitMQ eventos asíncronos para cambios de estado (pedido creado, pago result, notificaciones).

## Justificación

Requisitos de consistencia al crear pedidos requieren precios actuales (RF-10) → sincrono. Otros requisitos como notificaciones (RF-16) y actualización de stock (RF-12) se benefician de desacoplamiento y evitan ciclos.

## Consecuencias

Positivas:

- Se asegura la consistencia de los precios al momento de la compra mediante llamadas HTTP síncronas, cumpliendo RF-10 y evitando fraudes de precios.
- Se mejora la resiliencia del sistema al usar eventos RabbitMQ para actualizaciones de stock y notificaciones, permitiendo que cada servicio crezca de forma independiente (RNF-09).
- Se reduce la latencia de las operaciones críticas de lectura, ya que las lecturas de precio se realizan en tiempo real sin esperar colas asíncronas.
- Se facilita la trazabilidad y auditoría de los cambios de estado de los pedidos a través de eventos publicados en RabbitMQ, lo que simplifica la depuración y el monitoreo.

Negativas:

- La introducción de dos patrones de comunicación aumenta la complejidad arquitectónica, requiriendo más código de manejo de errores y pruebas específicas.
- El uso de RabbitMQ implica un riesgo de pérdida de mensajes o desorden en la entrega, lo que puede afectar la consistencia de stock (RF-12) y el estado de los pedidos (RF-14).
- Se incrementa la carga operativa y el mantenimiento de un broker de mensajes adicional, lo que puede generar costos de operación y requerir monitoreo especializado.
- Las llamadas HTTP síncronas pueden introducir latencia en la experiencia del usuario, especialmente si el servicio de catálogo presenta tiempos de respuesta variables, lo que podría afectar la satisfacción del cliente.

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
