"""Adaptador de Groq (modelos abiertos en la nube) sobre su API compatible con OpenAI."""

from typing import Any

import openai

from orchestrator.llm.base import ErrorProveedorLLM, Nivel, ProveedorBase, T

URL_BASE = "https://api.groq.com/openai/v1"

# Modelos de Groq que admiten salida estructurada con esquema JSON.
MODELOS_POR_DEFECTO: dict[Nivel, str] = {
    "rapido": "openai/gpt-oss-20b",
    "razonamiento": "openai/gpt-oss-120b",
}


class ProveedorGroq(ProveedorBase):
    nombre = "groq"

    def __init__(
        self,
        api_key: str | None = None,
        modelos: dict[Nivel, str] | None = None,
        max_intentos: int = 3,
        temperatura: float = 0.1,
        url_base: str = URL_BASE,
        cliente: Any | None = None,
    ) -> None:
        super().__init__(modelos or dict(MODELOS_POR_DEFECTO), max_intentos)
        self.temperatura = temperatura
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
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": esquema.__name__,
                        "schema": esquema.model_json_schema(),
                    },
                },
            )
        except openai.RateLimitError as error:
            raise ErrorProveedorLLM("groq: límite de peticiones alcanzado") from error
        except openai.APIStatusError as error:
            raise ErrorProveedorLLM(
                f"groq: error {error.status_code} de la API: {error.message}"
            ) from error
        except openai.APIConnectionError as error:
            raise ErrorProveedorLLM("groq: no se pudo conectar con la API") from error

        contenido = respuesta.choices[0].message.content if respuesta.choices else None
        if not contenido:
            raise ErrorProveedorLLM("groq: la respuesta llegó vacía")
        return contenido
