"""Ciclo LLM ↔ OPA de la fase 2 (plan técnico 7.2, pasos 1 a 3).

    LLM propone ──► OPA valida ──► ¿aprobada? ── sí ──► arquitectura.json
         ▲                              │
         └──── motivos del rechazo ◄─── no   (como mucho 3 intentos)

Si OPA no aprueba ninguna propuesta, el ciclo termina sin arquitectura aprobada y queda para
revisión humana (riesgo de la planificación del sprint 3). Cada intento se registra con los
motivos que recibió el LLM, su propuesta y la decisión de OPA: es la evidencia del ciclo y la
entrada de los nodos Decision de Neo4j.

El ciclo puede empezar por una arquitectura existente (`inicial`), por ejemplo una corregida a
mano: se valida primero y el LLM solo interviene si OPA la rechaza.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from orchestrator.architecture.modelo import Arquitectura
from orchestrator.architecture.propuesta import proponer_arquitectura
from orchestrator.architecture.validacion import DecisionArquitectura, validar_arquitectura
from orchestrator.ingest.requisito import DocumentoOrigen, ModeloRequisitos
from orchestrator.llm.base import Nivel, ProveedorLLM

INTENTOS = 3


class IntentoArquitectura(BaseModel):
    numero: int
    fecha: datetime
    origen: str = Field(description="«llm» si la propuso el LLM, «inicial» si ya existía")
    retroalimentacion: list[str] = Field(
        description="Motivos del rechazo anterior que recibió el LLM para esta propuesta"
    )
    arquitectura: Arquitectura
    decision: DecisionArquitectura


class ResultadoCiclo(BaseModel):
    """Registro de intentos del ciclo: se guarda como <nombre>.intentos.json."""

    documento: DocumentoOrigen
    aprobada: bool
    maximo_intentos: int
    intentos: list[IntentoArquitectura]

    @property
    def final(self) -> IntentoArquitectura:
        return self.intentos[-1]


def ciclo_llm_opa(
    modelo: ModeloRequisitos,
    llm: ProveedorLLM,
    intentos: int = INTENTOS,
    nivel: Nivel = "razonamiento",
    inicial: Arquitectura | None = None,
    al_intento: Callable[[IntentoArquitectura], None] | None = None,
    validar: Callable[[Arquitectura], DecisionArquitectura] = validar_arquitectura,
    proponer: Callable[..., Arquitectura] = proponer_arquitectura,
) -> ResultadoCiclo:
    """Propone y valida hasta que OPA apruebe o se agoten los intentos.

    Un error del LLM o de OPA se propaga: el ciclo no puede decidir sin ellos.
    """
    if intentos < 1:
        raise ValueError("intentos debe ser al menos 1")
    historial: list[IntentoArquitectura] = []
    motivos: list[str] = []
    for numero in range(1, intentos + 1):
        if numero == 1 and inicial is not None:
            arquitectura, origen = inicial, "inicial"
        else:
            arquitectura = proponer(modelo, llm, nivel=nivel, retroalimentacion=motivos or None)
            origen = "llm"
        decision = validar(arquitectura)
        intento = IntentoArquitectura(
            numero=numero,
            fecha=datetime.now(UTC),
            origen=origen,
            retroalimentacion=motivos,
            arquitectura=arquitectura,
            decision=decision,
        )
        historial.append(intento)
        if al_intento is not None:
            al_intento(intento)
        if decision.aprobado:
            break
        # Se acumulan los motivos de todos los rechazos: con solo el último, el LLM puede volver
        # a introducir un problema que ya había corregido.
        motivos = motivos + [m for m in decision.retroalimentacion() if m not in motivos]
    return ResultadoCiclo(
        documento=modelo.documento,
        aprobada=historial[-1].decision.aprobado,
        maximo_intentos=intentos,
        intentos=historial,
    )
