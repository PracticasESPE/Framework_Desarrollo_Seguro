"""Ingesta del documento de requisitos (fase 1)."""

from orchestrator.ingest.extraccion import (
    DocumentoExtraido,
    ErrorExtraccion,
    extraer_markdown,
    limpiar_markdown,
)

__all__ = ["DocumentoExtraido", "ErrorExtraccion", "extraer_markdown", "limpiar_markdown"]
