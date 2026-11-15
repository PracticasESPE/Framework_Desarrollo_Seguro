<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0010: Aplicar el patrón Saga

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Patrón arq.transaccion.001 inferido por OPA (rasgos: transaccion\_entre\_servicios) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El patrón Saga se aplica para coordinar operaciones distribuidas entre microservicios, garantizando la consistencia de los pedidos sin depender de transacciones ACID globales.

## Decisión

Se aplica Saga: transacción distribuida como secuencia de pasos locales con compensación. Implementación prevista: rabbitmq.

## Justificación

pedidos coordina operaciones que involucran a otros servicios

## Consecuencias

Positivas:

- Permite que cada servicio mantenga su propia base de datos, reduciendo el acoplamiento y mejorando la escalabilidad.
- Facilita la recuperación ante fallos mediante pasos de compensación, evitando estados inconsistentes.
- Mejora la visibilidad de los flujos de negocio al registrar cada paso en RabbitMQ, lo que facilita el monitoreo y auditoría.

Negativas:

- Incrementa la complejidad de la lógica de negocio, requiriendo la implementación de manejadores de compensación y orquestadores.
- Puede introducir latencia adicional al esperar la confirmación de cada paso antes de avanzar al siguiente.
- Requiere un manejo cuidadoso de la idempotencia y la tolerancia a fallos, lo que aumenta el esfuerzo de desarrollo y pruebas.

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

Servicios afectados: `pedidos`

No la motiva un requisito concreto: OPA la deduce de la estructura.
