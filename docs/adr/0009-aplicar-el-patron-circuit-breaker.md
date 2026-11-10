<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0009: Aplicar el patrón Circuit Breaker

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-10 |
| Origen | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema realiza llamadas síncronas entre microservicios, lo que puede provocar fallos en cascada cuando un servicio falla. Para mitigar este riesgo se decide aplicar el patrón Circuit Breaker, interrumpiendo las llamadas a servicios que presentan fallos repetidos. Esta medida garantiza la disponibilidad y la estabilidad del ecosistema de servicios. &lt;requisito-CODIGO ASVS-V11.1.4&gt;Hay controles contra la automatización que protegen de llamadas excesivas, robo masivo de datos y denegación de servicio&lt;/requisito-CODIGO&gt; &lt;requisito-CODIGO CWE-400&gt;Uncontrolled Resource Consumption&lt;/requisito-CODIGO&gt; &lt;requisito-CODIGO CWE-770&gt;Allocation of Resources Without Limits or Throttling&lt;/requisito-CODIGO&gt;

## Decisión

Se aplica Circuit Breaker: corta las llamadas a un servicio que falla para evitar fallos en cascada. Implementación prevista: nestjs\_interceptor\_con\_reintentos\_y\_timeout.

## Justificación

Llamadas síncronas entre servicios: pagos -&gt; usuarios, pedidos -&gt; catalogo

## Consecuencias

Positivas:

- Reduce la propagación de fallos, evitando que un servicio caído afecte a los demás y manteniendo la disponibilidad del sistema.
- Mejora la experiencia del usuario al evitar tiempos de espera prolongados y errores inesperados en la interfaz.
- Facilita la observabilidad y el monitoreo, ya que los estados de los circuit breakers se pueden exponer y alertar.

Negativas:

- Aumenta la complejidad del código y la configuración, requiriendo interceptores y lógica adicional en cada microservicio.
- Puede introducir latencia adicional al evaluar el estado del circuito antes de cada llamada.
- Requiere un mecanismo de persistencia o sincronización del estado del circuito para evitar inconsistencias en entornos distribuidos.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V11.1.4 | Hay controles contra la automatización que protegen de llamadas excesivas, robo masivo de datos y denegación de servicio |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-400 | Uncontrolled Resource Consumption |
| CWE-770 | Allocation of Resources Without Limits or Throttling |

## Trazabilidad

Servicios afectados: `pagos`, `usuarios`, `pedidos`, `catalogo`

No la motiva un requisito concreto: OPA la deduce de la estructura.
