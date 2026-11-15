<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0007: Aplicar el patrón Event-Driven

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere desacoplar los microservicios para mejorar la escalabilidad y la resiliencia ante fallos. Se decide adoptar un modelo event-driven, donde los servicios se comunican mediante eventos asíncronos en lugar de llamadas directas. Esta arquitectura facilita la incorporación de nuevos servicios y la gestión de dependencias entre avisos, pagos, pedidos, inventario, reportes y usuarios.

## Decisión

Se aplica Event-Driven: los servicios se comunican con eventos asíncronos en lugar de llamadas directas. Implementación prevista: rabbitmq.

## Justificación

Dependencias por eventos: avisos -&gt; pagos, avisos -&gt; pedidos, inventario -&gt; pedidos, pagos -&gt; pedidos, reportes -&gt; pedidos, reportes -&gt; usuarios

## Consecuencias

Positivas:

- Mayor desacoplamiento entre servicios, lo que permite actualizaciones independientes y despliegues sin afectar a los demás.
- Escalabilidad horizontal más sencilla, ya que cada servicio puede escalar según la carga de sus eventos.
- Resiliencia aumentada, pues la pérdida de un servicio no interrumpe la comunicación; los eventos se almacenan en RabbitMQ y se procesan cuando el receptor esté disponible.
- Facilidad de incorporación de nuevos servicios, ya que solo deben suscribirse a los eventos relevantes sin modificar la lógica de los emisores.

Negativas:

- Incremento de complejidad operativa: se requiere monitoreo y gestión de RabbitMQ, colas y posibles cuellos de botella.
- Dificultad en el trazado de transacciones, ya que la comunicación asíncrona dificulta seguir el flujo de una operación completa.
- Consumo de recursos adicionales: cada servicio necesita un cliente RabbitMQ y la infraestructura debe soportar la latencia y el almacenamiento de mensajes.
- Riesgo de inconsistencias eventual: los datos pueden quedar en estados intermedios mientras los eventos se procesan, lo que exige lógica de compensación.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V5.1.3 | Toda entrada (formularios, peticiones REST, parámetros, cabeceras, archivos) se valida con listas de valores permitidos |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-20 | Improper Input Validation |
| CWE-345 | Insufficient Verification of Data Authenticity |

## Trazabilidad

Servicios afectados: `avisos`, `pagos`, `pedidos`, `inventario`, `reportes`, `usuarios`

No la motiva un requisito concreto: OPA la deduce de la estructura.
