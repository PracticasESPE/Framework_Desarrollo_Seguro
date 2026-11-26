"""Adaptador de OpenRouter sobre su API compatible con OpenAI.

OpenRouter da acceso a muchos modelos con una sola clave. Los que terminan en `:free` no cuestan
nada, pero tienen límites bajos: 20 peticiones por minuto y 50 al día (1000 al día si la cuenta
compró alguna vez 10 USD de créditos). Por eso sirve como respaldo de Groq y Gemini, no como
proveedor principal de un documento grande.

Los modelos gratuitos cambian a menudo: los de por defecto son los que admitían salida
estructurada en noviembre de 2026, y se cambian con OPENROUTER_MODELO_RAPIDO y
OPENROUTER_MODELO_RAZONAMIENTO. Algunos solo responden si en la cuenta se permiten los endpoints
gratuitos que pueden guardar los prompts (Settings > Privacy de OpenRouter).
"""

import time
from typing import Any

import openai

from orchestrator.llm.base import ErrorProveedorLLM, Nivel, ProveedorBase, T, error_de_limite

URL_BASE = "https://openrouter.ai/api/v1"

MODELOS_POR_DEFECTO: dict[Nivel, str] = {
    "rapido": "nvidia/nemotron-3.5-super-vl:free",
    "razonamiento": "baidu/ernie-5.5-flash-preview:free",
}
# Los modelos que razonan cuentan ese razonamiento como salida: con poco margen, el JSON se corta.
MAX_TOKENS_SALIDA = 16384


class ProveedorOpenRouter(ProveedorBase):
    """Pide la salida con esquema JSON y solo a los proveedores de OpenRouter que la admiten
    (`provider.require_parameters`): los demás ignorarían el esquema."""

    nombre = "openrouter"

    def __init__(
        self,
        api_key: str | None = None,
        modelos: dict[Nivel, str] | None = None,
        max_intentos: int = 3,
        temperatura: float = 0.1,
        url_base: str = URL_BASE,
        cliente: Any | None = None,
        reloj: Any = time.time,
    ) -> None:
        super().__init__(modelos or dict(MODELOS_POR_DEFECTO), max_intentos)
        self.temperatura = temperatura
        self._reloj = reloj
        self._cliente = cliente or openai.OpenAI(api_key=api_key, base_url=url_base)

    def _invocar(self, prompt: str, esquema: type[T], modelo: str, sistema: str | None) -> T | str:
        mensajes: list[dict[str, str]] = []
        if sistema:
            mensajes.append({"role": "system", "content": sistema})
        mensajes.append({"role": "user", "content": prompt})

        try:
            respuesta = self._cliente.chat.completions.create(
                model=modelo,
                messages=mensajes,
                temperature=self.temperatura,
                max_completion_tokens=MAX_TOKENS_SALIDA,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": esquema.__name__,
                        "schema": esquema.model_json_schema(),
                    },
                },
                extra_body={"provider": {"require_parameters": True}},
            )
        except openai.RateLimitError as error:
            raise self._limite(error) from error
        except openai.AuthenticationError as error:
            raise ErrorProveedorLLM(
                "openrouter: la clave OPENROUTER_API_KEY no es válida (401)"
            ) from error
        except openai.APIStatusError as error:
            raise ErrorProveedorLLM(
                f"openrouter: error {error.status_code} de la API: {error.message}"
            ) from error
        except openai.APIConnectionError as error:
            raise ErrorProveedorLLM("openrouter: no se pudo conectar con la API") from error

        uso = getattr(respuesta, "usage", None)
        self._anotar_uso(
            getattr(uso, "prompt_tokens", None), getattr(uso, "completion_tokens", None)
        )
        contenido = respuesta.choices[0].message.content if respuesta.choices else None
        if not contenido:
            raise ErrorProveedorLLM("openrouter: la respuesta llegó vacía")
        return contenido

    def _limite(self, error: openai.RateLimitError) -> Exception:
        """El 429 de OpenRouter: «free-models-per-day» es la cuota del día, y la cabecera
        X-RateLimit-Reset (milisegundos desde 1970) dice cuándo se renueva."""
        cabeceras = error.response.headers
        espera = cabeceras.get("retry-after")
        reinicio = cabeceras.get("x-ratelimit-reset")
        if espera is None and reinicio:
            try:
                espera = str(max(int(reinicio) / 1000 - self._reloj(), 0.0))
            except ValueError:
                espera = None
        detalle = error.message.replace("per-day", "per day")
        return error_de_limite("openrouter", detalle, espera)
