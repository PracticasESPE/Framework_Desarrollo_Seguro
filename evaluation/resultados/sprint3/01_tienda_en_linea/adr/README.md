<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# Decisiones arquitectónicas (ADR)

Generadas el 2026-11-14 por el framework a partir de `arquitectura.json` y de la validación de OPA, para el documento requisitos.docx (SHA-256 `0515668b00b8`).

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

- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas ventas -&gt; pedidos -&gt; catalogo: si catalogo falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas ventas -&gt; pedidos -&gt; usuarios: si usuarios falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.ciclo_de_eventos`: pagos, pedidos dependen unos de otros en círculo (pagos -&gt; pedidos (asincrona), pedidos -&gt; pagos (asincrona)): es una saga coreografiada; documenta sus eventos y la compensación si un paso falla

## Registro

| ADR | Título | Origen | Requisitos |
|---|---|---|---|
| [0001](0001-division-en-5-microservicios.md) | División en 5 microservicios | Decisión D-01 de la propuesta arquitectónica, validada por OPA | RF-01, RF-02, RF-06, RF-10, RF-15, RF-19 |
| [0002](0002-patron-de-comunicacion.md) | Patrón de comunicación | Decisión D-02 de la propuesta arquitectónica, validada por OPA | RF-01, RF-11, RF-15, RF-16, RF-20 |
| [0003](0003-uso-de-rabbitmq-para-eventos-de-dominio.md) | Uso de RabbitMQ para eventos de dominio | Decisión D-03 de la propuesta arquitectónica, validada por OPA | RF-15, RF-17, RF-16, RNF-09 |
| [0004](0004-base-de-datos-por-microservicio.md) | Base de datos por microservicio | Decisión D-04 de la propuesta arquitectónica, validada por OPA | RNF-09, RNF-10, RNF-05 |
| [0005](0005-seguridad-y-calidad-de-servicio-transversal.md) | Seguridad y calidad de servicio transversal | Decisión D-05 de la propuesta arquitectónica, validada por OPA | RNF-05, RNF-06, RNF-07, RNF-04, RNF-01 |
| [0006](0006-aplicar-el-patron-database-per-service.md) | Aplicar el patrón Database per Service | Patrón arq.basedatos.001 inferido por OPA (rasgos: autonomia\_de\_datos) | estructura |
| [0007](0007-aplicar-el-patron-event-driven.md) | Aplicar el patrón Event-Driven | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) | estructura |
| [0008](0008-aplicar-el-patron-api-gateway.md) | Aplicar el patrón API Gateway | Patrón arq.gateway.001 inferido por OPA (rasgos: autenticacion\_centralizada, punto\_unico\_acceso) | RF-02, RF-03, RF-05, RF-21, RNF-05, RNF-06 |
| [0009](0009-aplicar-el-patron-circuit-breaker.md) | Aplicar el patrón Circuit Breaker | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) | estructura |
| [0010](0010-aplicar-el-patron-saga.md) | Aplicar el patrón Saga | Patrón arq.transaccion.001 inferido por OPA (rasgos: transaccion\_entre\_servicios) | estructura |
