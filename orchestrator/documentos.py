"""Carga del documento de requisitos: el paso de captura de la fase 1.

El documento llega desde el dashboard o la API y es la entrada menos confiable del framework, así
que se valida antes de guardarlo:

- Lista permitida de formatos (PDF, DOCX, TXT y Markdown) y comprobación de que el contenido
  corresponde al formato, no solo la extensión (CWE-434).
- Tamaño máximo (CWE-400), que la API también aplica mientras recibe el cuerpo.
- El nombre del archivo guardado lo genera el servidor. El nombre original solo se muestra, nunca
  se usa como ruta (CWE-22).
- Un DOCX es un ZIP: se limita el número de entradas y el tamaño descomprimido declarado
  (CWE-409), porque la extracción con Docling lo descomprimirá después.
"""

from __future__ import annotations

import hashlib
import io
import re
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Literal

from pydantic import BaseModel, ValidationError

# Si cambian, hay que cambiar también dashboard/src/validacion.ts (lo comprueba test_documentos).
TAMANO_MAXIMO = 10 * 1024 * 1024
FORMATOS: dict[str, str] = {".pdf": "pdf", ".docx": "docx", ".txt": "txt", ".md": "md"}

DOCX_MAX_ENTRADAS = 1000
DOCX_MAX_DESCOMPRIMIDO = 100 * 1024 * 1024
DOCX_OBLIGATORIOS = ("[Content_Types].xml", "word/document.xml")
LARGO_MAXIMO_NOMBRE = 120
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")

Formato = Literal["pdf", "docx", "txt", "md"]


class ErrorDocumento(ValueError):
    """El documento no se acepta. El mensaje se puede mostrar a quien lo subió."""


class FormatoNoPermitido(ErrorDocumento):
    pass


class DocumentoDemasiadoGrande(ErrorDocumento):
    pass


class ContenidoNoValido(ErrorDocumento):
    pass


class DocumentoCargado(BaseModel):
    """Lo que se guarda junto a cada documento y lo que la API devuelve."""

    id: str
    nombre: str
    formato: Formato
    tamano: int
    sha256: str
    fecha: datetime


def nombre_visible(nombre: str) -> str:
    """Nombre original solo para mostrarlo: sin carpetas ni caracteres de control."""
    # PureWindowsPath trata tanto «/» como «\» como separadores de carpeta.
    base = _CONTROL.sub("", PureWindowsPath(nombre).name).strip()
    if len(base) > LARGO_MAXIMO_NOMBRE:
        raiz, punto, extension = base.rpartition(".")
        if punto and len(extension) <= 10:
            base = f"{raiz[: LARGO_MAXIMO_NOMBRE - len(extension) - 1]}.{extension}"
        else:
            base = base[:LARGO_MAXIMO_NOMBRE]
    return base


def detectar_formato(nombre: str) -> Formato:
    """Formato según la extensión del nombre, solo si está en la lista permitida."""
    extension = Path(nombre_visible(nombre)).suffix.lower()
    formato = FORMATOS.get(extension)
    if formato is None:
        raise FormatoNoPermitido("Formato no permitido: el documento debe ser PDF, DOCX, TXT o MD")
    return formato  # type: ignore[return-value]


def validar_contenido(formato: Formato, datos: bytes) -> None:
    """Comprueba que el contenido es de verdad del formato que indica la extensión."""
    if not datos:
        raise ContenidoNoValido("El archivo está vacío")
    if len(datos) > TAMANO_MAXIMO:
        raise DocumentoDemasiadoGrande(
            f"El documento supera el máximo de {TAMANO_MAXIMO // (1024 * 1024)} MB"
        )
    match formato:
        case "pdf":
            if not datos.startswith(b"%PDF-"):
                raise ContenidoNoValido("El archivo no es un PDF válido")
        case "docx":
            _validar_docx(datos)
        case "txt" | "md":
            if b"\x00" in datos:
                raise ContenidoNoValido("El archivo de texto contiene datos binarios")
            try:
                datos.decode("utf-8-sig")
            except UnicodeDecodeError as error:
                raise ContenidoNoValido("El archivo de texto debe estar en UTF-8") from error


def _validar_docx(datos: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(datos)) as archivo:
            entradas = archivo.infolist()
    except zipfile.BadZipFile as error:
        raise ContenidoNoValido("El archivo no es un DOCX válido") from error
    if len(entradas) > DOCX_MAX_ENTRADAS:
        raise ContenidoNoValido("El DOCX tiene demasiados archivos internos")
    if sum(entrada.file_size for entrada in entradas) > DOCX_MAX_DESCOMPRIMIDO:
        raise ContenidoNoValido("El DOCX descomprimido es demasiado grande")
    nombres = {entrada.filename for entrada in entradas}
    if not all(obligatorio in nombres for obligatorio in DOCX_OBLIGATORIOS):
        raise ContenidoNoValido("El archivo no es un DOCX válido")


def guardar_documento(datos: bytes, nombre: str, carpeta: Path) -> DocumentoCargado:
    """Valida el documento y lo guarda en la carpeta con un nombre generado por el servidor."""
    formato = detectar_formato(nombre)
    validar_contenido(formato, datos)
    documento = DocumentoCargado(
        id=uuid.uuid4().hex,
        nombre=nombre_visible(nombre),
        formato=formato,
        tamano=len(datos),
        sha256=hashlib.sha256(datos).hexdigest(),
        fecha=datetime.now(UTC),
    )
    carpeta.mkdir(parents=True, exist_ok=True)
    # Modo «x»: nunca sobrescribe un archivo existente.
    with (carpeta / f"{documento.id}.{formato}").open("xb") as destino:
        destino.write(datos)
    (carpeta / f"{documento.id}.json").write_text(documento.model_dump_json(), encoding="utf-8")
    return documento


def listar_documentos(carpeta: Path) -> list[DocumentoCargado]:
    """Documentos cargados, del más reciente al más antiguo."""
    if not carpeta.is_dir():
        return []
    documentos = []
    for ficha in carpeta.glob("*.json"):
        try:
            documentos.append(DocumentoCargado.model_validate_json(ficha.read_bytes()))
        except ValidationError:
            continue
    return sorted(documentos, key=lambda documento: documento.fecha, reverse=True)
