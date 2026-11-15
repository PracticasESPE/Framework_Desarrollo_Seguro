<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0010: Aplicar el patrón Saga

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Patrón arq.transaccion.001 inferido por OPA (rasgos: transaccion\_entre\_servicios) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema requiere coordinar transacciones que abarcan varios microservicios, especialmente en el flujo de pagos. El patrón Saga permite dividir la operación en pasos locales con compensaciones, evitando bloqueos de bases de datos distribuidas. Esta solución mantiene la consistencia sin sacrificar la escalabilidad de la arquitectura.

## Decisión

Se aplica Saga: transacción distribuida como secuencia de pasos locales con compensación. Implementación prevista: rabbitmq.

## Justificación

pagos coordina operaciones que involucran a otros servicios

## Consecuencias

Positivas:

- Garantiza la consistencia eventual de los datos entre los servicios involucrados, evitando estados inconsistentes.
- Permite que cada microservicio mantenga su autonomía y escale de forma independiente, ya que la coordinación se realiza a través de eventos.
- Facilita la recuperación ante fallos mediante pasos de compensación, reduciendo la necesidad de rollbacks complejos.
- Reduce la dependencia de transacciones distribuidas de base de datos, lo que simplifica la infraestructura y mejora el rendimiento.

Negativas:

- Incrementa la complejidad del diseño y la implementación, requiriendo lógica adicional para manejar compensaciones y estados.
- Aumenta la latencia total del flujo de negocio, ya que cada paso debe esperar la confirmación del siguiente.
- Requiere que los servicios sean idempotentes y manejen correctamente los mensajes duplicados, lo que añade esfuerzo de desarrollo.
- Existe riesgo de inconsistencias temporales si una compensación falla, lo que puede requerir monitoreo y reintentos manuales.

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
