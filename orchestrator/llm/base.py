"""Interfaz común de los proveedores de LLM.

Las fases del motor dependen solo de `ProveedorLLM`; nunca llaman a un SDK directamente.
Así se puede cambiar de proveedor por configuración y comparar modelos en la evaluación.
"""

from abc import ABC, abstractmethod
from typing import Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

Nivel = Literal["rapido", "razonamiento"]
NIVELES: tuple[Nivel, ...] = ("rapido", "razonamiento")


class ErrorLLM(Exception):
    """Error base de la capa de LLM."""


class ErrorProveedorLLM(ErrorLLM):
    """El proveedor no pudo atender la petición (red, autenticación, límites, rechazo)."""


class ErrorSalidaEstructurada(ErrorLLM):
    """La respuesta no cumplió el esquema tras agotar los intentos."""


@runtime_checkable
class ProveedorLLM(Protocol):
    def generar_estructurado(
        self,
        prompt: str,
        esquema: type[T],
        nivel: Nivel = "rapido",
        sistema: str | None = None,
    ) -> T:
        """Devuelve una instancia validada del esquema o lanza error."""
        ...


class ProveedorBase(ABC):
    """Lógica compartida: selección de modelo por nivel, validación y reintentos."""

    nombre: str

    def __init__(self, modelos: dict[Nivel, str], max_intentos: int = 3) -> None:
        faltantes = [nivel for nivel in NIVELES if not modelos.get(nivel)]
        if faltantes:
            raise ValueError(f"Falta el modelo para el nivel: {', '.join(faltantes)}")
        if max_intentos < 1:
            raise ValueError("max_intentos debe ser al menos 1")
        self.modelos = modelos
        self.max_intentos = max_intentos

    def generar_estructurado(
        self,
        prompt: str,
        esquema: type[T],
        nivel: Nivel = "rapido",
        sistema: str | None = None,
    ) -> T:
        if nivel not in self.modelos:
            raise ValueError(f"Nivel desconocido: {nivel!r}")
        modelo = self.modelos[nivel]

        ultimo_error: Exception | None = None
        for _ in range(self.max_intentos):
            respuesta = self._invocar(prompt, esquema, modelo, sistema)
            try:
                if isinstance(respuesta, esquema):
                    return respuesta
                return esquema.model_validate_json(respuesta)
            except ValidationError as error:
                ultimo_error = error

        raise ErrorSalidaEstructurada(
            f"{self.nombre}: la respuesta no cumplió el esquema {esquema.__name__} "
            f"tras {self.max_intentos} intento(s)"
        ) from ultimo_error

    @abstractmethod
    def _invocar(self, prompt: str, esquema: type[T], modelo: str, sistema: str | None) -> T | str:
        """Llama al proveedor y devuelve el JSON en texto o la instancia ya validada."""
