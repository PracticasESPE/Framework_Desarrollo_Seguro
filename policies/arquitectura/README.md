# Reglas arquitectónicas (fase 2)

Deciden si la propuesta de arquitectura del LLM (`arquitectura.json`) se acepta e infieren los
patrones de la base de conocimiento que aplican, con su justificación (plan técnico, 7.2, paso
2). El motor arma la entrada en `orchestrator/architecture/validacion.py` y consulta
`data.arquitectura.decision`.

## Reglas que bloquean

| Regla | Qué exige |
|---|---|
| `arquitectura.base_datos_propia` | Cada servicio tiene su propia base de datos (Database per Service) |
| `arquitectura.sin_ciclos` | Las dependencias entre servicios no forman ciclos, directos o indirectos |
| `arquitectura.dependencias_conocidas` | Cada dependencia apunta a otro servicio de la arquitectura |
| `arquitectura.servicios_unicos` | Hay al menos un servicio y ningún nombre se repite |

Los motivos de los bloqueantes vuelven al LLM para que corrija la propuesta (ciclo LLM ↔ OPA).

## Advertencias

| Regla | Cuándo avisa |
|---|---|
| `arquitectura.servicio_concentrado` | Un servicio tiene más de la mitad de los requisitos: puede mezclar varios contextos |
| `arquitectura.cadena_sincrona` | Tres servicios encadenados por llamadas síncronas: un fallo se propaga |

## Inferencia de patrones

Cada patrón de `knowledge_base/patrones` declara en `aplica_cuando` un mínimo de servicios y
unas etiquetas. La política deduce de la arquitectura sus **rasgos** y un patrón aplica si hay
servicios suficientes y al menos uno de sus rasgos:

| Rasgo | Se deduce cuando |
|---|---|
| `punto_unico_acceso` | Algún requisito tiene la etiqueta `punto_unico_acceso` o `limite_peticiones` |
| `autenticacion_centralizada` | Hay requisitos de `autenticacion` y más de un servicio |
| `autonomia_de_datos` | Cada servicio tiene su propia base de datos |
| `comunicacion_asincrona` | Alguna dependencia es por eventos |
| `dependencia_sincrona_externa` | Alguna dependencia es una llamada síncrona |
| `transaccion_entre_servicios` | Un servicio llama a otro y depende además de un tercero: coordina una operación |

Las demás etiquetas de la base (`varios_tipos_de_cliente`, `alta_disponibilidad`...) todavía no se
pueden deducir de `arquitectura.json`, así que BFF no se infiere por ahora.

Cada patrón inferido trae su id, la implementación prevista, los controles ASVS y las CWE de la
base de conocimiento, los rasgos por los que aplica y el motivo.

Con la arquitectura que propuso el LLM para el documento 1 del dataset, OPA aprueba y infiere
`api_gateway`, `database_per_service`, `event_driven`, `saga` y `circuit_breaker`: los cinco
patrones de la referencia.

## Pruebas

```bash
opa test policies/arquitectura -v
```
