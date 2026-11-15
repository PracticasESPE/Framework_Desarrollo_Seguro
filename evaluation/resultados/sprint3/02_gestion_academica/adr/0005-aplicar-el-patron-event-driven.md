<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0005: Aplicar el patrón Event-Driven

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) |
| Documento de requisitos | requisitos.docx (SHA-256 `16229f92f991`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema necesita desacoplar los microservicios para mejorar la escalabilidad y la resiliencia ante fallos. Al adoptar un modelo Event-Driven, los servicios se comunican mediante eventos asíncronos en lugar de llamadas directas, lo que permite una mayor flexibilidad y la posibilidad de añadir nuevos consumidores sin modificar los productores. Esta decisión se basa en la arquitectura actual, donde los servicios notificaciones, certificados, matriculas y notas dependen de eventos para coordinarse. &lt;requisito-CODIGO ASVS-V5.1.3&gt;Toda entrada (formularios, peticiones REST, parámetros, cabeceras, archivos) se valida con listas de valores permitidos&lt;/requisito-CODIGO&gt; &lt;requisito-CODIGO CWE-20&gt;Improper Input Validation&lt;/requisito-CODIGO&gt; &lt;requisito-CODIGO CWE-345&gt;Insufficient Verification of Data Authenticity&lt;/requisito-CODIGO&gt;

## Decisión

Se aplica Event-Driven: los servicios se comunican con eventos asíncronos en lugar de llamadas directas. Implementación prevista: rabbitmq.

## Justificación

Dependencias por eventos: notificaciones -&gt; certificados, notificaciones -&gt; matriculas, notificaciones -&gt; notas

## Consecuencias

Positivas:

- Mejora la escalabilidad y la resiliencia, ya que los servicios pueden procesar eventos de forma independiente y en paralelo.
- Facilita la incorporación de nuevos servicios o funcionalidades sin afectar a los existentes, gracias al desacoplamiento.
- Reduce la latencia de las operaciones críticas al permitir que los servicios reaccionen a eventos en tiempo real.
- Permite un mejor monitoreo y trazabilidad de los flujos de negocio a través de los eventos publicados en RabbitMQ.

Negativas:

- Incrementa la complejidad operativa, ya que se debe gestionar y monitorear RabbitMQ y garantizar la entrega de mensajes.
- Aumenta el tiempo de desarrollo inicial, pues se requiere diseñar y mantener los esquemas de eventos y los consumidores.
- Introduce latencia adicional en la comunicación, ya que los eventos deben ser publicados y consumidos antes de que el flujo continúe.
- Requiere un mayor esfuerzo de pruebas, especialmente para garantizar la idempotencia y la consistencia eventual de los datos.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V5.1.3 | Toda entrada (formularios, peticiones REST, parámetros, cabeceras, archivos) se valida con listas de valores permitidos |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-20 | Improper Input Validation |
| CWE-345 | Insufficient Verification of Data Authenticity |

## Trazabilidad

Servicios afectados: `notificaciones`, `certificados`, `matriculas`, `notas`

No la motiva un requisito concreto: OPA la deduce de la estructura.
