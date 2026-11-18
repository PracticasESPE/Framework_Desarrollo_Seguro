"""Validación de la propuesta arquitectónica con OPA (fase 2, plan técnico 7.2, paso 2).

El motor arma la entrada con arquitectura.json y los patrones de la base de conocimiento
(knowledge_base/patrones) y pide a las políticas de policies/arquitectura la decisión: si la
propuesta cumple las reglas arquitectónicas y qué patrones aplican, con su justificación. Si OPA
la rechaza, los motivos de los bloqueantes son la retroalimentación para el LLM
(`proponer_arquitectura(..., retroalimentacion=...)`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from orchestrator.architecture.modelo import Arquitectura
from orchestrator.knowledge.base_conocimiento import BaseConocimiento, cargar_base_conocimiento
from orchestrator.opa import consultar

RAIZ = Path(__file__).resolve().parents[2]
POLITICAS_POR_DEFECTO = RAIZ / "policies" / "arquitectura"
CONSULTA = "data.arquitectura.decision"


class Motivo(BaseModel):
    regla: str
    motivo: str


class Criterio(BaseModel):
    regla: str
    cumple: bool
    detalle: str


class Rasgo(BaseModel):
    etiqueta: str
    motivo: str


class PatronInferido(BaseModel):
    id: str
    patron: str
    implementacion: str
    controles: list[str]
    cwe: list[str]
    por: list[str]
    motivo: str


class DecisionArquitectura(BaseModel):
    aprobado: bool
    bloqueantes: list[Motivo]
    advertencias: list[Motivo]
    criterios: list[Criterio]
    rasgos: list[Rasgo]
    patrones: list[PatronInferido]
    justificacion: str

    def retroalimentacion(self) -> list[str]:
        """Motivos del rechazo, para que el LLM corrija la propuesta."""
        return [b.motivo for b in self.bloqueantes]


def construir_entrada(
    arquitectura: Arquitectura, base: BaseConocimiento | None = None
) -> dict[str, Any]:
    base = base or cargar_base_conocimiento()
    return {
        "arquitectura": arquitectura.model_dump(mode="json"),
        "patrones": [p.model_dump(mode="json", exclude_none=True) for p in base.patrones],
    }


def validar_arquitectura(
    arquitectura: Arquitectura,
    base: BaseConocimiento | None = None,
    politicas: Path = POLITICAS_POR_DEFECTO,
    opa: str | None = None,
) -> DecisionArquitectura:
    """Pide a OPA la decisión sobre la arquitectura. Lanza ErrorOPA si no puede obtenerla."""
    valor = consultar(CONSULTA, construir_entrada(arquitectura, base), politicas, opa)
    decision = DecisionArquitectura.model_validate(valor)
    # OPA devuelve los conjuntos sin orden fijo: se ordenan para que el resultado sea estable.
    decision.bloqueantes.sort(key=lambda m: (m.regla, m.motivo))
    decision.advertencias.sort(key=lambda m: (m.regla, m.motivo))
    decision.rasgos.sort(key=lambda r: r.etiqueta)
    decision.patrones.sort(key=lambda p: p.id)
    return decision
