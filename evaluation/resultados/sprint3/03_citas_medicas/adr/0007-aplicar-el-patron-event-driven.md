<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0007: Aplicar el patrón Event-Driven

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema necesita desacoplar los microservicios para mejorar la escalabilidad y la resiliencia. Se decide adoptar un modelo Event-Driven con RabbitMQ, permitiendo que los servicios se comuniquen mediante eventos asíncronos en lugar de llamadas directas. &lt;requisito-CODIGO ASVS-V5.1.3&gt;Toda entrada (formularios, peticiones REST, parámetros, cabeceras, archivos) se valida con listas de valores permitidos&lt;/requisito-CODIGO&gt; &lt;requisito-CODIGO CWE-20&gt;Improper Input Validation&lt;/requisito-CODIGO&gt; &lt;requisito-CODIGO CWE-345&gt;Insufficient Verification of Data Authenticity&lt;/requisito-CODIGO&gt;

## Decisión

Se aplica Event-Driven: los servicios se comunican con eventos asíncronos en lugar de llamadas directas. Implementación prevista: rabbitmq.

## Justificación

Dependencias por eventos: administracion -&gt; historia\_clinica, citas -&gt; pagos

## Consecuencias

Positivas:

- Mayor desacoplamiento entre servicios, facilitando su evolución independiente.
- Escalabilidad horizontal mejorada, ya que los servicios pueden crecer sin depender de llamadas síncronas.
- Mayor tolerancia a fallos, pues la pérdida de un servicio no bloquea el flujo de datos.
- Facilidad para integrar nuevos servicios que consumen o publican eventos.

Negativas:

- Complejidad añadida en el monitoreo y trazabilidad de eventos asíncronos.
- Necesidad de implementar idempotencia y manejo de duplicados para evitar inconsistencias.
- Sobrecarga operativa de RabbitMQ, requiriendo mantenimiento y ajustes de rendimiento.
- Latencia introducida por la capa de mensajería, afectando la experiencia de usuario en flujos críticos.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V5.1.3 | Toda entrada (formularios, peticiones REST, parámetros, cabeceras, archivos) se valida con listas de valores permitidos |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-20 | Improper Input Validation |
| CWE-345 | Insufficient Verification of Data Authenticity |

## Trazabilidad

Servicios afectados: `administracion`, `historia_clinica`, `citas`, `pagos`

No la motiva un requisito concreto: OPA la deduce de la estructura.
