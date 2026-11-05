# /// script
# requires-python = ">=3.12"
# dependencies = ["python-docx>=1.1", "fpdf2>=2.8", "pypdf>=6.0", "pyyaml>=6.0"]
# ///
"""Genera los formatos TXT, DOCX y PDF de cada documento de requisitos del dataset.

La fuente es requisitos.md, escrita con un subconjunto de Markdown: títulos, párrafos, listas
numeradas o con viñetas y tablas. Después de generar, comprueba que cada frase de
referencia.yaml aparece en los cuatro formatos y guarda en formatos.json las huellas que usan las
pruebas (tests/test_datasets.py) para detectar formatos desactualizados.

Tiene sus propias dependencias (no entran en uv.lock):

  uv run evaluation/datasets/generar_formatos.py                     # todos los documentos
  uv run evaluation/datasets/generar_formatos.py 01_tienda_en_linea  # solo uno
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import zipfile
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import yaml
from docx import Document
from docx.shared import Pt
from fpdf import FPDF
from pypdf import PdfReader

CARPETA = Path(__file__).resolve().parent
FUENTE = "requisitos.md"
# Fecha fija en los metadatos: regenerar sin cambios en la fuente produce los mismos archivos.
FECHA = datetime(2026, 11, 4, tzinfo=UTC)
AUTOR = "Framework de desarrollo seguro - dataset de evaluación"
_ITEM = re.compile(r"^(\d+\. |- )")


def huella_texto(texto: str) -> str:
    """Huella del texto sin depender de los finales de línea (Git en Windows usa CRLF)."""
    return hashlib.sha256(texto.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def normalizar(texto: str) -> str:
    return " ".join(texto.split())


def leer_bloques(markdown: str) -> list[tuple]:
    """Bloques del documento: ("titulo", nivel, texto), ("parrafo", texto),
    ("lista", numerada, elementos) y ("tabla", filas)."""
    lineas = [linea.rstrip() for linea in markdown.splitlines()]
    bloques: list[tuple] = []
    i = 0
    while i < len(lineas):
        linea = lineas[i]
        if not linea:
            i += 1
        elif linea.startswith("#"):
            nivel = len(linea) - len(linea.lstrip("#"))
            bloques.append(("titulo", nivel, linea[nivel:].strip()))
            i += 1
        elif linea.startswith("|"):
            filas = []
            while i < len(lineas) and lineas[i].startswith("|"):
                celdas = [c.strip() for c in lineas[i].strip("|").split("|")]
                if not all(c and set(c) <= {"-", ":"} for c in celdas):  # separador de cabecera
                    filas.append(celdas)
                i += 1
            bloques.append(("tabla", filas))
        elif _ITEM.match(linea):
            numerada = linea[0].isdigit()
            elementos = []
            while i < len(lineas) and _ITEM.match(lineas[i]):
                elementos.append(_ITEM.sub("", lineas[i]).strip())
                i += 1
            bloques.append(("lista", numerada, elementos))
        else:
            partes = []
            while i < len(lineas) and lineas[i] and not lineas[i].startswith(("#", "|")):
                if _ITEM.match(lineas[i]):
                    break
                partes.append(lineas[i].strip())
                i += 1
            bloques.append(("parrafo", " ".join(partes)))
    return bloques


def _marca(numerada: bool, n: int) -> str:
    return f"{n}. " if numerada else "- "


def escribir_txt(bloques: list[tuple], destino: Path) -> None:
    partes = []
    for bloque in bloques:
        match bloque:
            case ("titulo", _, texto) | ("parrafo", texto):
                partes.append(texto)
            case ("lista", numerada, elementos):
                partes.append(
                    "\n".join(f"{_marca(numerada, n)}{e}" for n, e in enumerate(elementos, 1))
                )
            case ("tabla", filas):
                partes.append("\n".join(" | ".join(fila) for fila in filas))
    destino.write_text("\n\n".join(partes) + "\n", encoding="utf-8", newline="\n")


def _zip_determinista(contenido: bytes) -> bytes:
    """Reescribe el ZIP del DOCX con fechas fijas: python-docx usa la hora actual."""
    salida = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(contenido)) as origen, zipfile.ZipFile(salida, "w") as nuevo:
        for item in origen.infolist():
            info = zipfile.ZipInfo(item.filename, date_time=FECHA.timetuple()[:6])
            info.compress_type = zipfile.ZIP_DEFLATED
            nuevo.writestr(info, origen.read(item.filename))
    return salida.getvalue()


def escribir_docx(bloques: list[tuple], titulo: str, destino: Path) -> None:
    doc = Document()
    doc.styles["Normal"].font.size = Pt(11)
    propiedades = doc.core_properties
    propiedades.title, propiedades.author, propiedades.last_modified_by = titulo, AUTOR, AUTOR
    propiedades.created = propiedades.modified = FECHA.replace(tzinfo=None)
    propiedades.revision = 1
    for bloque in bloques:
        match bloque:
            case ("titulo", nivel, texto):
                doc.add_heading(texto, level=nivel - 1)
            case ("parrafo", texto):
                doc.add_paragraph(texto)
            case ("lista", numerada, elementos):
                for n, elemento in enumerate(elementos, 1):
                    if numerada:  # numeración escrita, como en el TXT: reinicia en cada sección
                        doc.add_paragraph(f"{n}. {elemento}", style="List Paragraph")
                    else:
                        doc.add_paragraph(elemento, style="List Bullet")
            case ("tabla", filas):
                tabla = doc.add_table(rows=0, cols=len(filas[0]), style="Table Grid")
                for numero, fila in enumerate(filas):
                    celdas = tabla.add_row().cells
                    for celda, texto in zip(celdas, fila, strict=True):
                        celda.text = texto
                        if numero == 0:
                            celda.paragraphs[0].runs[0].bold = True
                doc.add_paragraph()
    memoria = io.BytesIO()
    doc.save(memoria)
    destino.write_bytes(_zip_determinista(memoria.getvalue()))


class _Pdf(FPDF):
    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("Helvetica", size=9)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")


def escribir_pdf(bloques: list[tuple], titulo: str, destino: Path) -> None:
    # Fuente estándar Helvetica (Latin-1): la fuente debe poder codificarse en Latin-1.
    pdf = _Pdf(format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(True, margin=20)
    pdf.set_creation_date(FECHA)
    pdf.set_title(titulo)
    pdf.set_author(AUTOR)
    pdf.set_lang("es")
    pdf.add_page()
    for bloque in bloques:
        match bloque:
            case ("titulo", nivel, texto):
                pdf.ln(2)
                pdf.set_font("Helvetica", "B", 18 if nivel == 1 else 13)
                pdf.multi_cell(0, 9 if nivel == 1 else 7, texto, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(2)
            case ("parrafo", texto):
                pdf.set_font("Helvetica", size=11)
                # Tampoco se parte un párrafo: algunos requisitos están en prosa.
                lineas = pdf.multi_cell(0, 6, texto, dry_run=True, output="LINES")
                if pdf.will_page_break(len(lineas) * 6):
                    pdf.add_page()
                pdf.multi_cell(0, 6, texto, new_x="LMARGIN", new_y="NEXT")
                pdf.ln(3)
            case ("lista", numerada, elementos):
                pdf.set_font("Helvetica", size=11)
                margen = pdf.l_margin
                ancho = pdf.w - pdf.r_margin - (margen + 11)
                for n, elemento in enumerate(elementos, 1):
                    # Un requisito no se parte entre páginas: el pie quedaría en medio de la frase.
                    lineas = pdf.multi_cell(ancho, 6, elemento, dry_run=True, output="LINES")
                    if pdf.will_page_break(len(lineas) * 6):
                        pdf.add_page()
                    pdf.set_x(margen + 4)
                    pdf.cell(7, 6, _marca(numerada, n).strip())
                    pdf.set_left_margin(margen + 11)
                    pdf.multi_cell(0, 6, elemento, new_x="LMARGIN", new_y="NEXT")
                    pdf.set_left_margin(margen)
                    pdf.ln(1.5)
                pdf.ln(2)
            case ("tabla", filas):
                pdf.set_font("Helvetica", size=10)
                with pdf.table(text_align="LEFT", line_height=6) as tabla:
                    for fila in filas:
                        nueva = tabla.row()
                        for celda in fila:
                            nueva.cell(celda)
                pdf.ln(4)
    pdf.output(str(destino))


def texto_docx(ruta: Path) -> str:
    doc = Document(str(ruta))
    celdas = [c.text for t in doc.tables for fila in t.rows for c in fila.cells]
    return "\n".join([p.text for p in doc.paragraphs] + celdas)


def texto_pdf(ruta: Path) -> str:
    return "\n".join(pagina.extract_text() or "" for pagina in PdfReader(str(ruta)).pages)


def frases_de_referencia(carpeta: Path) -> list[str]:
    referencia = yaml.safe_load((carpeta / "referencia.yaml").read_text(encoding="utf-8"))
    return [r["texto"] for r in referencia["requisitos"]] + referencia.get("fuera_de_alcance", [])


def generar(carpeta: Path) -> list[str]:
    """Genera los formatos de un documento y devuelve los problemas encontrados."""
    markdown = (carpeta / FUENTE).read_text(encoding="utf-8")
    try:
        markdown.encode("latin-1")
    except UnicodeEncodeError as error:
        caracter = markdown[error.start]
        return [f"{FUENTE}: el carácter {caracter!r} no existe en Latin-1 (fuente del PDF)"]
    bloques = leer_bloques(markdown)
    titulo = next(b[2] for b in bloques if b[0] == "titulo")
    txt, docx, pdf = (carpeta / f"requisitos.{e}" for e in ("txt", "docx", "pdf"))
    escribir_txt(bloques, txt)
    escribir_docx(bloques, titulo, docx)
    escribir_pdf(bloques, titulo, pdf)

    textos = {
        FUENTE: markdown,
        txt.name: txt.read_text(encoding="utf-8"),
        docx.name: texto_docx(docx),
        pdf.name: texto_pdf(pdf),
    }
    problemas = [
        f"{formato}: no aparece «{frase[:60]}...»"
        for formato, texto in textos.items()
        for frase in frases_de_referencia(carpeta)
        if normalizar(frase) not in normalizar(texto)
    ]
    huellas = {
        "fuente": FUENTE,
        "fuente_sha256": huella_texto(markdown),
        "formatos": {
            txt.name: huella_texto(textos[txt.name]),
            docx.name: hashlib.sha256(docx.read_bytes()).hexdigest(),
            pdf.name: hashlib.sha256(pdf.read_bytes()).hexdigest(),
        },
        "herramientas": {p: version(p) for p in ("python-docx", "fpdf2", "pypdf")},
    }
    (carpeta / "formatos.json").write_text(
        json.dumps(huellas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    return problemas


def main(nombres: list[str]) -> int:
    carpetas = [CARPETA / n for n in nombres] or sorted(
        p.parent for p in CARPETA.glob(f"*/{FUENTE}")
    )
    total = 0
    for carpeta in carpetas:
        problemas = generar(carpeta)
        total += len(problemas)
        estado = "correcto" if not problemas else f"{len(problemas)} problema(s)"
        print(f"{carpeta.name}: txt, docx y pdf generados; {estado}")
        for problema in problemas:
            print(f"  - {problema}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
