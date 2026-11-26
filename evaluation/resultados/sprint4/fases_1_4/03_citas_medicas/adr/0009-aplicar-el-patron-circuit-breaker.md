<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0009: Aplicar el patrón Circuit Breaker

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-25 |
| Origen | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema realiza llamadas síncronas entre microservicios (citas, gestión, historia, laboratorio, pagos) y el servicio de autenticación. Cuando uno de estos servicios falla, las llamadas sucesivas pueden provocar fallos en cascada, afectando la disponibilidad del sistema. Para mitigar este riesgo se decide aplicar el patrón Circuit Breaker, interrumpiendo las llamadas a un servicio que presenta fallos repetidos y evitando la sobrecarga de recursos.

## Decisión

Se aplica Circuit Breaker: corta las llamadas a un servicio que falla para evitar fallos en cascada. Implementación prevista: nestjs\_interceptor\_con\_reintentos\_y\_timeout.

## Justificación

Llamadas síncronas entre servicios: citas -&gt; auth, gestion -&gt; auth, historia -&gt; auth, laboratorio -&gt; auth, pagos -&gt; auth

## Consecuencias

Positivas:

- Reduce la propagación de fallos, manteniendo la disponibilidad de los servicios que no están afectados.
- Limita el consumo de recursos en caso de fallos, evitando que un servicio saturado agote la capacidad del clúster.
- Mejora la experiencia del usuario al evitar tiempos de espera prolongados cuando un servicio está caído.
- Facilita la detección temprana de problemas, ya que el circuito abierto actúa como indicador de fallos persistentes.

Negativas:

- Aumenta la complejidad del código y la configuración, requiriendo interceptores y lógica de reintentos.
- Puede introducir latencia adicional por los reintentos y los timeouts configurados.
- El manejo incorrecto de los estados del circuito puede bloquear llamadas legítimas, generando falsos positivos.
- Requiere monitoreo y métricas específicas para ajustar los umbrales de activación del circuito.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V11.1.4 | Hay controles contra la automatización que protegen de llamadas excesivas, robo masivo de datos y denegación de servicio |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-400 | Uncontrolled Resource Consumption |
| CWE-770 | Allocation of Resources Without Limits or Throttling |

## Trazabilidad

Servicios afectados: `citas`, `auth`, `gestion`, `historia`, `laboratorio`, `pagos`

No la motiva un requisito concreto: OPA la deduce de la estructura.
