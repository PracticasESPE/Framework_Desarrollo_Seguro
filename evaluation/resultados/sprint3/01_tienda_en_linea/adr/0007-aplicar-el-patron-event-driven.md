<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0007: Aplicar el patrón Event-Driven

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere desacoplar los microservicios de pagos y pedidos para mejorar la escalabilidad y la resiliencia ante fallos. La comunicación síncrona genera cuellos de botella y dificulta la incorporación de nuevos servicios. Adoptar un modelo event-driven con RabbitMQ permite que los servicios reaccionen a eventos de forma asíncrona y desacoplada. El sistema debe cumplir con &lt;requisito-CODIGO ASVS-V5.1.3&gt;Toda entrada (formularios, peticiones REST, parámetros, cabeceras, archivos) se valida con listas de valores permitidos&lt;/requisito-CODIGO&gt; y mitigar &lt;requisito-CODIGO CWE-20&gt;Improper Input Validation&lt;/requisito-CODIGO&gt; y &lt;requisito-CODIGO CWE-345&gt;Insufficient Verification of Data Authenticity&lt;/requisito-CODIGO&gt;.

## Decisión

Se aplica Event-Driven: los servicios se comunican con eventos asíncronos en lugar de llamadas directas. Implementación prevista: rabbitmq.

## Justificación

Dependencias por eventos: pagos -&gt; pedidos, pedidos -&gt; pagos

## Consecuencias

Positivas:

- Mejora la escalabilidad al permitir que cada servicio procese eventos de manera independiente, ajustando su consumo según la carga.
- Aumenta la resiliencia, ya que la falla de un servicio no bloquea la cadena de procesamiento; los eventos se almacenan y se reintentan.
- Facilita la incorporación de nuevos servicios que consumen los mismos eventos sin modificar los productores.
- Reduce la latencia de respuesta al cliente, ya que la lógica de negocio se ejecuta de forma asíncrona y no bloquea la petición inicial.

Negativas:

- Incrementa la complejidad operativa, requiriendo monitoreo y gestión de colas, y la garantía de entrega de mensajes.
- Introduce la necesidad de manejar la consistencia eventual, lo que puede requerir lógica adicional para reconciliar estados.
- Aumenta el riesgo de pérdida de mensajes si RabbitMQ no está configurado con persistencia y replicación adecuadas.
- Requiere que los servicios sean idempotentes y manejen duplicados, lo que complica el diseño de la lógica de negocio.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V5.1.3 | Toda entrada (formularios, peticiones REST, parámetros, cabeceras, archivos) se valida con listas de valores permitidos |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-20 | Improper Input Validation |
| CWE-345 | Insufficient Verification of Data Authenticity |

## Trazabilidad

Servicios afectados: `pagos`, `pedidos`

No la motiva un requisito concreto: OPA la deduce de la estructura.
