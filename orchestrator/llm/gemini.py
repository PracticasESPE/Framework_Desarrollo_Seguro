"""Adaptador de Gemini sobre el SDK oficial google-genai."""

from typing import Any

from google import genai
from google.genai import errors

from orchestrator.llm.base import ErrorProveedorLLM, Nivel, ProveedorBase, T

MODELOS_POR_DEFECTO: dict[Nivel, str] = {
    "rapido": "gemini-2.5-flash",
    "razonamiento": "gemini-2.5-pro",
}


class ProveedorGemini(ProveedorBase):
    nombre = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        modelos: dict[Nivel, str] | None = None,
        max_intentos: int = 3,
        temperatura: float = 0.1,
        cliente: Any | None = None,
    ) -> None:
        super().__init__(modelos or dict(MODELOS_POR_DEFECTO), max_intentos)
        self.temperatura = temperatura
        self._cliente = cliente or genai.Client(api_key=api_key)

    def _invocar(self, prompt: str, esquema: type[T], modelo: str, sistema: str | None) -> T | str:
        configuracion: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_schema": esquema,
            "temperature": self.temperatura,
        }
        if sistema:
            configuracion["system_instruction"] = sistema

        try:
            respuesta = self._cliente.models.generate_content(
                model=modelo, contents=prompt, config=configuracion
            )
        except errors.APIError as error:
            raise ErrorProveedorLLM(
                f"gemini: error {error.code} de la API: {error.message}"
            ) from error

        if not respuesta.text:
            raise ErrorProveedorLLM("gemini: la respuesta llegó vacía o fue bloqueada")
        return respuesta.text
