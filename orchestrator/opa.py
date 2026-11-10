"""Consulta a Open Policy Agent con `opa eval`: la usan los gates y la validación arquitectónica."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


class ErrorOPA(Exception):
    """No se pudo obtener el resultado de OPA."""


def consultar(
    consulta: str, entrada: dict[str, Any], politicas: Path, opa: str | None = None
) -> Any:
    """Evalúa `consulta` (p. ej. data.gates.gate1.decision) con la entrada y las políticas dadas."""
    ejecutable = opa or shutil.which("opa")
    if ejecutable is None:
        raise ErrorOPA("No se encontró OPA. Instálalo (winget install open-policy-agent.opa)")
    try:
        proceso = subprocess.run(
            [
                ejecutable,
                "eval",
                "--format",
                "json",
                "--data",
                str(politicas),
                "--stdin-input",
                consulta,
            ],
            input=json.dumps(entrada),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ErrorOPA(f"No se pudo ejecutar OPA: {error}") from error
    if proceso.returncode != 0:
        raise ErrorOPA(f"OPA falló al evaluar {consulta}: {proceso.stderr.strip()}")
    try:
        return json.loads(proceso.stdout)["result"][0]["expressions"][0]["value"]
    except (json.JSONDecodeError, KeyError, IndexError) as error:
        raise ErrorOPA(f"OPA no devolvió una decisión para {consulta}") from error
