<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# Decisiones arquitectónicas (ADR)

Generadas el 2026-11-15 por el framework a partir de `arquitectura.json` y de la validación de OPA, para el documento requisitos.docx (SHA-256 `97afabd99b91`).

Para regenerarlas:

```bash
framework arquitectura adr <arquitectura.json> --requisitos <modelo_requisitos.json>
```

## Validación de OPA

Arquitectura aprobada: cumple los 4 criterios; patrones inferidos: api\_gateway, circuit\_breaker, database\_per\_service, event\_driven

| Regla | Cumple | Detalle |
|---|---|---|
| `arquitectura.base_datos_propia` | sí | Cada servicio tiene su propia base de datos (Database per Service) |
| `arquitectura.sin_ciclos` | sí | Las llamadas síncronas entre servicios no forman ciclos |
| `arquitectura.dependencias_conocidas` | sí | Cada dependencia apunta a otro servicio de la arquitectura |
| `arquitectura.servicios_unicos` | sí | Hay al menos un servicio y no hay nombres repetidos |

## Registro

| ADR | Título | Origen | Requisitos |
|---|---|---|---|
| [0001](0001-division-en-microservicios.md) | División en microservicios | Decisión D-01 de la propuesta arquitectónica, validada por OPA | RF-01, RF-02, RF-03, RF-04, RF-05, RF-06, RF-07, RF-08, RF-09, RF-10, RF-11, RF-12, RF-13, RF-14, RF-15, RF-16, RF-17, RF-18, RF-19, RF-20, RF-21, RF-22, RF-23, RF-24, RF-25, RF-26, RF-27, RF-28, RF-29, RF-30, RNF-01, RNF-02, RNF-03, RNF-04, RNF-05, RNF-06, RNF-07, RNF-08, RNF-09, RNF-10, RNF-11, RNF-12, RNF-13, RNF-14 |
| [0002](0002-comunicacion-entre-servicios.md) | Comunicación entre servicios | Decisión D-02 de la propuesta arquitectónica, validada por OPA | RF-21, RF-19, RNF-06, RNF-10 |
| [0003](0003-seguridad-y-autenticacion.md) | Seguridad y autenticación | Decisión D-03 de la propuesta arquitectónica, validada por OPA | RNF-09, RNF-13 |
| [0004](0004-base-de-datos-por-servicio.md) | Base de datos por servicio | Decisión D-04 de la propuesta arquitectónica, validada por OPA | RF-30, RNF-05 |
| [0005](0005-manejo-de-errores-y-monitoreo.md) | Manejo de errores y monitoreo | Decisión D-05 de la propuesta arquitectónica, validada por OPA | RNF-12, RNF-11 |
| [0006](0006-aplicar-el-patron-database-per-service.md) | Aplicar el patrón Database per Service | Patrón arq.basedatos.001 inferido por OPA (rasgos: autonomia\_de\_datos) | estructura |
| [0007](0007-aplicar-el-patron-event-driven.md) | Aplicar el patrón Event-Driven | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) | estructura |
| [0008](0008-aplicar-el-patron-api-gateway.md) | Aplicar el patrón API Gateway | Patrón arq.gateway.001 inferido por OPA (rasgos: autenticacion\_centralizada, punto\_unico\_acceso) | RF-02, RNF-02, RNF-03, RNF-04, RF-18, RNF-09, RNF-10 |
| [0009](0009-aplicar-el-patron-circuit-breaker.md) | Aplicar el patrón Circuit Breaker | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) | estructura |
