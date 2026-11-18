<!-- Generado por el framework (framework arquitectura adr). Se regenera: no lo edites. -->
# Decisiones arquitectónicas (ADR)

Generadas el 2026-11-14 por el framework a partir de `arquitectura.json` y de la validación de OPA, para el documento requisitos.docx (SHA-256 `16229f92f991`).

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

- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas asistencia -&gt; catalogo -&gt; usuarios: si usuarios falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas certificados -&gt; matriculas -&gt; catalogo: si catalogo falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas certificados -&gt; matriculas -&gt; usuarios: si usuarios falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas certificados -&gt; notas -&gt; catalogo: si catalogo falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas certificados -&gt; notas -&gt; matriculas: si matriculas falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas certificados -&gt; notas -&gt; usuarios: si usuarios falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas matriculas -&gt; catalogo -&gt; usuarios: si usuarios falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas notas -&gt; catalogo -&gt; usuarios: si usuarios falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas notas -&gt; matriculas -&gt; catalogo: si catalogo falla o tarda, arrastra a los demás; considera eventos
- `arquitectura.cadena_sincrona`: Cadena de llamadas síncronas notas -&gt; matriculas -&gt; usuarios: si usuarios falla o tarda, arrastra a los demás; considera eventos

## Registro

| ADR | Título | Origen | Requisitos |
|---|---|---|---|
| [0001](0001-division-en-7-microservicios.md) | División en 7 microservicios | Decisión D-01 de la propuesta arquitectónica, validada por OPA | RF-01, RF-03, RF-07, RF-11, RF-16, RF-15, RF-21, RF-24 |
| [0002](0002-comunicacion-sincrona-vs-asincrona.md) | Comunicación síncrona vs asíncrona | Decisión D-02 de la propuesta arquitectónica, validada por OPA | RF-30, RNF-04, RF-24, RF-25 |
| [0003](0003-seguridad-y-gestion-de-secretos.md) | Seguridad y gestión de secretos | Decisión D-03 de la propuesta arquitectónica, validada por OPA | RF-05, RF-06, RNF-03, RNF-06, RNF-07 |
| [0004](0004-aplicar-el-patron-database-per-service.md) | Aplicar el patrón Database per Service | Patrón arq.basedatos.001 inferido por OPA (rasgos: autonomia\_de\_datos) | estructura |
| [0005](0005-aplicar-el-patron-event-driven.md) | Aplicar el patrón Event-Driven | Patrón arq.eventos.001 inferido por OPA (rasgos: comunicacion\_asincrona) | estructura |
| [0006](0006-aplicar-el-patron-api-gateway.md) | Aplicar el patrón API Gateway | Patrón arq.gateway.001 inferido por OPA (rasgos: autenticacion\_centralizada, punto\_unico\_acceso) | RF-03, RF-04, RF-05, RF-06, RNF-02, RNF-03, RNF-05 |
| [0007](0007-aplicar-el-patron-circuit-breaker.md) | Aplicar el patrón Circuit Breaker | Patrón arq.resiliencia.001 inferido por OPA (rasgos: dependencia\_sincrona\_externa) | estructura |
| [0008](0008-aplicar-el-patron-saga.md) | Aplicar el patrón Saga | Patrón arq.transaccion.001 inferido por OPA (rasgos: transaccion\_entre\_servicios) | estructura |
