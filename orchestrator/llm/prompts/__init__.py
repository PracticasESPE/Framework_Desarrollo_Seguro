"""Prompts de generación de la fase 3, con contexto de seguridad recuperado por GraphRAG."""

from orchestrator.llm.prompts.comun import Prompt, bloque, neutralizar, nuevo_codigo
from orchestrator.llm.prompts.contexto import (
    PREGUNTA_BASE,
    PREGUNTAS_POR_ETIQUETA,
    combinar,
    contexto_de_seguridad,
    contexto_vacio,
    preguntas_de_seguridad,
)
from orchestrator.llm.prompts.especificacion import (
    Campo,
    Entidad,
    EntidadesPropuestas,
    EspecificacionServicio,
    construir_especificacion,
    descripcion_de,
    esquema_de_entidades,
    identificador_de_entidad,
    prompt_especificacion,
)
from orchestrator.llm.prompts.logica import LogicaEntidad, clase_de, prompt_logica

__all__ = [
    "PREGUNTAS_POR_ETIQUETA",
    "PREGUNTA_BASE",
    "Campo",
    "Entidad",
    "EntidadesPropuestas",
    "EspecificacionServicio",
    "LogicaEntidad",
    "Prompt",
    "bloque",
    "clase_de",
    "combinar",
    "construir_especificacion",
    "contexto_de_seguridad",
    "contexto_vacio",
    "descripcion_de",
    "esquema_de_entidades",
    "identificador_de_entidad",
    "neutralizar",
    "nuevo_codigo",
    "preguntas_de_seguridad",
    "prompt_especificacion",
    "prompt_logica",
]
