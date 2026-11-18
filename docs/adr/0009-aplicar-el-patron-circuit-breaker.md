<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0009: Aplicar el patrón Circuit Breaker

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) |
| Documento de requisitos | requisitos.docx (SHA-256 `0515668b00b8`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema microservicio utiliza llamadas síncronas entre servicios (pagos→usuarios, pedidos→catalogo). Cuando un servicio falla, las peticiones se propagan y pueden saturar la arquitectura, provocando caídas en cascada. Para mitigar este riesgo se decide aplicar el patrón Circuit Breaker, interrumpiendo las llamadas a servicios que presentan fallos repetidos y evitando la sobrecarga de recursos.

## Decisión

Se aplica Circuit Breaker: corta las llamadas a un servicio que falla para evitar fallos en cascada. Implementación prevista: nestjs\_interceptor\_con\_reintentos\_y\_timeout.

## Justificación

Llamadas síncronas entre servicios: pagos -&gt; usuarios, pedidos -&gt; catalogo

## Consecuencias

Positivas:

- Reduce la propagación de fallos y mejora la resiliencia del sistema.
- Evita la sobrecarga de recursos y mejora la disponibilidad de los servicios.
- Facilita la detección temprana de servicios defectuosos y permite la recuperación automática.
- Cumple con los controles ASVS-V11.1.4 y mitiga CWE-400 y CWE-770.

Negativas:

- Incrementa la complejidad de la implementación y el mantenimiento de los interceptores.
- Puede introducir latencia adicional en las llamadas exitosas debido a la lógica de circuit breaker.
- Requiere configuración y monitorización de umbrales de fallo y tiempo de espera.
- Si mal configurado, puede bloquear servicios válidos y generar falsos positivos.

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
