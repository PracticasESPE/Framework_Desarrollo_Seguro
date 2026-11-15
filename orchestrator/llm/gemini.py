"""Adaptador de Gemini sobre el SDK oficial google-genai."""

import time
from collections.abc import Callable
from typing import Any

from google import genai
from google.genai import errors
from pydantic import BaseModel

from orchestrator.llm.base import ErrorProveedorLLM, Nivel, ProveedorBase, T, error_de_limite

# Errores del servidor que suelen pasar solos («high demand»): se reintenta tras estas esperas.
ERRORES_PASAJEROS = {500, 502, 503, 504}
ESPERAS_ERROR_PASAJERO_S = (3.0, 10.0)

MODELOS_POR_DEFECTO: dict[Nivel, str] = {
    "rapido": "gemini-3.5-flash-lite",
    "razonamiento": "gemini-3.8-flash",
}


def esquema_para_gemini(esquema: type[BaseModel]) -> dict[str, Any]:
    """JSON Schema del modelo sin `maxItems`.

    Gemini rechaza con un 400 sin detalle el `maxItems` de una lista de objetos (las
    clasificaciones de una sección). Los límites se siguen cumpliendo: ProveedorBase valida cada
    respuesta con Pydantic y reintenta si no cumple.
    """

    def limpiar(nodo: Any) -> Any:
        if isinstance(nodo, dict):
            return {k: limpiar(v) for k, v in nodo.items() if k != "maxItems"}
        if isinstance(nodo, list):
            return [limpiar(v) for v in nodo]
        return nodo

    return limpiar(esquema.model_json_schema())


class ProveedorGemini(ProveedorBase):
    nombre = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        modelos: dict[Nivel, str] | None = None,
        max_intentos: int = 3,
        temperatura: float = 0.1,
        cliente: Any | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(modelos or dict(MODELOS_POR_DEFECTO), max_intentos)
        self.temperatura = temperatura
        self._cliente = cliente or genai.Client(api_key=api_key)
        self._dormir = dormir

    def _generar(self, modelo: str, prompt: str, configuracion: dict[str, Any]) -> Any:
        """Llama a la API y reintenta los errores pasajeros del servidor (500, 502, 503 y 504).

        El SDK de Gemini, a diferencia del de Groq, no los reintenta. En la medición del 15/11
        devolvió «503: high demand» en dos de cada tres documentos, y la clasificación fallaba.
        """
        for espera in (*ESPERAS_ERROR_PASAJERO_S, None):
            try:
                return self._cliente.models.generate_content(
                    model=modelo, contents=prompt, config=configuracion
                )
            except errors.APIError as error:
                if error.code not in ERRORES_PASAJEROS or espera is None:
                    raise
                self._dormir(espera)
        raise AssertionError("inalcanzable")  # pragma: no cover

    def _invocar(self, prompt: str, esquema: type[T], modelo: str, sistema: str | None) -> T | str:
        configuracion: dict[str, Any] = {
            "response_mime_type": "application/json",
            # JSON Schema estándar y no `response_schema`: este no admite `additionalProperties`,
            # que Pydantic genera para los modelos con extra="forbid" (los de la clasificación).
            "response_json_schema": esquema_para_gemini(esquema),
            "temperature": self.temperatura,
            # No se usan herramientas; evita el aviso del SDK sobre llamadas automáticas.
            "automatic_function_calling": {"disable": True},
        }
        if sistema:
            configuracion["system_instruction"] = sistema

        try:
            respuesta = self._generar(modelo, prompt, configuracion)
        except errors.APIError as error:
            if error.code == 429:
                # Gemini indica la espera y si la cuota es diaria en el texto del error.
                raise error_de_limite("gemini", str(error.message or ""), None) from error
            raise ErrorProveedorLLM(
                f"gemini: error {error.code} de la API: {error.message}"
            ) from error

        uso = getattr(respuesta, "usage_metadata", None)
        salida = (getattr(uso, "candidates_token_count", None) or 0) + (
            getattr(uso, "thoughts_token_count", None) or 0
        )
        self._anotar_uso(getattr(uso, "prompt_token_count", None), salida)
        if not respuesta.text:
            raise ErrorProveedorLLM("gemini: la respuesta llegó vacía o fue bloqueada")
        return respuesta.text
