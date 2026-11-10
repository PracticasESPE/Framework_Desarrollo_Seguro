<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0010: Aplicar el patrón Saga

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-10 |
| Origen | Patrón arq.transaccion.001 inferido por OPA (rasgos: transaccion\_entre\_servicios) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere coordinar pagos con otros microservicios sin bloquear transacciones globales. El patrón Saga permite dividir la operación en pasos locales con compensación, manteniendo consistencia. Se implementará sobre RabbitMQ para orquestar los eventos. Esta decisión responde a la necesidad de evitar bloqueos y garantizar la integridad de los datos.

## Decisión

Se aplica Saga: transacción distribuida como secuencia de pasos locales con compensación. Implementación prevista: rabbitmq.

## Justificación

pagos coordina operaciones que involucran a otros servicios

## Consecuencias

Positivas:

- Garantiza consistencia eventual sin bloqueos de base de datos, reduciendo riesgo de deadlocks.
- Permite que cada microservicio gestione su propia lógica de compensación, facilitando la recuperación ante fallos.
- Mejora la escalabilidad al permitir que los servicios se ejecuten de forma asíncrona y paralela.
- Facilita la trazabilidad de transacciones distribuidas mediante eventos RabbitMQ.

Negativas:

- Incrementa la complejidad arquitectónica y de desarrollo al manejar compensaciones y orquestación.
- Aumenta la latencia total de la operación debido a la comunicación asíncrona entre servicios.
- Requiere mecanismos de idempotencia y manejo de errores más robustos para evitar inconsistencias.
- Necesita monitoreo y alertas adicionales para detectar y resolver fallos de compensación.

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

Servicios afectados: `pagos`

No la motiva un requisito concreto: OPA la deduce de la estructura.
