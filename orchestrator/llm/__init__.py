"""Adaptador de proveedores de LLM, con caché, respaldo entre proveedores y medición del uso."""

from orchestrator.llm.base import (
    ErrorLimiteLLM,
    ErrorLLM,
    ErrorProveedorLLM,
    ErrorSalidaEstructurada,
    Nivel,
    ProveedorLLM,
    UsoLLM,
)
from orchestrator.llm.cache import ProveedorConCache
from orchestrator.llm.cadena import ProveedorEnCadena
from orchestrator.llm.fabrica import (
    PROVEEDORES,
    crear_adaptador,
    crear_proveedor,
    describir_uso,
    uso_por_proveedor,
)

__all__ = [
    "PROVEEDORES",
    "ErrorLLM",
    "ErrorLimiteLLM",
    "ErrorProveedorLLM",
    "ErrorSalidaEstructurada",
    "Nivel",
    "ProveedorConCache",
    "ProveedorEnCadena",
    "ProveedorLLM",
    "UsoLLM",
    "crear_adaptador",
    "crear_proveedor",
    "describir_uso",
    "uso_por_proveedor",
]
