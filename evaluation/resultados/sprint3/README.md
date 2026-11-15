# Fases 1 y 2 con los documentos del dataset (sprint 3)

Generado el 15/11/2026 14:37 UTC con `uv run python -m evaluation.fases_1_2 --formato docx`. Cada carpeta tiene el modelo de requisitos, la arquitectura aprobada, el registro de intentos del ciclo LLM ↔ OPA, los ADR, el diagrama C4, las evaluaciones y la salida de cada comando (`ejecucion.log`).

## Fase 1: requisitos

| Documento | Encontrados | Falsos positivos | Tipo correcto | Etiquetas (P / R / F1) |
|---|---|---|---|---|
| 01_tienda_en_linea | 30/30 (100%) | 1 | 27/30 (90%) | 91% / 62% / 0.74 |
| 02_gestion_academica | 38/38 (100%) | 1 | 33/38 (87%) | 95% / 50% / 0.65 |
| 03_citas_medicas | 43/43 (100%) | 1 | 37/43 (86%) | 91% / 44% / 0.60 |

## Fase 2: arquitectura

| Documento | Ciclo LLM ↔ OPA | Servicios (propuestos / referencia) | Coinciden | Agrupación (P / R / F1) | Patrones de la referencia inferidos | ADR |
|---|---|---|---|---|---|---|
| 01_tienda_en_linea | aprobada en el intento 1 | 5 / 5 | 4 | 83% / 83% / 0.83 | 5/5 | 10 |
| 02_gestion_academica | aprobada en el intento 1 | 7 / 6 | 4 | 62% / 56% / 0.59 | 4/4 (además saga) | 8 |
| 03_citas_medicas | aprobada en el intento 1 | 6 / 6 | 4 | 79% / 79% / 0.79 | 4/6 (falta bff, saga) | 9 |

## Detalle por documento

### 01_tienda_en_linea: Tienda en línea

- Pasos: clasificar 239.0 s, registrar 10.6 s, proponer 17.2 s, adr 145.4 s, diagrama 4.5 s.
- Tipo incorrecto: RF-14: no_funcional (esperado funcional); RF-20: no_funcional (esperado funcional); RF-21: no_funcional (esperado funcional).
- Falsos positivos: RF-01 [1, párrafo 2] La empresa quiere que sus clientes compren a cualquier hora, que el stock se act.
- Avisos de OPA: arquitectura.cadena_sincrona ×2, arquitectura.ciclo_de_eventos.
- Patrones inferidos: api_gateway, circuit_breaker, database_per_service, event_driven, saga.
- Servicios propuestos: usuarios, catalogo, pedidos, pagos, ventas.
- Correspondencia con la referencia: catalogo -> catalogo, notificaciones -> pedidos, pagos -> pagos, pedidos -> pedidos, transversal -> transversal, usuarios -> usuarios.

### 02_gestion_academica: Gestión académica

- Pasos: clasificar 526.7 s, registrar 10.0 s, proponer 21.8 s, adr 45.1 s, diagrama 1.6 s.
- Tipo incorrecto: RNF-01: funcional (esperado no_funcional); RF-12: no_funcional (esperado funcional); RNF-06: funcional (esperado no_funcional); RNF-07: funcional (esperado no_funcional); RNF-10: funcional (esperado no_funcional).
- Falsos positivos: RF-01 [1, párrafo 2] El instituto quiere un sistema en línea para estudiantes, docentes y personal ad.
- Avisos de OPA: arquitectura.cadena_sincrona ×10.
- Patrones inferidos: api_gateway, circuit_breaker, database_per_service, event_driven, saga.
- Servicios propuestos: usuarios, catalogo, matriculas, notas, asistencia, certificados, notificaciones.
- Correspondencia con la referencia: calificaciones -> notas, certificados -> certificados, matriculas -> matriculas, notificaciones -> notificaciones, oferta -> catalogo, transversal -> transversal, usuarios -> usuarios.

### 03_citas_medicas: Citas médicas

- Pasos: clasificar 191.7 s, registrar 26.8 s, proponer reutilizado, adr 312.1 s, diagrama 39.0 s.
- Tipo incorrecto: RF-01: no_funcional (esperado funcional); RF-03: no_funcional (esperado funcional); RF-05: no_funcional (esperado funcional); RF-25: no_funcional (esperado funcional); RNF-06: funcional (esperado no_funcional); RNF-09: funcional (esperado no_funcional).
- Falsos positivos: RF-01 [1, párrafo 2] La red quiere que los pacientes reserven y paguen sus citas en línea, que la his.
- Patrones inferidos: api_gateway, circuit_breaker, database_per_service, event_driven.
- Servicios propuestos: usuarios, citas, historia_clinica, pagos, laboratorio, administracion.
- Correspondencia con la referencia: agenda -> citas, historia_clinica -> historia_clinica, laboratorio -> laboratorio, notificaciones -> citas, pagos -> pagos, transversal -> transversal, usuarios -> usuarios.

