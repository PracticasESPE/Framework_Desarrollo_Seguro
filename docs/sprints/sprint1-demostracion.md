# Sprint 1: demostración del walking skeleton hasta el Gate 1

Hito del plan técnico (16 de octubre de 2026): *un microservicio pasa el Gate 1 en CI y sus
hallazgos quedan en Neo4j. Si no se cumple, no se avanza a la generación con LLM.*

## Qué se demuestra

```
Servicio de referencia   Gate 1 (Abner)          Fase 4 del motor (Marcelo)     Neo4j
services/usuarios  ──►  tsc, ESLint, Semgrep, ──► lee los SARIF y los      ──► Ejecucion
                        Gitleaks, Trivy,          normaliza como hallazgos      ─REGISTRA─► Hallazgo
                        Hadolint → SARIF                                         ─ES─► CWE
```

Todo el recorrido se ejecuta solo en GitHub Actions en cada pull request hacia `dev`, `test` o
`main` (`.github/workflows/framework.yml`, un paso por fase).

## Demostración en CI

1. Abrir la última ejecución de **Actions → framework-desarrollo-seguro → Pipeline por fases**.
2. Mostrar en orden los pasos:
   - **Pruebas del motor (pytest, incluye integración con Neo4j)**: todas en verde.
   - **Fase 4 - Security Gate 1**: tabla de las 8 herramientas y "Gate 1 aprobado".
   - **Fase 4 en el motor: hallazgos registrados en Neo4j**: SARIF leídos y ejecución creada.
   - **Hallazgos visibles en Neo4j**: hallazgos de la ejecución y conteo de nodos.
   - **Demostración: SARIF de ejemplo registrados en Neo4j**: cómo se ven los hallazgos cuando
     sí los hay (crítico, alto, medio, bajo) con sus CWE.
3. En **Summary**, mostrar las tablas del Gate 1, de la fase 4 y de las pruebas del motor.
4. En la pestaña **Security** del repositorio, los hallazgos publicados por cada herramienta.

## Demostración local

Requiere Docker Desktop en marcha, `uv` instalado y el archivo `.env` completo.

```bash
docker compose -f docker-compose.dev.yml up -d neo4j
uv run framework grafo esquema
bash scripts/gate1.sh
uv run framework run --fase 4 --grafo --descripcion "Demostración sprint 1"
uv run framework hallazgos listar
```

Después, en Neo4j Browser (`http://localhost:7474`):

```cypher
MATCH p = (e:Ejecucion)-[:REGISTRA]->(h:Hallazgo)
OPTIONAL MATCH q = (h)-[:ES]->(:CWE)
RETURN p, q
```

## Resultado al cierre del sprint

| Elemento | Estado |
|---|---|
| Servicio de referencia `usuarios` (NestJS, Prisma, Jest) | Compila y pasa sus pruebas en CI |
| Gate 1 con 8 herramientas y publicación de SARIF | Aprobado, sin hallazgos |
| Lector SARIF y modelo común de hallazgos | Probado con ejemplos y con salidas reales de Hadolint y Gitleaks |
| Esquema de Neo4j (14 restricciones, 7 índices) | Aplicado en local y en cada ejecución de CI |
| Registro de ejecuciones y hallazgos en Neo4j | Funciona en local y en CI |
| Pruebas del motor | 106 pruebas, 95 % de cobertura de `orchestrator/` |
| Proveedor de LLM | Groq elegido (`evaluation/comparacion_llm/`) |

## Pendiente para el sprint 2

- Neo4j de CI es temporal: los hallazgos de cada ejecución se pierden al terminar el trabajo.
  Para la evaluación habrá que exportarlos o usar un Neo4j persistente.
- La decisión de aprobar el gate todavía la toma `scripts/gate1.sh`; en el sprint 2 pasa a OPA
  (`policies/gates/gate1.rego`), como exige el principio P1 del plan.
- Los hallazgos aún no se enlazan a un `Componente`: llegará con la generación de servicios.
