"""Fase 2: análisis y propuesta arquitectónica."""

from orchestrator.architecture.ciclo import (
    IntentoArquitectura,
    ResultadoCiclo,
    ciclo_llm_opa,
)
from orchestrator.architecture.modelo import (
    Arquitectura,
    DecisionPropuesta,
    Dependencia,
    PropuestaArquitectura,
    Servicio,
    ServicioPropuesto,
)
from orchestrator.architecture.propuesta import (
    ErrorPropuesta,
    construir_arquitectura,
    problemas_de_la_propuesta,
    proponer_arquitectura,
)
from orchestrator.architecture.validacion import DecisionArquitectura, validar_arquitectura

__all__ = [
    "Arquitectura",
    "DecisionArquitectura",
    "DecisionPropuesta",
    "Dependencia",
    "ErrorPropuesta",
    "IntentoArquitectura",
    "PropuestaArquitectura",
    "ResultadoCiclo",
    "Servicio",
    "ServicioPropuesto",
    "ciclo_llm_opa",
    "construir_arquitectura",
    "problemas_de_la_propuesta",
    "proponer_arquitectura",
    "validar_arquitectura",
]
