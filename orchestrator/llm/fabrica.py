"""Selección del proveedor de LLM a partir de la configuración.

`crear_proveedor` monta, según `.env`:

    LLM_PROVIDER  ──►  caché (LLM_CACHE)  ─┐
    LLM_RESPALDO  ──►  caché (LLM_CACHE)  ─┴─► cadena de respaldo (solo si hay respaldo)

Cada proveedor tiene su propia caché, así que una respuesta de Gemini nunca se sirve como si fuera
de Groq.
"""

import json
import logging
import os
from dataclasses import asdict
from pathlib import Path

from pydantic import SecretStr

from orchestrator.config import PROVEEDORES_LLM, Configuracion, obtener_configuracion
from orchestrator.llm.base import ErrorLLM, Nivel, ProveedorLLM, UsoLLM
from orchestrator.llm.cache import ProveedorConCache
from orchestrator.llm.cadena import ProveedorEnCadena

PROVEEDORES = PROVEEDORES_LLM

log = logging.getLogger(__name__)


class ErrorClaveFaltante(ErrorLLM):
    """El proveedor elegido no tiene su clave en el entorno ni en .env."""


def _clave(valor: SecretStr | None, variable: str) -> str:
    if valor is None:
        raise ErrorClaveFaltante(f"Falta la variable {variable} en el entorno o en .env")
    return valor.get_secret_value()


def _modelos(rapido: str | None, razonamiento: str | None) -> dict[Nivel, str] | None:
    """Devuelve los modelos configurados o None para usar los del adaptador."""
    if rapido is None and razonamiento is None:
        return None
    if rapido is None or razonamiento is None:
        raise ErrorLLM(
            "Hay que definir los dos niveles: LLM_MODELO_RAPIDO y LLM_MODELO_RAZONAMIENTO"
        )
    return {"rapido": rapido, "razonamiento": razonamiento}


def nombres_de_respaldo(config: Configuracion, principal: str) -> list[str]:
    """Proveedores de LLM_RESPALDO, sin repetir y sin el principal."""
    nombres: list[str] = []
    for nombre in (n.strip().lower() for n in config.llm_respaldo.split(",")):
        if not nombre or nombre == principal or nombre in nombres:
            continue
        if nombre not in PROVEEDORES:
            # El valor no se repite en el mensaje: si alguien pegó ahí una clave, se filtraría
            # en la terminal, en los logs o en el dashboard.
            raise ErrorLLM(
                "LLM_RESPALDO solo admite nombres de proveedor separados por comas "
                f"({', '.join(PROVEEDORES)}) y tiene otro valor. Las claves van en "
                "GEMINI_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY u OPENROUTER_API_KEY."
            )
        nombres.append(nombre)
    return nombres


def crear_proveedor(
    nombre: str | None = None, configuracion: Configuracion | None = None
) -> ProveedorLLM:
    """Proveedor principal con su caché y, si hay LLM_RESPALDO, la cadena de respaldo."""
    config = configuracion or obtener_configuracion()
    principal = (nombre or config.llm_provider).lower()
    nombres = [principal, *nombres_de_respaldo(config, principal)]

    proveedores: list[ProveedorLLM] = []
    for elegido in nombres:
        # Los modelos de LLM_MODELO_* son del principal: los de respaldo usan los suyos.
        try:
            proveedor = crear_adaptador(elegido, config, modelos_configurados=elegido == principal)
        except ErrorClaveFaltante:
            if elegido == principal:
                raise
            # Un respaldo sin clave no entra en la cadena: así LLM_RESPALDO puede nombrar uno de
            # pago (claude) que solo se usa en las máquinas que tienen su clave.
            log.info("Respaldo %s sin clave: no entra en la cadena", elegido)
            continue
        if config.llm_cache:
            proveedor = ProveedorConCache(proveedor, config.llm_cache_dir)
        proveedores.append(proveedor)
    return proveedores[0] if len(proveedores) == 1 else ProveedorEnCadena(proveedores)


def crear_adaptador(
    nombre: str, config: Configuracion, modelos_configurados: bool = True
) -> ProveedorLLM:
    """El adaptador de un proveedor, sin caché ni respaldo."""
    elegido = nombre.lower()
    modelos = (
        _modelos(config.llm_modelo_rapido, config.llm_modelo_razonamiento)
        if modelos_configurados
        else None
    )
    intentos = config.llm_max_intentos

    # Cada SDK se importa solo cuando se elige su proveedor.
    if elegido == "gemini":
        from orchestrator.llm.gemini import ProveedorGemini

        return ProveedorGemini(
            api_key=_clave(config.gemini_api_key, "GEMINI_API_KEY"),
            modelos=modelos,
            max_intentos=intentos,
        )
    if elegido == "groq":
        from orchestrator.llm.groq import ProveedorGroq

        return ProveedorGroq(
            api_key=_clave(config.groq_api_key, "GROQ_API_KEY"),
            modelos=modelos,
            max_intentos=intentos,
            esfuerzo_razonamiento=config.llm_esfuerzo_razonamiento,
        )
    if elegido == "openrouter":
        from orchestrator.llm.openrouter import ProveedorOpenRouter

        # Sus modelos propios valen siempre, sea principal o respaldo; LLM_MODELO_* los reemplaza
        # solo si es el principal.
        propios = (
            _modelos(config.openrouter_modelo_rapido, config.openrouter_modelo_razonamiento)
            if config.openrouter_modelo_rapido or config.openrouter_modelo_razonamiento
            else None
        )
        return ProveedorOpenRouter(
            api_key=_clave(config.openrouter_api_key, "OPENROUTER_API_KEY"),
            modelos=modelos or propios,
            max_intentos=intentos,
        )
    if elegido == "claude":
        from orchestrator.llm.claude import ProveedorClaude

        return ProveedorClaude(
            api_key=_clave(config.anthropic_api_key, "ANTHROPIC_API_KEY"),
            modelos=modelos,
            max_intentos=intentos,
        )
    if elegido == "ollama":
        from orchestrator.llm.ollama import ProveedorOllama

        return ProveedorOllama(host=config.ollama_host, modelos=modelos, max_intentos=intentos)

    # Sin repetir el valor recibido, por si es una clave pegada en la variable equivocada.
    raise ErrorLLM(
        f"Proveedor de LLM desconocido en LLM_PROVIDER o --proveedor. "
        f"Opciones: {', '.join(PROVEEDORES)}"
    )


def uso_por_proveedor(proveedor: object) -> dict[str, UsoLLM]:
    """Llamadas, respuestas desde la caché y tokens de cada proveedor que intervino."""
    if isinstance(proveedor, ProveedorEnCadena):
        total: dict[str, UsoLLM] = {}
        for interno in proveedor.proveedores:
            for nombre, uso in uso_por_proveedor(interno).items():
                total.setdefault(nombre, UsoLLM()).sumar(uso)
        return total
    nombre = getattr(proveedor, "nombre", type(proveedor).__name__)
    if isinstance(proveedor, ProveedorConCache):
        return {nombre: proveedor.uso_total()}
    uso = getattr(proveedor, "uso", None)
    return {nombre: uso if isinstance(uso, UsoLLM) else UsoLLM()}


def uso_en_json(proveedor: object) -> dict[str, dict[str, int]]:
    """El uso de cada proveedor que intervino, para guardarlo en los resúmenes."""
    return {
        nombre: asdict(uso)
        for nombre, uso in uso_por_proveedor(proveedor).items()
        if uso.llamadas or uso.desde_cache
    }


def sumar_usos(*usos: dict[str, dict[str, int]]) -> dict[str, dict[str, int]]:
    """Suma, proveedor por proveedor, usos guardados con `uso_en_json`."""
    total: dict[str, dict[str, int]] = {}
    for uso in usos:
        for nombre, valores in uso.items():
            acumulado = total.setdefault(nombre, {})
            for clave, valor in valores.items():
                acumulado[clave] = acumulado.get(clave, 0) + valor
    return total


# Si está definida, cada comando que usa el LLM añade ahí una línea JSON con su uso. La
# evaluación (evaluation/fases_1_4.py) la usa para medir los tokens de cada fase.
VARIABLE_REGISTRO_USO = "FRAMEWORK_REGISTRO_USO"


def registrar_uso(proveedor: object, paso: str) -> None:
    ruta = os.environ.get(VARIABLE_REGISTRO_USO)
    if not ruta:
        return
    linea = json.dumps({"paso": paso, "uso": uso_en_json(proveedor)}, ensure_ascii=False)
    with Path(ruta).open("a", encoding="utf-8") as registro:
        registro.write(linea + "\n")


def describir_uso(proveedor: object) -> str:
    """Una línea por proveedor con uso, p. ej. «groq: 11 llamadas, 3 desde caché, 24 310 tokens»."""
    partes = []
    for nombre, uso in uso_por_proveedor(proveedor).items():
        if not uso.llamadas and not uso.desde_cache:
            continue
        tokens = uso.tokens_entrada + uso.tokens_salida
        partes.append(
            f"{nombre}: {uso.llamadas} llamadas al proveedor, {uso.desde_cache} desde caché, "
            f"{tokens} tokens ({uso.tokens_entrada} de entrada y {uso.tokens_salida} de salida)"
        )
    return "; ".join(partes) or "sin llamadas al LLM"
