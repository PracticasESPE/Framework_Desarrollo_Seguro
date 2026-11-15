<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0009: Aplicar el patrón Circuit Breaker

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema realiza llamadas síncronas entre microservicios, lo que puede provocar fallos en cascada cuando un servicio deja de responder. Para mitigar este riesgo se decide aplicar el patrón Circuit Breaker, interrumpiendo las llamadas a un servicio que falla repetidamente. Esta medida garantiza la disponibilidad de los demás servicios y mejora la experiencia del usuario. Se alinea con el control ASVS-V11.1.4 y mitiga los riesgos CWE-400 y CWE-770.

## Decisión

Se aplica Circuit Breaker: corta las llamadas a un servicio que falla para evitar fallos en cascada. Implementación prevista: nestjs\_interceptor\_con\_reintentos\_y\_timeout.

## Justificación

Llamadas síncronas entre servicios: pedidos -&gt; catalogo, pedidos -&gt; usuarios, ventas -&gt; pedidos

## Consecuencias

Positivas:

- Reduce la propagación de fallos, manteniendo la disponibilidad de los microservicios afectados.
- Mejora la experiencia del usuario al evitar tiempos de espera prolongados cuando un servicio está caído.
- Facilita la detección temprana de problemas de un servicio, permitiendo alertas y acciones correctivas más rápidas.

Negativas:

- Aumenta la complejidad del código al introducir interceptores y lógica de reintentos.
- Puede introducir latencia adicional en las llamadas exitosas debido al manejo de timeouts y reintentos.
- Requiere monitoreo y ajuste de umbrales para evitar falsos positivos que bloqueen servicios válidos.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V11.1.4 | Hay controles contra la automatización que protegen de llamadas excesivas, robo masivo de datos y denegación de servicio |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-400 | Uncontrolled Resource Consumption |
| CWE-770 | Allocation of Resources Without Limits or Throttling |

## Trazabilidad

Servicios afectados: `pedidos`, `catalogo`, `usuarios`, `ventas`

No la motiva un requisito concreto: OPA la deduce de la estructura.
