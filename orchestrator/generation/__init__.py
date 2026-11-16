"""Fase 3: generación de la estructura interna de cada microservicio."""

from orchestrator.generation.plantilla import (
    RUTA_PLANTILLA,
    ErrorPlantilla,
    generar_servicio,
    leer_especificacion,
)

__all__ = ["RUTA_PLANTILLA", "ErrorPlantilla", "generar_servicio", "leer_especificacion"]
