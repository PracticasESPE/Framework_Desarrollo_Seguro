<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# Decisiones arquitectónicas (ADR)

Generadas el 2026-11-25 por el framework a partir de `arquitectura.json` y de la validación de OPA, para el documento requisitos.docx (SHA-256 `97afabd99b91`).

Para regenerarlas:

```bash
framework arquitectura adr <arquitectura.json> --requisitos <modelo_requisitos.json>
```

## Validación de OPA

Arquitectura aprobada: cumple los 4 criterios; patrones inferidos: api\_gateway, circuit\_breaker, database\_per\_service, event\_driven, saga

| Regla | Cumple | Detalle |
|---|---|---|
| `arquitectura.base_datos_propia` | sí | Cada servicio tiene su propia base de datos (Database per Service) |
| `arquitectura.sin_ciclos` | sí | Las llamadas síncronas entre servicios no forman ciclos |
| `arquitectura.dependencias_conocidas` | sí | Cada dependencia apunta a otro servicio de la arquitectura |
| `arquitectura.servicios_unicos` | sí | Hay al menos un servicio y no hay nombres repetidos |

Advertencias:

- `arquitectura.ciclo_de_eventos`: citas, gestion, historia, laboratorio, pagos dependen unos de otros en círculo (citas -&gt; gestion (asincrona), citas -&gt; pagos (asincrona), gestion -&gt; citas (asincrona), gestion -&gt; historia (asincrona), gestion -&gt; laboratorio (asincrona), historia -&gt; gestion (asincrona), historia -&gt; laboratorio (asincrona), laboratorio -&gt; gestion (asincrona), pagos -&gt; citas (asincrona), pagos -&gt; gestion (asincrona)): es una saga coreografiada; documenta sus eventos y la compensación si un paso falla

## Registro

| ADR | Título | Origen | Requisitos |
|---|---|---|---|
| [0001](0001-division-en-6-microservicios.md) | División en 6 microservicios | Decisión D-01 de la propuesta arquitectónica, validada por OPA | RF-01, RF-02, RF-03, RF-04, RF-05, RF-06, RF-07, RF-08, RF-09, RF-10, RF-11, RF-12, RF-13, RF-14, RF-15, RF-16, RF-17, RF-18, RF-19, RF-20, RF-21, RF-22, RF-23, RF-24, RF-25, RF-26, RF-27, RF-28, RF-29, RF-30, RF-31, RF-32, RF-33, RF-34, RF-35, RF-36 |
| [0002](0002-comunicacion-sincrona-vs-asincrona.md) | Comunicación síncrona vs asíncrona | Decisión D-02 de la propuesta arquitectónica, validada por OPA | RF-03, RF-04, RF-06, RF-21, RF-22, RF-23, RF-25, RF-27, RF-28, RF-29 |
| [0003](0003-base-de-datos-por-microservicio.md) | Base de datos por microservicio | Decisión D-03 de la propuesta arquitectónica, validada por OPA | RNF-02, RNF-07 |
| [0004](0004-uso-de-rabbitmq-para-eventos.md) | Uso de RabbitMQ para eventos | Decisión D-04 de la propuesta arquitectónica, validada por OPA | RF-21, RF-22, RF-23, RF-25, RF-27, RF-28, RF-29, RF-36 |
| [0005](0005-seguridad-y-gestion-de-secretos.md) | Seguridad y gestión de secretos | Decisión D-05 de la propuesta arquitectónica, validada por OPA | RNF-03, RNF-07, RF-03, RF-04, RF-06 |
| [0006](0006-aplicar-el-patron-database-per-service.md) | Aplicar el patrón Database per Service | Patrón arq.basedatos.001 inferido por OPA (rasgos: autonomia\_de\_datos) | estructura |
| [0007](0007-aplicar-el-patron-event-driven.md) | Aplicar el patrón Event-Driven | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) | estructura |
| [0008](0008-aplicar-el-patron-api-gateway.md) | Aplicar el patrón API Gateway | Patrón arq.gateway.001 inferido por OPA (rasgos: autenticacion\_centralizada, punto\_unico\_acceso) | RF-01, RF-03, RF-04, RF-06, RNF-01, RF-21, RF-27, RNF-03, RNF-04 |
| [0009](0009-aplicar-el-patron-circuit-breaker.md) | Aplicar el patrón Circuit Breaker | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) | estructura |
| [0010](0010-aplicar-el-patron-saga.md) | Aplicar el patrón Saga | Patrón arq.transaccion.001 inferido por OPA (rasgos: transaccion\_entre\_servicios) | estructura |
