"""Normalización del texto extraído y división en unidades de requisito (fase 1).

Recibe el Markdown de la extracción (orchestrator/ingest/extraccion.py) y entrega una lista de
unidades: cada punto de una lista, cada viñeta, cada párrafo y cada tabla, con su sección y una
ubicación estable como "3.1" (sección 3, punto 1). La clasificación con LLM trabaja después sobre
estas unidades, de una en una, sin reescribir su texto: así cada requisito conserva la frase
literal del documento y se puede trazar hasta él.

La limpieza es de forma y no cambia palabras:

- Unicode en forma NFC, para que una misma letra con tilde se compare igual venga de donde venga.
- Espacios raros (no separables, finos, tabuladores) pasan a un espacio normal, y se juntan los
  espacios seguidos.
- Se eliminan los caracteres invisibles: de ancho cero, guion opcional y los de control de
  dirección del texto. Pueden esconder instrucciones para el LLM o hacer que un texto se vea
  distinto de lo que es (técnica «Trojan Source», CVE-2021-42574). Se cuentan para avisar.

Funciona igual con el Markdown de Docling (PDF y DOCX) que con un TXT, donde los títulos no llevan
«#» y las tablas son filas separadas por «|».
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from pydantic import BaseModel

Bloque = Literal["parrafo", "lista", "vineta", "tabla"]

# Ancho cero, unión, guion opcional, marca de orden de bytes y controles de dirección del texto.
_INVISIBLES = re.compile("[\u00ad\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]")
_ESPACIOS = re.compile(r"[ \t\u00a0\u1680\u2000-\u200a\u202f\u205f\u3000]+")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

_TITULO_MD = re.compile(r"^(#{1,6})\s+(.*)$")
_NUMERADO = re.compile(r"^(\d{1,3})[.)]\s+(.+)$")
_VINETA = re.compile(r"^[-*•]\s+(.+)$")
_SEPARADOR_TABLA = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")
# Negrita o cursiva de Markdown (Docling marca así los encabezados de las tablas de un DOCX).
_ENFASIS = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_LARGO_MAXIMO_TITULO = 80


class TextoNormalizado(BaseModel):
    texto: str
    invisibles_eliminados: int


class UnidadTexto(BaseModel):
    """Un fragmento del documento que puede ser un requisito, con dónde está."""

    ubicacion: str
    seccion: str | None
    titulo_seccion: str | None
    bloque: Bloque
    texto: str


def normalizar_texto(texto: str) -> TextoNormalizado:
    """Limpieza de forma: Unicode NFC, espacios y caracteres invisibles o de control."""
    texto = unicodedata.normalize("NFC", texto.replace("\r\n", "\n").replace("\r", "\n"))
    invisibles = len(_INVISIBLES.findall(texto))
    texto = _CONTROL.sub("", _INVISIBLES.sub("", texto))
    lineas = [_ESPACIOS.sub(" ", linea).strip() for linea in texto.split("\n")]
    return TextoNormalizado(
        texto="\n".join(lineas).strip() + "\n", invisibles_eliminados=invisibles
    )


def segmentar(markdown: str) -> list[UnidadTexto]:
    """Divide el texto normalizado en unidades con su sección y su ubicación."""
    texto = normalizar_texto(markdown).texto
    lineas = [_ENFASIS.sub(r"\2", linea) for linea in texto.split("\n")]
    titulos_markdown = any(_TITULO_MD.match(linea) for linea in lineas)
    segmentador = _Segmentador()
    for i, linea in enumerate(lineas):
        anterior = lineas[i - 1] if i > 0 else ""
        siguiente = lineas[i + 1] if i + 1 < len(lineas) else ""
        titulo = _titulo(linea, anterior, siguiente, titulos_markdown)
        if titulo is not None:
            segmentador.titulo(*titulo)
        elif not linea:
            segmentador.cerrar_bloque()
        elif _es_fila_de_tabla(linea):
            segmentador.fila(linea)
        elif coincidencia := _NUMERADO.match(linea):
            segmentador.punto(int(coincidencia.group(1)), coincidencia.group(2))
        elif coincidencia := _VINETA.match(linea):
            segmentador.vineta(coincidencia.group(1))
        else:
            segmentador.texto(linea)
    segmentador.cerrar_bloque()
    return segmentador.unidades


def _titulo(
    linea: str, anterior: str, siguiente: str, titulos_markdown: bool
) -> tuple[str | None, str] | None:
    """Número y texto del título, o None si la línea no es un título."""
    if titulos_markdown:
        coincidencia = _TITULO_MD.match(linea)
        if not coincidencia:
            return None
        return _numero_del_titulo(coincidencia.group(2))
    # Texto sin «#» (TXT): un título es una línea corta, aislada entre líneas en blanco, que no
    # termina como una frase. Así «3. Cuentas y acceso» es un título y «1. Las cuentas...» no.
    if anterior or siguiente or not linea or len(linea) > _LARGO_MAXIMO_TITULO:
        return None
    if linea.endswith((".", ":", ";", ",")) or _es_fila_de_tabla(linea):
        return None
    return _numero_del_titulo(linea)


def _numero_del_titulo(texto: str) -> tuple[str | None, str]:
    coincidencia = re.match(r"^(\d{1,3})\.?\s+(.+)$", texto)
    if coincidencia:
        return coincidencia.group(1), coincidencia.group(2)
    return None, texto


def _es_fila_de_tabla(linea: str) -> bool:
    return linea.startswith("|") or linea.count(" | ") >= 1


class _Segmentador:
    """Acumula las líneas de cada bloque y genera las unidades con su ubicación."""

    def __init__(self) -> None:
        self.unidades: list[UnidadTexto] = []
        self.seccion: str | None = None
        self.titulo_seccion: str | None = None
        self.contadores: dict[str, int] = {}
        self.actual: tuple[Bloque, str, list[str]] | None = None

    def titulo(self, numero: str | None, texto: str) -> None:
        self.cerrar_bloque()
        self.seccion, self.titulo_seccion, self.contadores = numero, texto, {}

    def punto(self, numero: int, texto: str) -> None:
        self.cerrar_bloque()
        self.actual = ("lista", f"{self.seccion or 0}.{numero}", [texto])

    def vineta(self, texto: str) -> None:
        self.cerrar_bloque()
        self.actual = ("vineta", self._ubicacion("viñeta"), [texto])

    def fila(self, linea: str) -> None:
        if self.actual is None or self.actual[0] != "tabla":
            self.cerrar_bloque()
            self.actual = ("tabla", self._ubicacion("tabla"), [])
        if not _SEPARADOR_TABLA.match(linea):
            celdas = [c.strip() for c in linea.strip().strip("|").split("|")]
            self.actual[2].append(" | ".join(celdas))

    def texto(self, linea: str) -> None:
        # Una línea suelta continúa el punto o el párrafo en curso (un PDF puede partirlos).
        if self.actual is not None and self.actual[0] != "tabla":
            self.actual[2].append(linea)
            return
        self.cerrar_bloque()
        self.actual = ("parrafo", self._ubicacion("párrafo"), [linea])

    def cerrar_bloque(self) -> None:
        if self.actual is None:
            return
        bloque, ubicacion, partes = self.actual
        texto = ("\n" if bloque == "tabla" else " ").join(partes).strip()
        if texto:
            self.unidades.append(
                UnidadTexto(
                    ubicacion=ubicacion,
                    seccion=self.seccion,
                    titulo_seccion=self.titulo_seccion,
                    bloque=bloque,
                    texto=texto,
                )
            )
        self.actual = None

    def _ubicacion(self, clase: str) -> str:
        self.contadores[clase] = self.contadores.get(clase, 0) + 1
        return f"{self.seccion or 0}, {clase} {self.contadores[clase]}"
