"""Fase 2: análisis y propuesta arquitectónica."""

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

__all__ = [
    "Arquitectura",
    "DecisionPropuesta",
    "Dependencia",
    "ErrorPropuesta",
    "PropuestaArquitectura",
    "Servicio",
    "ServicioPropuesto",
    "construir_arquitectura",
    "problemas_de_la_propuesta",
    "proponer_arquitectura",
]
