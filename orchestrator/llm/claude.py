"""Adaptador de Claude sobre el SDK oficial de Anthropic."""

from typing import Any

import anthropic

from orchestrator.llm.base import ErrorProveedorLLM, Nivel, ProveedorBase, T

MODELOS_POR_DEFECTO: dict[Nivel, str] = {
    "rapido": "claude-haiku-4-5",
    "razonamiento": "claude-opus-5-5",
}

# Modelos cuyos clasificadores de seguridad pueden rechazar una petición y que admiten
# que la API la reintente en otro modelo dentro de la misma llamada.
_PREFIJOS_CON_FALLBACK = ("claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-1")
_BETA_FALLBACK = "server-side-fallback-2026-07-01"

MAX_TOKENS = 16000


class ProveedorClaude(ProveedorBase):
    """No envía `temperature`: los modelos Opus actuales rechazan los parámetros de muestreo."""

    nombre = "claude"

    def __init__(
        self,
        api_key: str | None = None,
        modelos: dict[Nivel, str] | None = None,
        max_intentos: int = 3,
        usar_fallbacks: bool = True,
        cliente: Any | None = None,
    ) -> None:
        super().__init__(modelos or dict(MODELOS_POR_DEFECTO), max_intentos)
        self.usar_fallbacks = usar_fallbacks
        self._cliente = cliente or anthropic.Anthropic(api_key=api_key)

    def _invocar(self, prompt: str, esquema: type[T], modelo: str, sistema: str | None) -> T | str:
        parametros: dict[str, Any] = {
            "model": modelo,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
            "output_format": esquema,
        }
        if sistema:
            parametros["system"] = sistema

        try:
            if self.usar_fallbacks and modelo.startswith(_PREFIJOS_CON_FALLBACK):
                respuesta = self._cliente.beta.messages.parse(
                    betas=[_BETA_FALLBACK], fallbacks="default", **parametros
                )
            else:
                respuesta = self._cliente.messages.parse(**parametros)
        except anthropic.RateLimitError as error:
            raise ErrorProveedorLLM("claude: límite de peticiones alcanzado") from error
        except anthropic.APIStatusError as error:
            raise ErrorProveedorLLM(
                f"claude: error {error.status_code} de la API: {error.message}"
            ) from error
        except anthropic.APIConnectionError as error:
            raise ErrorProveedorLLM("claude: no se pudo conectar con la API") from error

        if respuesta.stop_reason == "refusal":
            raise ErrorProveedorLLM("claude: el modelo rechazó la petición")
        if respuesta.stop_reason == "max_tokens":
            raise ErrorProveedorLLM("claude: la respuesta se cortó por el límite de tokens")
        if respuesta.parsed_output is None:
            raise ErrorProveedorLLM("claude: la respuesta no contiene salida estructurada")
        return respuesta.parsed_output
