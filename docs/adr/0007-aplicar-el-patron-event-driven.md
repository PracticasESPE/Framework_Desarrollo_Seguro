<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0007: Aplicar el patrón Event-Driven

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-10 |
| Origen | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere desacoplar los microservicios para mejorar la escalabilidad y la resiliencia. Se decide adoptar un modelo Event‑Driven, donde los servicios se comunican mediante eventos asíncronos a través de RabbitMQ. Esta arquitectura permite que los servicios de avisos, pagos, pedidos, inventario, reportes y usuarios se integren sin dependencias directas, reduciendo el acoplamiento y facilitando la evolución independiente de cada componente. &lt;requisito-CODIGO ASVS-V5.1.3&gt;Toda entrada (formularios, peticiones REST, parámetros, cabeceras, archivos) se valida con listas de valores permitidos&lt;/requisito-CODIGO&gt;

## Decisión

Se aplica Event-Driven: los servicios se comunican con eventos asíncronos en lugar de llamadas directas. Implementación prevista: rabbitmq.

## Justificación

Dependencias por eventos: avisos -&gt; pagos, avisos -&gt; pedidos, inventario -&gt; pedidos, pagos -&gt; pedidos, reportes -&gt; pedidos, reportes -&gt; usuarios

## Consecuencias

Positivas:

- Mejora la escalabilidad y la resiliencia al permitir que los servicios se escalen de forma independiente y se recuperen de fallos sin afectar a todo el sistema.
- Reduce el acoplamiento entre microservicios, facilitando la evolución y el mantenimiento de cada componente sin impactar a los demás.
- Facilita la incorporación de nuevos servicios y la integración con sistemas externos mediante la publicación y suscripción a eventos.
- Mitiga los riesgos de &lt;requisito-CODIGO CWE-20&gt;Improper Input Validation&lt;/requisito-CODIGO&gt; y &lt;requisito-CODIGO CWE-345&gt;Insufficient Verification of Data Authenticity&lt;/requisito-CODIGO&gt; al validar las entradas con listas de valores permitidos y asegurar la autenticidad de los datos.

Negativas:

- Incrementa la complejidad operativa al requerir la gestión y monitoreo de RabbitMQ, lo que implica costos de mantenimiento y posibles cuellos de botella en la cola.
- Aumenta la latencia de los flujos de negocio, ya que las operaciones se realizan de forma asíncrona y dependen de la entrega de eventos.
- Requiere un mecanismo de compensación y manejo de errores más sofisticado para garantizar la consistencia eventual entre servicios.
- Puede generar sobrecarga de mensajes y duplicados si no se implementa un esquema de deduplicación, lo que afecta el rendimiento.

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
