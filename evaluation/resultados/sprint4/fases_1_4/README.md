# Fases 1 a 4 con los documentos del dataset (sprint 4)

Generado el 26/11/2026 22:39 UTC con `uv run python -m evaluation.fases_1_4`. Cada carpeta tiene lo de las fases 1 y 2 (ver sprint 3), la especificación de cada servicio (`especificaciones/`), el resumen de la fase 3 (`sistema.json`) y los hallazgos del Gate 1 uno por uno (`hallazgos_gate1.json`).

| Documento | Requisitos | Arquitectura | Servicios completos | Entidades con lógica (al 1.er intento) | Pruebas Jest | Gate 1 aprobados | Hallazgos |
|---|---|---|---|---|---|---|---|
| 03_citas_medicas | 43/43 | aprobada (intento 1) | 6/6 | 26/31 (10) | 185 (descartadas 10) | - | - |

## Detalle

### 03_citas_medicas: Citas médicas

- Pasos: clasificar 339.3 s, proponer 24.3 s, adr 135.9 s, diagrama 2.5 s, sistema 5305.7 s en 2 ejecuciones.
- Tokens del LLM: fase 3 876 007 (129 llamadas); total 876 007.
- Fase 3: 5 entidades sin lógica (para revisión), 0 con error al pedirla, 45 reglas pendientes declaradas por el LLM.
- Advertencia de la arquitectura: La entidad «aviso» está en historia, gestion: cada servicio tendrá su propia tabla en su base (Database per Service).
- Advertencia de la arquitectura: La entidad «cita» está en citas, pagos: cada servicio tendrá su propia tabla en su base (Database per Service).
- Advertencia de la arquitectura: La entidad «especialidad» está en citas, gestion: cada servicio tendrá su propia tabla en su base (Database per Service).
- Advertencia de la arquitectura: La entidad «horario» está en citas, gestion: cada servicio tendrá su propia tabla en su base (Database per Service).
- Advertencia de la arquitectura: La entidad «medico» está en citas, gestion: cada servicio tendrá su propia tabla en su base (Database per Service).
- Advertencia de la arquitectura: La entidad «paciente» está en auth, historia, gestion: cada servicio tendrá su propia tabla en su base (Database per Service).
- Advertencia de la arquitectura: La entidad «sede» está en citas, gestion: cada servicio tendrá su propia tabla en su base (Database per Service).
