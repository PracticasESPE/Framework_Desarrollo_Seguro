<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0008: Aplicar el patrón Saga

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Patrón arq.transaccion.001 inferido por OPA (rasgos: transaccion\_entre\_servicios) |
| Documento de requisitos | requisitos.docx (SHA-256 `16229f92f991`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

Los microservicios de asistencia, certificados, matriculas y notas necesitan coordinar operaciones distribuidas que involucran múltiples bases de datos PostgreSQL independientes sin bloquear los recursos globales. Para garantizar la consistencia eventual y mitigar problemas como ASVS-V11.1.6 y CWE-362, se requiere un mecanismo de transacciones distribuidas confiable. La decisión validada implementa el patrón Saga mediante mensajes asíncronos en RabbitMQ, asegurando que los flujos de negocio complejos cumplan con ASVS-V11.1.1 y prevengan fallos de flujo según CWE-841.

## Decisión

Se aplica Saga: transacción distribuida como secuencia de pasos locales con compensación. Implementación prevista: rabbitmq.

## Justificación

asistencia, certificados, matriculas, notas coordina operaciones que involucran a otros servicios

## Consecuencias

Positivas:

- Permite mantener la consistencia eventual entre las bases de datos PostgreSQL independientes de los microservicios sin acoplar sus transacciones locales.
- Mitiga condiciones de carrera (CWE-362) y asegura el orden estricto de los flujos de negocio complejos requeridos por ASVS-V11.1.1.
- Aprovecha la infraestructura existente de RabbitMQ para la comunicación basada en eventos sin introducir dependencias de pago o licencias comerciales.

Negativas:

- Incrementa la complejidad operacional al tener que diseñar, desplegar y monitorizar las acciones de compensación para cada paso fallido en la infraestructura autoalojada.
- Introduce latencia en las operaciones de negocio debido a la naturaleza asíncrona de las transacciones distribuidas a través de RabbitMQ.
- Requiere un esfuerzo adicional de depuración y trazabilidad entre los contenedores NestJS para rastrear el estado de las Sagas en vuelo.

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

Servicios afectados: `asistencia`, `certificados`, `matriculas`, `notas`

No la motiva un requisito concreto: OPA la deduce de la estructura.
