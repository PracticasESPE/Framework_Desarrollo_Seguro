"""Interfaz común de los proveedores de LLM.

Las fases del motor dependen solo de `ProveedorLLM`; nunca llaman a un SDK directamente.
Así se puede cambiar de proveedor por configuración y comparar modelos en la evaluación.
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

Nivel = Literal["rapido", "razonamiento"]
NIVELES: tuple[Nivel, ...] = ("rapido", "razonamiento")


class ErrorLLM(Exception):
    """Error base de la capa de LLM."""


class ErrorProveedorLLM(ErrorLLM):
    """El proveedor no pudo atender la petición (red, autenticación, límites, rechazo)."""


class ErrorLimiteLLM(ErrorProveedorLLM):
    """El proveedor rechazó la petición por su límite de uso (HTTP 429).

    `espera_s` es lo que pide esperar el proveedor (cabecera `retry-after`), si lo indica.
    `diario` distingue la cuota del día, que no se recupera en minutos, del límite por minuto.
    El mensaje siempre contiene «límite» o «cuota» y nunca el texto del proveedor, que puede
    incluir datos de la cuenta.
    """

    def __init__(self, mensaje: str, espera_s: float | None = None, diario: bool = False):
        super().__init__(mensaje)
        self.espera_s = espera_s
        self.diario = diario


def error_de_limite(proveedor: str, detalle: str, retry_after: str | None) -> ErrorLimiteLLM:
    """Construye el error a partir de la respuesta 429 del proveedor."""
    espera = _segundos(retry_after) if retry_after else _espera_en_texto(detalle)
    diario = bool(re.search(r"per day|\((?:TPD|RPD)\)|daily|PerDay", detalle, re.IGNORECASE))
    if diario:
        cuando = f"; se renueva en {_legible(espera)}" if espera is not None else ""
        return ErrorLimiteLLM(f"{proveedor}: cuota diaria agotada{cuando}", espera, diario=True)
    return ErrorLimiteLLM(f"{proveedor}: límite de peticiones alcanzado", espera)


def _segundos(valor: str) -> float | None:
    try:
        return max(float(valor), 0.0)
    except ValueError:
        return None


def _espera_en_texto(detalle: str) -> float | None:
    """«Please try again in 7m12.5s» (Groq) o «retry in 31s» (Gemini)."""
    encontrado = re.search(r"(?:try again|retry) in (?:(\d+)h)?(?:(\d+)m)?(?:([\d.]+)s)?", detalle)
    if not encontrado or not any(encontrado.groups()):
        return None
    horas, minutos, segundos = (float(g) if g else 0.0 for g in encontrado.groups())
    return horas * 3600 + minutos * 60 + segundos


def _legible(segundos: float) -> str:
    if segundos < 90:
        return f"{segundos:.0f} s"
    if segundos < 5400:
        return f"{segundos / 60:.0f} min"
    return f"{segundos / 3600:.1f} h"


class ErrorSalidaEstructurada(ErrorLLM):
    """La respuesta no cumplió el esquema tras agotar los intentos."""


@dataclass
class UsoLLM:
    """Lo que ha consumido un proveedor desde que se creó: para medir coste y cuota."""

    llamadas: int = 0
    desde_cache: int = 0
    tokens_entrada: int = 0
    tokens_salida: int = 0

    def sumar(self, otro: "UsoLLM") -> None:
        self.llamadas += otro.llamadas
        self.desde_cache += otro.desde_cache
        self.tokens_entrada += otro.tokens_entrada
        self.tokens_salida += otro.tokens_salida


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
        self.uso = UsoLLM()

    def _anotar_uso(self, entrada: int | None, salida: int | None) -> None:
        """Lo llaman los adaptadores con los tokens que informa el proveedor en cada llamada."""
        self.uso.llamadas += 1
        self.uso.tokens_entrada += entrada or 0
        self.uso.tokens_salida += salida or 0

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
