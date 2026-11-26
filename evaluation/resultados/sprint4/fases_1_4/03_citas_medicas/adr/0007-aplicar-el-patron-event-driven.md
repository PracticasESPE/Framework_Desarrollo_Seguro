<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0007: Aplicar el patrón Event-Driven

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-25 |
| Origen | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Para desacoplar los microservicios y permitir que cada uno escale de forma independiente, se decide adoptar un modelo de comunicación basado en eventos asíncronos. Este enfoque facilita la resiliencia y la tolerancia a fallos, ya que los servicios no dependen de la disponibilidad inmediata de los demás. Además, permite integrar nuevos componentes sin modificar las interfaces existentes.

## Decisión

Se aplica Event-Driven: los servicios se comunican con eventos asíncronos en lugar de llamadas directas. Implementación prevista: rabbitmq.

## Justificación

Dependencias por eventos: citas -&gt; gestion, citas -&gt; pagos, gestion -&gt; citas, gestion -&gt; historia, gestion -&gt; laboratorio, historia -&gt; gestion, historia -&gt; laboratorio, laboratorio -&gt; gestion, pagos -&gt; citas, pagos -&gt; gestion

## Consecuencias

Positivas:

- Mayor desacoplamiento entre servicios, lo que simplifica la evolución y despliegue independiente de cada microservicio.
- Escalabilidad horizontal mejorada, ya que los consumidores pueden escalar según la carga de eventos sin afectar a los productores.
- Resiliencia aumentada: fallos en un servicio no bloquean la comunicación, los mensajes se almacenan en RabbitMQ hasta que el receptor esté disponible.
- Facilidad de integración de nuevos servicios: basta publicar eventos y suscribirse, sin cambiar contratos REST.

Negativas:

- Complejidad operativa adicional: se requiere monitoreo y gestión de colas, persistencia y reintentos en RabbitMQ.
- Latencia mayor en la propagación de datos, ya que la comunicación es asíncrona y puede haber retrasos.
- Necesidad de garantizar idempotencia y manejo de duplicados, lo que implica lógica extra en los consumidores.
- Riesgo de pérdida de mensajes en caso de fallos no detectados, requiriendo mecanismos de persistencia y recuperación.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V5.1.3 | Toda entrada (formularios, peticiones REST, parámetros, cabeceras, archivos) se valida con listas de valores permitidos |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-20 | Improper Input Validation |
| CWE-345 | Insufficient Verification of Data Authenticity |

## Trazabilidad

Servicios afectados: `citas`, `gestion`, `pagos`, `historia`, `laboratorio`

No la motiva un requisito concreto: OPA la deduce de la estructura.
