"""Modelo común de hallazgos de seguridad.

Todas las herramientas de análisis (SAST, SCA, secretos, contenedores, DAST) se normalizan
a esta estructura, que es la que reciben las políticas de OPA y la que se registra en Neo4j.
"""

import hashlib
from collections import Counter
from enum import StrEnum

from pydantic import BaseModel, Field


class Severidad(StrEnum):
    CRITICA = "critica"
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"
    INFO = "info"


ORDEN_SEVERIDAD: tuple[Severidad, ...] = (
    Severidad.CRITICA,
    Severidad.ALTA,
    Severidad.MEDIA,
    Severidad.BAJA,
    Severidad.INFO,
)


class Hallazgo(BaseModel):
    herramienta: str
    regla_id: str
    mensaje: str
    severidad: Severidad
    archivo: str | None = None
    linea_inicio: int | None = Field(default=None, ge=1)
    linea_fin: int | None = Field(default=None, ge=1)
    cwe: list[str] = []
    # Identifica el mismo hallazgo entre iteraciones para medir correcciones y regresiones.
    huella: str


def calcular_huella(herramienta: str, regla_id: str, archivo: str | None, contexto: str) -> str:
    """Huella propia para las herramientas que no publican una en su SARIF."""
    base = "|".join((herramienta.lower(), regla_id, archivo or "", contexto.strip()))
    return hashlib.sha256(base.encode("utf-8")).hexdigest()[:32]


def contar_por_severidad(hallazgos: list[Hallazgo]) -> dict[str, int]:
    conteo = Counter(h.severidad for h in hallazgos)
    return {severidad.value: conteo.get(severidad, 0) for severidad in ORDEN_SEVERIDAD}
