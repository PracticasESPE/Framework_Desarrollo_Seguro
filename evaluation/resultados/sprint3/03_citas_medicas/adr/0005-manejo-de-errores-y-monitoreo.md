<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# ADR-0005: Manejo de errores y monitoreo

| Campo | Valor |
|---|---|
| Estado | Aceptada |
| Fecha | 2026-11-15 |
| Origen | Decisión D-05 de la propuesta arquitectónica, validada por OPA |
| Documento de requisitos | requisitos.docx (SHA-256 `97afabd99b91`) |
| Redacción | LLM (groq), revisada por el motor |

## Contexto

El sistema debe evitar exponer información interna a través de los mensajes de error y garantizar la disponibilidad del 99,5 % durante el horario de atención. Para cumplir con RNF‑12 y RNF‑11, se decide implementar un manejo genérico de errores y centralizar el logging y métricas en ELK + Prometheus.

## Decisión

Se implementa manejo genérico de errores sin exponer detalles internos y se centraliza el logging y métricas en ELK + Prometheus; los mensajes de error cumplen RNF‑12.

## Justificación

Evita fuga de información sensible y facilita el cumplimiento del SLA (RNF‑11).

## Consecuencias

Positivas:

- Mejora la seguridad al no revelar detalles internos.
- Facilita el cumplimiento del SLA al permitir monitoreo y alertas tempranas.
- Reduce la complejidad de los microservicios al unificar la lógica de error.
- Mejora la trazabilidad y depuración gracias a ELK y Prometheus.

Negativas:

- Incrementa la carga operativa al mantener y escalar ELK y Prometheus.
- Requiere configuración adicional de los microservicios para enviar logs y métricas.
- Posible latencia adicional en la respuesta al incluir procesamiento de logs.
- Necesidad de capacitación del equipo en herramientas de observabilidad.

## Trazabilidad

Servicios afectados: todos (requisito transversal)

| Requisito | Texto del documento |
|---|---|
| RNF-12 | Los mensajes de error no muestran detalles internos del sistema. |
| RNF-11 | El sistema debe estar disponible el 99,5 % del tiempo en el horario de atención de las clínicas, de 07:00 a 20:00. |
