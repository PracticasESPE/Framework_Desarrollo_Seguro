"""Extracción del documento de requisitos a Markdown: primer paso de la fase 1.

El documento ya pasó por la carga (orchestrator/documentos.py), pero se vuelve a validar aquí con
las mismas reglas, porque esta función también se usa desde la CLI con archivos locales:

- PDF y DOCX se convierten con Docling, que conserva títulos, listas y tablas. El PDF se procesa
  sin OCR: los documentos de requisitos traen texto, y el OCR descargaría otro modelo y tardaría
  mucho más.
- El PDF se lee con pypdfium2 y no con docling-parse, que es el lector por defecto. docling-parse
  carga unos archivos de su paquete desde código C++ que, en Windows, no abre rutas con letras
  fuera de ASCII: en `D:\\...\\Prácticas\\...` falla con «filename does not exists» aunque el
  archivo exista. pypdfium2 recibe los bytes en memoria y conserva todas las frases del dataset.
- TXT y Markdown se leen directamente: Docling no admite TXT, y un Markdown ya es el resultado.
- Docling recibe los bytes ya validados, no la ruta, para que el archivo no cambie entre la
  validación y la conversión.
- Se fijan un número máximo de páginas y un tiempo máximo. Si Docling no termina o solo convierte
  una parte, la extracción falla: un documento a medias haría perder requisitos sin avisar.

El Markdown resultante sigue siendo entrada no confiable para el LLM de los pasos siguientes.
"""

from __future__ import annotations

import hashlib
import io
import re
import time
from functools import lru_cache
from importlib.metadata import version
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel

from orchestrator.documentos import (
    TAMANO_MAXIMO,
    DocumentoDemasiadoGrande,
    ErrorDocumento,
    Formato,
    detectar_formato,
    nombre_visible,
    validar_contenido,
)

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter

PAGINAS_MAXIMAS = 100
TIEMPO_MAXIMO_S = 300.0
LECTURA_DIRECTA = "lectura directa"
_LINEAS_EN_BLANCO = re.compile(r"\n{3,}")


class ErrorExtraccion(ErrorDocumento):
    """No se pudo extraer el texto del documento. El mensaje se puede mostrar al usuario."""


class DocumentoExtraido(BaseModel):
    """Resultado de la extracción: el Markdown y los datos para trazarlo hasta el original."""

    nombre: str
    formato: Formato
    sha256: str
    herramienta: str
    caracteres: int
    lineas: int
    duracion_s: float
    markdown: str


def extraer_markdown(ruta: Path, nombre: str | None = None) -> DocumentoExtraido:
    """Convierte un documento de requisitos (PDF, DOCX, TXT o MD) a Markdown.

    `nombre` es el nombre original, que da el formato; por defecto, el del archivo. Sirve para los
    documentos cargados desde la API, que se guardan con un nombre generado por el servidor.
    """
    nombre = nombre_visible(nombre or ruta.name)
    formato = detectar_formato(nombre)
    if ruta.stat().st_size > TAMANO_MAXIMO:
        raise DocumentoDemasiadoGrande(
            f"El documento supera el máximo de {TAMANO_MAXIMO // (1024 * 1024)} MB"
        )
    datos = ruta.read_bytes()
    validar_contenido(formato, datos)

    if formato in ("txt", "md"):
        inicio = time.perf_counter()
        texto, herramienta = datos.decode("utf-8-sig"), LECTURA_DIRECTA
    else:
        # Cargar Docling y PyTorch tarda más que convertir; la duración mide solo la conversión.
        _conversor()
        inicio = time.perf_counter()
        texto, herramienta = _con_docling(datos, formato), f"docling {version('docling')}"
    markdown = limpiar_markdown(texto)
    if not markdown.strip():
        raise ErrorExtraccion("No se pudo extraer texto del documento")

    return DocumentoExtraido(
        nombre=nombre,
        formato=formato,
        sha256=hashlib.sha256(datos).hexdigest(),
        herramienta=herramienta,
        caracteres=len(markdown),
        lineas=markdown.count("\n"),
        duracion_s=round(time.perf_counter() - inicio, 2),
        markdown=markdown,
    )


def limpiar_markdown(texto: str) -> str:
    """Ajustes mínimos de forma: finales de línea, espacios al final y líneas en blanco seguidas.

    No cambia palabras: la normalización del texto es un paso posterior de la fase 1.
    """
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    texto = "\n".join(linea.rstrip() for linea in texto.split("\n"))
    return _LINEAS_EN_BLANCO.sub("\n\n", texto).strip() + "\n"


def _con_docling(datos: bytes, formato: Formato) -> str:
    from docling.datamodel.base_models import ConversionStatus, DocumentStream

    resultado = _conversor().convert(
        DocumentStream(name=f"documento.{formato}", stream=io.BytesIO(datos)),
        max_num_pages=PAGINAS_MAXIMAS,
        max_file_size=TAMANO_MAXIMO,
        raises_on_error=False,
    )
    if resultado.status != ConversionStatus.SUCCESS:
        detalle = "; ".join(e.error_message for e in resultado.errors) or resultado.status.value
        raise ErrorExtraccion(f"Docling no pudo convertir el documento completo: {detalle}")
    return resultado.document.export_to_markdown()


@lru_cache(maxsize=1)
def _conversor() -> DocumentConverter:
    """Conversor de Docling, creado una sola vez porque carga sus modelos al primer uso."""
    from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    opciones = PdfPipelineOptions(
        do_ocr=False, do_table_structure=True, document_timeout=TIEMPO_MAXIMO_S
    )
    pdf = PdfFormatOption(pipeline_options=opciones, backend=PyPdfiumDocumentBackend)
    return DocumentConverter(
        allowed_formats=[InputFormat.PDF, InputFormat.DOCX],
        format_options={InputFormat.PDF: pdf},
    )
