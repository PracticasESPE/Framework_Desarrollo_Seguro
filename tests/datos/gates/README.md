# Ejemplo de resultados de los tres gates

Carpeta con la misma forma que `salida/` tras una ejecución del pipeline, para probar y demostrar
las decisiones de OPA sin ejecutar las herramientas:

| Gate | Archivos | Decisión esperada |
|---|---|---|
| 1 | `security/sarif/{semgrep,gitleaks,trivy-fs,trivy-config,hadolint}.sarif` | Rechazado: inyección SQL (Semgrep), un secreto (Gitleaks) y una CVE crítica (Trivy) |
| 2 | `security/sarif/{spectral,conftest}.sarif` y `openapi/usuarios.json` | Aprobado con una advertencia de Conftest |
| 3 | `security/sarif/{trivy-image,zap,nuclei}.sarif`, `sbom/sbom.json` y `pruebas/jest.json` | Rechazado: inyección SQL detectada por ZAP |

```bash
uv run framework gates decidir --gate 1 --salida tests/datos/gates --compilacion-ok --no-bloquear
```
