<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0010: Aplicar el patrón Saga

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-25 |
| Origen | Patrón arq.transaccion.001 inferido por OPA (rasgos: transaccion\_entre\_servicios) |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema necesita garantizar la consistencia entre múltiples microservicios que realizan operaciones críticas, como citas, gestión, historia, laboratorio y pagos. Para evitar inconsistencias y condiciones de carrera, se decide implementar el patrón Saga con RabbitMQ como bus de eventos. Esta solución permite que cada servicio ejecute pasos locales y compense en caso de fallo, manteniendo la integridad de los flujos de negocio.

## Decisión

Se aplica Saga: transacción distribuida como secuencia de pasos locales con compensación. Implementación prevista: rabbitmq.

## Justificación

citas, gestion, historia, laboratorio, pagos coordina operaciones que involucran a otros servicios

## Consecuencias

Positivas:

- Mejora la consistencia de datos entre servicios sin necesidad de transacciones distribuidas pesadas, reduciendo la posibilidad de estados inconsistentes.
- Facilita la recuperación ante fallos mediante pasos de compensación, lo que aumenta la resiliencia del sistema.
- Permite que cada microservicio siga su propia lógica de negocio, manteniendo la independencia y la escalabilidad.
- Cumple con los controles ASVS-V11.1.1 y V11.1.6 al garantizar que los flujos de negocio se procesan secuencialmente y sin condiciones de carrera.

Negativas:

- Incrementa la complejidad arquitectónica y de desarrollo al requerir la implementación de lógica de compensación y manejo de eventos.
- Aumenta la latencia de las transacciones, ya que cada paso depende de la recepción y procesamiento de mensajes RabbitMQ.
- Requiere un monitoreo y trazabilidad exhaustivos para detectar y resolver fallos en la cadena de eventos, lo que eleva la carga operativa.
- Existe riesgo de duplicación de mensajes o pérdida de idempotencia si no se gestionan correctamente los identificadores de saga.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V11.1.1 | Los flujos de negocio de un usuario se procesan solo en orden secuencial y sin saltarse pasos |
| ASVS-V11.1.6 | La aplicación no sufre condiciones de carrera entre la comprobación y el uso (TOCTOU) en operaciones sensibles |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-362 | Concurrent Execution using Shared Resource with Improper Synchronization ('Race Condition') |
| CWE-841 | Improper Enforcement of Behavioral Workflow |

## Trazabilidad

Servicios afectados: `citas`, `gestion`, `historia`, `laboratorio`, `pagos`

No la motiva un requisito concreto: OPA la deduce de la estructura.
