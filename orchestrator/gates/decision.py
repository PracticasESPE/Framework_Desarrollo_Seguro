"""Decisión de los Security Gates con OPA (principio P1: el LLM propone, las reglas deciden).

El motor arma la entrada de cada gate a partir de los SARIF que dejan los scripts de los gates,
se la pasa a las políticas Rego de policies/gates mediante `opa eval` y devuelve la decisión
con su justificación: los bloqueantes, las advertencias y el resultado de cada criterio.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from orchestrator.gates.hallazgos import Hallazgo
from orchestrator.gates.sarif import ErrorSarif, leer_sarif
from orchestrator.opa import ErrorOPA, consultar

RAIZ = Path(__file__).resolve().parents[2]
POLITICAS_POR_DEFECTO = RAIZ / "policies" / "gates"

# Archivo SARIF que deja cada herramienta -> nombre canónico de la herramienta en la entrada.
HERRAMIENTAS: dict[int, dict[str, str]] = {
    1: {
        "semgrep.sarif": "semgrep",
        "gitleaks.sarif": "gitleaks",
        "trivy-fs.sarif": "trivy fs",
        "trivy-config.sarif": "trivy config",
        "hadolint.sarif": "hadolint",
    },
    2: {"spectral.sarif": "spectral", "conftest.sarif": "conftest"},
    3: {"trivy-image.sarif": "trivy image", "zap.sarif": "zap", "nuclei.sarif": "nuclei"},
}

# Fase del pipeline en la que actúa cada gate (para registrar sus hallazgos).
FASE_DEL_GATE = {1: 4, 2: 8, 3: 11}

_DAST = {"zap", "nuclei"}


class ErrorDecision(ErrorOPA):
    """No se pudo obtener la decisión de OPA."""


class Motivo(BaseModel):
    regla: str
    motivo: str
    huella: str | None = None


class Criterio(BaseModel):
    regla: str
    cumple: bool
    detalle: str


class DecisionGate(BaseModel):
    gate: int
    aprobado: bool
    bloqueantes: list[Motivo]
    advertencias: list[Motivo]
    criterios: list[Criterio]
    conteo: dict[str, int]
    justificacion: str


class EntradaGate(BaseModel):
    gate: int
    datos: dict[str, Any]
    hallazgos: list[Hallazgo]


def _leer_herramientas(gate: int, carpeta_sarif: Path) -> tuple[list[Hallazgo], list[dict]]:
    """Hallazgos de las herramientas del gate y su estado: ok, hallazgos o error (sin SARIF)."""
    hallazgos: list[Hallazgo] = []
    estados: list[dict] = []
    for archivo, nombre in HERRAMIENTAS[gate].items():
        ruta = carpeta_sarif / archivo
        if not ruta.is_file() or ruta.stat().st_size == 0:
            # Los scripts de los gates borran el SARIF de una herramienta que no terminó.
            estados.append({"nombre": nombre, "estado": "error"})
            continue
        try:
            propios = [h.model_copy(update={"herramienta": nombre}) for h in leer_sarif(ruta)]
        except ErrorSarif:
            estados.append({"nombre": nombre, "estado": "error"})
            continue
        hallazgos.extend(propios)
        estados.append({"nombre": nombre, "estado": "hallazgos" if propios else "ok"})
    return hallazgos, estados


def _sbom_valido(ruta: Path) -> bool:
    try:
        documento = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(documento, dict) and documento.get("bomFormat") == "CycloneDX"


def _resultado_pruebas(ruta: Path) -> dict[str, int] | None:
    """Totales del informe JSON de Jest (jest --json); None si no existe o no se puede leer."""
    try:
        informe = json.loads(ruta.read_text(encoding="utf-8"))
        return {"total": int(informe["numTotalTests"]), "fallidas": int(informe["numFailedTests"])}
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def construir_entrada(
    gate: int,
    salida: Path,
    carpeta_sarif: Path | None = None,
    compilacion_ok: bool = False,
) -> EntradaGate:
    """Arma la entrada de la política del gate con los artefactos que dejaron sus herramientas.

    `salida` es la carpeta de resultados del pipeline (salida/). Lo que falta se envía como
    ausente para que la política falle de forma segura.
    """
    if gate not in HERRAMIENTAS:
        raise ValueError(f"No existe el gate {gate}; los gates son 1, 2 y 3")
    sarif = carpeta_sarif or salida / "security" / "sarif"
    hallazgos, herramientas = _leer_herramientas(gate, sarif)
    datos: dict[str, Any] = {"herramientas": herramientas}

    if gate == 1:
        datos["hallazgos"] = [h.model_dump(mode="json") for h in hallazgos]
        datos["compilacion_ok"] = compilacion_ok
    elif gate == 2:
        datos["hallazgos"] = [h.model_dump(mode="json") for h in hallazgos]
        contrato = salida / "openapi" / "usuarios.json"
        datos["contrato_ok"] = contrato.is_file() and contrato.stat().st_size > 0
    else:
        datos["dast"] = [h.model_dump(mode="json") for h in hallazgos if h.herramienta in _DAST]
        datos["imagen"] = [
            h.model_dump(mode="json") for h in hallazgos if h.herramienta not in _DAST
        ]
        datos["sbom_generado"] = _sbom_valido(salida / "sbom" / "sbom.json")
        pruebas = _resultado_pruebas(salida / "pruebas" / "jest.json")
        if pruebas is not None:
            datos["pruebas"] = pruebas
    return EntradaGate(gate=gate, datos=datos, hallazgos=hallazgos)


def evaluar(
    entrada: EntradaGate, politicas: Path = POLITICAS_POR_DEFECTO, opa: str | None = None
) -> DecisionGate:
    """Pide a OPA la decisión del gate (data.gates.gateN.decision)."""
    try:
        valor = consultar(f"data.gates.gate{entrada.gate}.decision", entrada.datos, politicas, opa)
    except ErrorOPA as error:
        raise ErrorDecision(str(error)) from error
    return DecisionGate.model_validate(valor)


def resumen_markdown(decision: DecisionGate) -> str:
    estado = "aprobado" if decision.aprobado else "rechazado"
    lineas = [
        f"### Decisión OPA del Gate {decision.gate}: {estado}",
        "",
        decision.justificacion,
        "",
        "| Criterio | Cumple | Detalle |",
        "|---|---|---|",
        *[
            f"| `{c.regla}` | {'sí' if c.cumple else '**no**'} | {c.detalle} |"
            for c in decision.criterios
        ],
    ]
    if decision.bloqueantes:
        lineas += [
            "",
            "Bloqueantes:",
            *[f"- `{b.regla}`: {b.motivo}" for b in decision.bloqueantes],
        ]
    if decision.advertencias:
        lineas += ["", f"Advertencias: {len(decision.advertencias)} (no bloquean)."]
    return "\n".join(lineas) + "\n"
