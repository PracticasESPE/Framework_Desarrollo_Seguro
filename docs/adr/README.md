<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# Decisiones arquitectónicas (ADR)

Generadas el 2026-11-10 por el framework a partir de `arquitectura.json` y de la validación de OPA, para el documento requisitos.docx (SHA-256 `0515668b00b8`).

Para regenerarlas:

```bash
framework arquitectura adr <arquitectura.json> --requisitos <modelo_requisitos.json>
```

## Validación de OPA

Arquitectura aprobada: cumple los 4 criterios; patrones inferidos: api\_gateway, circuit\_breaker, database\_per\_service, event\_driven, saga

| Regla | Cumple | Detalle |
|---|---|---|
| `arquitectura.base_datos_propia` | sí | Cada servicio tiene su propia base de datos (Database per Service) |
| `arquitectura.sin_ciclos` | sí | Las dependencias entre servicios no forman ciclos |
| `arquitectura.dependencias_conocidas` | sí | Cada dependencia apunta a otro servicio de la arquitectura |
| `arquitectura.servicios_unicos` | sí | Hay al menos un servicio y no hay nombres repetidos |

## Registro

| ADR | Título | Origen | Requisitos |
|---|---|---|---|
| [0001](0001-division-en-microservicios.md) | División en microservicios | Decisión D-01 de la propuesta arquitectónica, validada por OPA | RF-01, RF-02, RF-03, RF-04, RF-05, RF-06, RF-07, RF-08, RF-09, RF-10, RF-11, RF-12, RF-13, RF-14, RF-15, RF-16, RF-17, RF-18, RF-19, RF-20, RNF-01, RNF-02, RNF-03, RNF-04, RNF-05, RNF-06, RNF-07, RNF-08, RNF-09, RNF-10 |
| [0002](0002-comunicacion-entre-microservicios.md) | Comunicación entre microservicios | Decisión D-02 de la propuesta arquitectónica, validada por OPA | RF-10, RF-12, RF-14, RF-16, RNF-09, RNF-06 |
| [0003](0003-seguridad-y-autenticacion.md) | Seguridad y autenticación | Decisión D-03 de la propuesta arquitectónica, validada por OPA | RNF-05, RNF-06, RNF-04, RF-01, RF-02, RF-04, RF-20 |
| [0004](0004-gestion-de-secretos.md) | Gestión de secretos | Decisión D-04 de la propuesta arquitectónica, validada por OPA | RNF-10 |
| [0005](0005-bases-de-datos-aisladas.md) | Bases de datos aisladas | Decisión D-05 de la propuesta arquitectónica, validada por OPA | RNF-09 |
| [0006](0006-aplicar-el-patron-database-per-service.md) | Aplicar el patrón Database per Service | Patrón arq.basedatos.001 inferido por OPA (rasgos: autonomia\_de\_datos) | estructura |
| [0007](0007-aplicar-el-patron-event-driven.md) | Aplicar el patrón Event-Driven | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) | estructura |
| [0008](0008-aplicar-el-patron-api-gateway.md) | Aplicar el patrón API Gateway | Patrón arq.gateway.001 inferido por OPA (rasgos: autenticacion\_centralizada, punto\_unico\_acceso) | RF-01, RF-02, RF-04, RF-20, RNF-05, RNF-06 |
| [0009](0009-aplicar-el-patron-circuit-breaker.md) | Aplicar el patrón Circuit Breaker | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) | estructura |
| [0010](0010-aplicar-el-patron-saga.md) | Aplicar el patrón Saga | Patrón arq.transaccion.001 inferido por OPA (rasgos: transaccion\_entre\_servicios) | estructura |
