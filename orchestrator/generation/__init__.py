"""Fase 3: generación de la estructura interna de cada microservicio."""

from orchestrator.generation.logica import (
    ErrorLogica,
    IntentoLogica,
    ResultadoLogica,
    generar_logica,
    preparar,
    problemas_del_codigo,
)
from orchestrator.generation.plantilla import (
    RUTA_PLANTILLA,
    ErrorPlantilla,
    generar_servicio,
    leer_especificacion,
)

__all__ = [
    "RUTA_PLANTILLA",
    "ErrorLogica",
    "ErrorPlantilla",
    "IntentoLogica",
    "ResultadoLogica",
    "generar_logica",
    "generar_servicio",
    "leer_especificacion",
    "preparar",
    "problemas_del_codigo",
]
