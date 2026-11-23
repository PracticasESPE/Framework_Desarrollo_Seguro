"""Decisión del Gate 1 sobre los servicios generados (fase 4, #71).

scripts/gate1-servicios.sh deja los SARIF de cada servicio en
salida/security/sarif/servicios/<servicio>/ y el resultado de tsc en `compilacion.txt`. Aquí se
pide a OPA la decisión de cada uno con la misma política que el servicio de referencia
(policies/gates/gate1.rego), más ESLint: en los servicios generados, sus resultados también son
hallazgos (un error de una regla es severidad alta y bloquea). Cada decisión se guarda en
salida/gates/servicios/<servicio>/gate1.json, sin tocar la del servicio de referencia.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from orchestrator.gates.decision import (
    POLITICAS_POR_DEFECTO,
    DecisionGate,
    EntradaGate,
    construir_entrada,
    evaluar,
)

# Además de las del Gate 1: en el servicio de referencia ESLint solo da un resultado en el script.
HERRAMIENTAS_DE_SERVICIO = {"eslint.sarif": "eslint"}


@dataclass
class DecisionServicio:
    servicio: str
    entrada: EntradaGate
    decision: DecisionGate
    destino: Path


def compilo(carpeta: Path) -> bool:
    """tsc --noEmit terminó bien. Si no hay resultado, se asume que no (fallo seguro)."""
    try:
        return (carpeta / "compilacion.txt").read_text(encoding="utf-8").strip() == "ok"
    except OSError:
        return False


def decidir_servicios(
    carpeta_sarif: Path,
    salida: Path,
    politicas: Path = POLITICAS_POR_DEFECTO,
    opa: str | None = None,
) -> list[DecisionServicio]:
    """La decisión del Gate 1 de cada servicio de `carpeta_sarif`, en orden alfabético."""
    decisiones = []
    for carpeta in sorted(p for p in carpeta_sarif.iterdir() if p.is_dir()):
        entrada = construir_entrada(
            1, salida, carpeta, compilo(carpeta), herramientas_extra=HERRAMIENTAS_DE_SERVICIO
        )
        decision = evaluar(entrada, politicas, opa)
        destino = salida / "gates" / "servicios" / carpeta.name / "gate1.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(
            json.dumps(
                {
                    "servicio": carpeta.name,
                    "entrada": entrada.datos,
                    "decision": decision.model_dump(),
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        decisiones.append(DecisionServicio(carpeta.name, entrada, decision, destino))
    return decisiones


def resumen_markdown(decisiones: list[DecisionServicio]) -> str:
    """Tabla para la página de la ejecución de GitHub Actions."""
    lineas = [
        "### Decisión OPA del Gate 1 sobre los servicios generados",
        "",
        "| Servicio | Decisión | Hallazgos (crítica/alta/media/baja) | Bloqueantes |",
        "|---|---|---|---|",
    ]
    for d in decisiones:
        c = d.decision.conteo
        conteo = "/".join(str(c.get(s, 0)) for s in ("critica", "alta", "media", "baja"))
        bloqueantes = "; ".join(b.motivo for b in d.decision.bloqueantes[:3]) or "-"
        if len(d.decision.bloqueantes) > 3:
            bloqueantes += f" (y {len(d.decision.bloqueantes) - 3} más)"
        estado = "aprobado" if d.decision.aprobado else "**rechazado**"
        lineas.append(f"| {d.servicio} | {estado} | {conteo} | {bloqueantes} |")
    aprobados = sum(d.decision.aprobado for d in decisiones)
    lineas += ["", f"{aprobados} de {len(decisiones)} servicios aprobados.", ""]
    return "\n".join(lineas)
