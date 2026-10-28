# Políticas de los Security Gates (OPA)

Deciden si cada Security Gate se aprueba o se rechaza. Son reglas deterministas en Rego, el
lenguaje de Open Policy Agent (OPA): el LLM nunca aprueba un gate (principio P1 del plan técnico).
Cada decisión lleva la regla que la justifica, para que sea reproducible y auditable.

| Archivo | Paquete | Qué decide |
|---|---|---|
| `gate1.rego` | `gates.gate1` | Análisis estático (fase 4): tsc, ESLint, Semgrep, Gitleaks, Trivy, Hadolint |
| `gate2.rego` | `gates.gate2` | Seguridad de integración (fase 8): contrato OpenAPI (Spectral) y Docker Compose (Conftest) |
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
  "justificacion": "Gate 1 rechazado: 1 bloqueante(s)"
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

Los hallazgos medios y bajos no bloquean: quedan en `advertencias`. Ante un dato que falta, las
políticas fallan de forma segura (directriz `sbd.fallo.001`): sin dato no hay aprobación.

## Uso

```bash
opa test policies/ -v                                   # pruebas de todas las políticas
opa eval -d policies/gates -i entrada.json "data.gates.gate1.decision"
```

El paso "Políticas OPA (opa test)" del workflow ejecuta las pruebas en cada pull request.
