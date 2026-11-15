<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0009: Aplicar el patrón Circuit Breaker

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema microservicio expone llamadas síncronas entre servicios críticos, lo que puede provocar fallos en cascada cuando uno de ellos falla. Para mitigar este riesgo se decide aplicar el patrón Circuit Breaker, implementado mediante un interceptor de NestJS con reintentos y timeout. Esta medida busca mejorar la resiliencia y la disponibilidad del sistema.

## Decisión

Se aplica Circuit Breaker: corta las llamadas a un servicio que falla para evitar fallos en cascada. Implementación prevista: nestjs\_interceptor\_con\_reintentos\_y\_timeout.

## Justificación

Llamadas síncronas entre servicios: historia\_clinica -&gt; usuarios, pagos -&gt; usuarios

## Consecuencias

Positivas:

- Previene fallos en cascada al interrumpir llamadas a servicios que están fallando, manteniendo la disponibilidad de los demás servicios.
- Reduce la carga en servicios sobrecargados al limitar el número de intentos, evitando que el consumo de recursos se descontrole.
- Mejora la experiencia del usuario al evitar tiempos de espera prolongados y errores inesperados en la capa de negocio.
- Facilita la observabilidad y el monitoreo al exponer métricas de estado del circuito, lo que ayuda a identificar y corregir problemas rápidamente.

Negativas:

- Aumenta la complejidad del código y la configuración, requiriendo pruebas adicionales para asegurar el correcto funcionamiento del interceptor.
- Puede introducir latencia adicional por los reintentos y los timeouts configurados, afectando la respuesta de los servicios.
- Si los umbrales de activación del circuito se configuran incorrectamente, puede generar falsos positivos, bloqueando servicios que aún funcionan.
- Requiere mantenimiento continuo para ajustar los parámetros de tiempo y umbral según la evolución de la carga y el comportamiento de los servicios.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V11.1.4 | Hay controles contra la automatización que protegen de llamadas excesivas, robo masivo de datos y denegación de servicio |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-400 | Uncontrolled Resource Consumption |
| CWE-770 | Allocation of Resources Without Limits or Throttling |

## Trazabilidad

Servicios afectados: `historia_clinica`, `usuarios`, `pagos`

No la motiva un requisito concreto: OPA la deduce de la estructura.
