# Políticas de los Security Gates (OPA)

Deciden si cada Security Gate se aprueba o se rechaza. Son reglas deterministas en Rego, el
lenguaje de Open Policy Agent (OPA): el LLM nunca aprueba un gate (principio P1 del plan técnico).
Cada decisión lleva la regla que la justifica, para que sea reproducible y auditable.

| Archivo | Paquete | Qué decide |
|---|---|---|
| `gate1.rego` | `gates.gate1` | Análisis estático (fase 4): tsc, ESLint, Semgrep, Gitleaks, Trivy, Hadolint |
| `gate2.rego` | `gates.gate2` | Seguridad de integración (fase 8): contrato OpenAPI (Spectral) y Docker Compose (Conftest) |
| `gate3.rego` | `gates.gate3` | Sistema en marcha (fase 11): DAST con ZAP y Nuclei, Trivy image, SBOM de Syft y pruebas de la fase 9 |
| `comun.rego` | `gates.comun` | Utilidades compartidas: severidades, ubicación de un hallazgo, conteo |
| `*_test.rego` | | Pruebas con `opa test`: cada regla con un caso que bloquea y otro que no |

## Entrada y salida

La entrada la arma el motor con los hallazgos ya normalizados por el lector SARIF
(`orchestrator/gates/sarif.py`). La salida es `data.gates.gateN.decision`:

```json
{
  "gate": 1,
  "aprobado": false,
  "bloqueantes": [{"regla": "gate1.severidad", "motivo": "Hallazgo alta de semgrep oss: ... en archivo:42", "huella": "..."}],
  "advertencias": [{"regla": "gate1.aviso", "motivo": "...", "huella": "..."}],
  "conteo": {"critica": 0, "alta": 1, "media": 0, "baja": 0, "info": 0},
  "criterios": [{"regla": "gate1.severidad", "cumple": false, "detalle": "Sin hallazgos críticos o altos"}],
  "justificacion": "Gate 1 rechazado: incumple 1 de 4 criterios (gate1.severidad)"
}
```

## Reglas

| Regla | Gate | Bloquea cuando |
|---|---|---|
| `gate1.severidad` | 1 | hay un hallazgo crítico o alto |
| `gate1.secreto` | 1 | Gitleaks encuentra un secreto, sea cual sea su severidad |
| `gate1.compilacion` | 1 | el código no compila, o no consta que compile |
| `gate1.herramienta_caida` | 1 | una herramienta no terminó |
| `gate2.contrato_api` | 2 | Spectral marca un error en el contrato OpenAPI |
| `gate2.politica_compose` | 2 | Conftest marca un `deny` en el Docker Compose |
| `gate2.severidad` | 2 | otra herramienta de integración da un hallazgo crítico o alto |
| `gate2.contrato` | 2 | no se pudo generar el contrato OpenAPI, o no consta |
| `gate2.herramienta_caida` | 2 | una herramienta no terminó |
| `gate3.dast` | 3 | ZAP o Nuclei encuentran una vulnerabilidad crítica o alta en el sistema en marcha |
| `gate3.imagen` | 3 | Trivy image encuentra una vulnerabilidad crítica o alta en la imagen |
| `gate3.sbom` | 3 | no se generó el SBOM (inventario de componentes), o no consta |
| `gate3.pruebas` | 3 | falla alguna prueba de la fase 9, no se ejecutó ninguna o no hay resultado |
| `gate3.herramienta_caida` | 3 | una herramienta no terminó |

## Justificación de cada decisión

Los tres gates devuelven además `criterios`: la lista de todas sus reglas con `cumple`
(verdadero o falso) y una descripción. Así no solo un rechazo, también una aprobación queda
justificada regla por regla, y la `justificacion` nombra los criterios incumplidos, por ejemplo
"Gate 3 rechazado: incumple 2 de 5 criterios (gate3.dast, gate3.sbom)". Las funciones
`comun.cumple` y `comun.criterios_incumplidos` arman esa lista igual en los tres gates.

Los hallazgos medios y bajos no bloquean: quedan en `advertencias`. Ante un dato que falta, las
políticas fallan de forma segura (directriz `sbd.fallo.001`): sin dato no hay aprobación.

## Uso

```bash
opa test policies/ -v                                   # pruebas de todas las políticas
opa eval -d policies/gates -i entrada.json "data.gates.gate3.decision"
```

El paso "Políticas OPA (opa test)" del workflow ejecuta las pruebas en cada pull request.

## Decisiones desde el motor y registro en Neo4j

El motor arma la entrada a partir de los artefactos del pipeline (`salida/security/sarif/`,
`salida/openapi/usuarios.json`, `salida/sbom/sbom.json` y `salida/pruebas/jest.json`), pide la
decisión a OPA (`orchestrator/gates/decision.py`) y la guarda en `salida/gates/gateN.json`:

```bash
uv run framework gates decidir --gate 1 --compilacion-ok   # termina con código 1 si se rechaza
uv run framework gates listar                               # decisiones de la última ejecución
```

Con Neo4j configurado, cada decisión queda en el grafo como un nodo `ResultadoGate` enlazado a
su ejecución y a las reglas que la justifican. Los tres gates de un mismo pipeline comparten
ejecución (la de la fase 4 o la que crea el primer gate):

```
(:Ejecucion)-[:TIENE_RESULTADO]->(:ResultadoGate)-[:BASADA_EN {cumple, detalle}]->(:Regla)
(:ResultadoGate)-[:BLOQUEADO_POR {regla}]->(:Hallazgo)
```

Consulta para ver las decisiones con sus criterios en Neo4j Browser:

```cypher
MATCH p = (e:Ejecucion)-[:TIENE_RESULTADO]->(r:ResultadoGate)-[:BASADA_EN]->(g:Regla)
WHERE e.id = $ejecucion
RETURN p
```

`tests/datos/gates/` tiene un pipeline de ejemplo completo: el Gate 1 se rechaza por un secreto
y hallazgos altos, el Gate 2 se aprueba con una advertencia y el Gate 3 se rechaza por una
inyección SQL que encuentra ZAP.
