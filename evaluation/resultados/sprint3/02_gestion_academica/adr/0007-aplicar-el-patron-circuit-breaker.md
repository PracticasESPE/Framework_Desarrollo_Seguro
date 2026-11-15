<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0007: Aplicar el patrón Circuit Breaker

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-14 |
| Origen | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) |
| Documento de requisitos | requisitos.docx (SHA-256 `16229f92f991`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

La arquitectura basada en microservicios NestJS presenta múltiples dependencias síncronas entre dominios como asistencia, catálogo, usuarios, certificados, matrículas y notas. Para cumplir con el control ASVS-V11.1.4 y mitigar vulnerabilidades como CWE-400 y CWE-770, se requiere proteger el sistema frente al agotamiento de recursos causado por fallos en cadena. La aplicación del patrón Circuit Breaker mediante un interceptor con reintentos y timeout evita que la indisponibilidad de un servicio sature las conexiones de toda la plataforma.

## Decisión

Se aplica Circuit Breaker: corta las llamadas a un servicio que falla para evitar fallos en cascada. Implementación prevista: nestjs\_interceptor\_con\_reintentos\_y\_timeout.

## Justificación

Llamadas síncronas entre servicios: asistencia -&gt; catalogo, asistencia -&gt; usuarios, catalogo -&gt; usuarios, certificados -&gt; matriculas, certificados -&gt; notas, certificados -&gt; usuarios, matriculas -&gt; catalogo, matriculas -&gt; usuarios, notas -&gt; catalogo, notas -&gt; matriculas, notas -&gt; usuarios

## Consecuencias

Positivas:

- Evita fallos en cascada y la saturación de recursos en los microservicios NestJS cuando una dependencia síncrona deja de responder.
- Mitiga directamente CWE-400 y CWE-770 al limitar el consumo descontrolado de conexiones y hilos de ejecución.
- Alinea la infraestructura autoalojada con el control ASVS-V11.1.4 frente a la denegación de servicio por llamadas excesivas.

Negativas:

- Introduce complejidad operativa en la gestión y monitorización de los estados de los Circuit Breakers en todos los contenedores.
- Puede generar respuestas de error inesperadas hacia los clientes si el circuito se abre prematuramente debido a timeouts mal configurados.

## Controles de seguridad

| Control ASVS | Qué exige |
|---|---|
| ASVS-V11.1.4 | Hay controles contra la automatización que protegen de llamadas excesivas, robo masivo de datos y denegación de servicio |

| CWE | Debilidad que mitiga |
|---|---|
| CWE-400 | Uncontrolled Resource Consumption |
| CWE-770 | Allocation of Resources Without Limits or Throttling |

## Trazabilidad

Servicios afectados: `asistencia`, `catalogo`, `usuarios`, `certificados`, `matriculas`, `notas`

No la motiva un requisito concreto: OPA la deduce de la estructura.
