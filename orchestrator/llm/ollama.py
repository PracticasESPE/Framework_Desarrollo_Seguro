"""Adaptador de modelos abiertos locales servidos con Ollama (opción sin coste)."""

from typing import Any

import ollama

from orchestrator.llm.base import ErrorProveedorLLM, Nivel, ProveedorBase, T

MODELOS_POR_DEFECTO: dict[Nivel, str] = {
    "rapido": "llama3.1",
    "razonamiento": "qwen2.5-coder",
}


class ProveedorOllama(ProveedorBase):
    nombre = "ollama"

    def __init__(
        self,
        host: str | None = None,
        modelos: dict[Nivel, str] | None = None,
        max_intentos: int = 3,
        temperatura: float = 0.1,
        cliente: Any | None = None,
    ) -> None:
        super().__init__(modelos or dict(MODELOS_POR_DEFECTO), max_intentos)
        self.temperatura = temperatura
        self._cliente = cliente or ollama.Client(host=host)

    def _invocar(self, prompt: str, esquema: type[T], modelo: str, sistema: str | None) -> T | str:
        mensajes: list[dict[str, str]] = []
        if sistema:
            mensajes.append({"role": "system", "content": sistema})
        mensajes.append({"role": "user", "content": prompt})

        try:
            respuesta = self._cliente.chat(
                model=modelo,
                messages=mensajes,
                format=esquema.model_json_schema(),
                options={"temperature": self.temperatura},
            )
        except ollama.ResponseError as error:
            raise ErrorProveedorLLM(f"ollama: {error.error}") from error
        except ConnectionError as error:
            raise ErrorProveedorLLM("ollama: no se pudo conectar con el servidor local") from error

        contenido = respuesta.message.content
        if not contenido:
            raise ErrorProveedorLLM("ollama: la respuesta llegó vacía")
        return contenido
