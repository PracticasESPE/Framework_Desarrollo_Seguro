"""Ingesta del documento de requisitos (fase 1)."""

from orchestrator.ingest.extraccion import (
    DocumentoExtraido,
    ErrorExtraccion,
    extraer_markdown,
    limpiar_markdown,
)
from orchestrator.ingest.normalizacion import (
    TextoNormalizado,
    UnidadTexto,
    normalizar_texto,
    segmentar,
)
from orchestrator.ingest.requisito import (
    ClasificacionRequisito,
    DocumentoOrigen,
    ModeloRequisitos,
    Requisito,
    construir_requisitos,
)

__all__ = [
    "ClasificacionRequisito",
    "DocumentoExtraido",
    "DocumentoOrigen",
    "ErrorExtraccion",
    "ModeloRequisitos",
    "Requisito",
    "TextoNormalizado",
    "UnidadTexto",
    "construir_requisitos",
    "extraer_markdown",
    "limpiar_markdown",
    "normalizar_texto",
    "segmentar",
]
