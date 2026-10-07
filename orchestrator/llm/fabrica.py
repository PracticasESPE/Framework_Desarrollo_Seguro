"""Selección del proveedor de LLM a partir de la configuración."""

from pydantic import SecretStr

from orchestrator.config import Configuracion, obtener_configuracion
from orchestrator.llm.base import ErrorLLM, Nivel, ProveedorLLM

PROVEEDORES: tuple[str, ...] = ("gemini", "groq", "claude", "ollama")


def _clave(valor: SecretStr | None, variable: str) -> str:
    if valor is None:
        raise ErrorLLM(f"Falta la variable {variable} en el entorno o en .env")
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


def crear_proveedor(
    nombre: str | None = None, configuracion: Configuracion | None = None
) -> ProveedorLLM:
    config = configuracion or obtener_configuracion()
    elegido = (nombre or config.llm_provider).lower()
    modelos = _modelos(config.llm_modelo_rapido, config.llm_modelo_razonamiento)
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

    raise ErrorLLM(f"Proveedor de LLM desconocido: {elegido!r}. Opciones: {', '.join(PROVEEDORES)}")
