"""Extracción del documento de requisitos a Markdown (orchestrator/ingest), inicio de la fase 1.

La fidelidad se mide con el dataset de evaluación: cada frase de la referencia es literal del
documento, así que debe aparecer en el Markdown extraído de cada formato. La referencia solo la
leen estas pruebas, nunca el framework.

Las pruebas con PDF tardan cerca de un minuto por documento, porque Docling analiza el diseño de
cada página con un modelo. Se activan con DOCLING_PDF=1; el workflow extrae además el PDF del
documento 1 en la fase 1.
"""

import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.documentos import (
    ContenidoNoValido,
    DocumentoDemasiadoGrande,
    FormatoNoPermitido,
    guardar_documento,
)
from orchestrator.ingest import ErrorExtraccion, extraccion, extraer_markdown, limpiar_markdown

DATASETS = Path(__file__).resolve().parent.parent / "evaluation" / "datasets"
DOCUMENTOS = sorted(p.parent for p in DATASETS.glob("*/referencia.yaml"))
runner = CliRunner()

con_pdf = pytest.mark.skipif(
    os.environ.get("DOCLING_PDF") != "1", reason="Lento: activar con DOCLING_PDF=1"
)


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def _frases_de_la_referencia(carpeta: Path) -> list[str]:
    referencia = yaml.safe_load((carpeta / "referencia.yaml").read_text(encoding="utf-8"))
    return [r["texto"] for r in referencia["requisitos"]] + referencia["fuera_de_alcance"]


def _frases_perdidas(carpeta: Path, formato: str) -> list[str]:
    extraido = extraer_markdown(carpeta / f"requisitos.{formato}")
    texto = _normalizar(extraido.markdown)
    return [f for f in _frases_de_la_referencia(carpeta) if _normalizar(f) not in texto]


# --- Fidelidad con el dataset de evaluación --------------------------------------------------


@pytest.mark.parametrize("formato", ["md", "txt", "docx"])
@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda c: c.name)
def test_la_extraccion_conserva_todas_las_frases(carpeta, formato):
    assert _frases_perdidas(carpeta, formato) == []


@con_pdf
@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda c: c.name)
def test_la_extraccion_del_pdf_conserva_todas_las_frases(carpeta):
    assert _frases_perdidas(carpeta, "pdf") == []


def test_el_dataset_tiene_los_tres_documentos():
    assert [c.name for c in DOCUMENTOS] == [
        "01_tienda_en_linea",
        "02_gestion_academica",
        "03_citas_medicas",
    ]


def test_docx_con_docling_conserva_titulos_y_tablas():
    extraido = extraer_markdown(DOCUMENTOS[0] / "requisitos.docx")
    assert extraido.herramienta.startswith("docling ")
    assert "## 3. Cuenta del cliente" in extraido.markdown
    assert "| Visitante" in extraido.markdown  # la tabla de usuarios sigue siendo una tabla


def test_metadatos_del_documento_extraido():
    ruta = DOCUMENTOS[0] / "requisitos.txt"
    extraido = extraer_markdown(ruta)
    assert extraido.formato == "txt"
    assert extraido.herramienta == "lectura directa"
    # Huella de los bytes en disco: Git en Windows puede cambiar los finales de línea.
    assert extraido.sha256 == hashlib.sha256(ruta.read_bytes()).hexdigest()
    assert extraido.caracteres == len(extraido.markdown)


# --- Validación de la entrada ----------------------------------------------------------------


def test_formato_no_permitido(tmp_path):
    ruta = tmp_path / "requisitos.html"
    ruta.write_text("<p>hola</p>", encoding="utf-8")
    with pytest.raises(FormatoNoPermitido):
        extraer_markdown(ruta)


def test_la_extension_no_basta(tmp_path):
    ruta = tmp_path / "requisitos.pdf"
    ruta.write_text("Esto no es un PDF", encoding="utf-8")
    with pytest.raises(ContenidoNoValido, match="no es un PDF"):
        extraer_markdown(ruta)


def test_texto_con_datos_binarios(tmp_path):
    ruta = tmp_path / "requisitos.txt"
    ruta.write_bytes(b"requisito\x00binario")
    with pytest.raises(ContenidoNoValido, match="binarios"):
        extraer_markdown(ruta)


def test_documento_demasiado_grande_no_se_lee(tmp_path, monkeypatch):
    ruta = tmp_path / "requisitos.txt"
    ruta.write_text("x" * 100, encoding="utf-8")
    monkeypatch.setattr(extraccion, "TAMANO_MAXIMO", 10)
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("No debía leerse"))
    with pytest.raises(DocumentoDemasiadoGrande):
        extraer_markdown(ruta)


def test_documento_sin_texto(tmp_path):
    ruta = tmp_path / "requisitos.md"
    ruta.write_text(" \n\n \t\n", encoding="utf-8")
    with pytest.raises(ErrorExtraccion, match="No se pudo extraer texto"):
        extraer_markdown(ruta)


def test_el_nombre_original_da_el_formato(tmp_path):
    ruta = tmp_path / "0f3c"  # como los documentos cargados: nombre generado por el servidor
    ruta.write_text("# Requisitos\n", encoding="utf-8")
    extraido = extraer_markdown(ruta, nombre="C:\\Users\\otro\\requisitos.md")
    assert extraido.nombre == "requisitos.md"
    assert extraido.formato == "md"


# --- Docling ---------------------------------------------------------------------------------


@pytest.mark.parametrize("estado", ["failure", "partial_success"])
def test_si_docling_no_convierte_todo_la_extraccion_falla(monkeypatch, estado):
    from docling.datamodel.base_models import ConversionStatus

    resultado = SimpleNamespace(
        status=ConversionStatus(estado),
        errors=[SimpleNamespace(error_message="se agotó el tiempo")],
        document=None,
    )
    conversor = SimpleNamespace(convert=lambda *a, **k: resultado)
    monkeypatch.setattr(extraccion, "_conversor", lambda: conversor)
    with pytest.raises(ErrorExtraccion, match="se agotó el tiempo"):
        extraer_markdown(DOCUMENTOS[0] / "requisitos.docx")


def test_docling_recibe_los_bytes_validados_y_los_limites(monkeypatch):
    from docling.datamodel.base_models import ConversionStatus

    llamada = {}

    def convertir(fuente, **opciones):
        llamada.update(nombre=fuente.name, datos=fuente.stream.read(), **opciones)
        documento = SimpleNamespace(export_to_markdown=lambda: "# Requisitos\r\n\r\n\r\n1. Uno  ")
        return SimpleNamespace(status=ConversionStatus.SUCCESS, errors=[], document=documento)

    monkeypatch.setattr(extraccion, "_conversor", lambda: SimpleNamespace(convert=convertir))
    ruta = DOCUMENTOS[0] / "requisitos.docx"
    extraido = extraer_markdown(ruta)

    assert llamada["nombre"] == "documento.docx"
    assert llamada["datos"] == ruta.read_bytes()
    assert llamada["max_num_pages"] == extraccion.PAGINAS_MAXIMAS
    assert llamada["raises_on_error"] is False
    assert extraido.markdown == "# Requisitos\n\n1. Uno\n"


def test_limpiar_markdown():
    assert limpiar_markdown("a  \r\nb\r\rc\n\n\n\n\nd") == "a\nb\n\nc\n\nd\n"


# --- CLI -------------------------------------------------------------------------------------


def test_comando_extraer_guarda_markdown_y_metadatos(tmp_path):
    origen = DOCUMENTOS[0] / "requisitos.txt"
    resultado = runner.invoke(
        app, ["requisitos", "extraer", str(origen), "--destino", str(tmp_path)]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Herramienta: lectura directa" in resultado.output
    assert "--- Vista previa ---" in resultado.output
    markdown = (tmp_path / "requisitos-txt.md").read_text(encoding="utf-8")
    metadatos = json.loads((tmp_path / "requisitos-txt.json").read_text(encoding="utf-8"))
    assert markdown.startswith("Tienda en línea: documento de requisitos")
    assert metadatos["markdown"] == "requisitos-txt.md"
    assert metadatos["caracteres"] == len(markdown)


def test_comando_extraer_un_documento_cargado(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(tmp_path))
    datos = (DOCUMENTOS[0] / "requisitos.md").read_bytes()
    cargado = guardar_documento(datos, "Requisitos tienda.md", tmp_path / "documentos")

    resultado = runner.invoke(app, ["requisitos", "extraer", "--documento", cargado.id])

    assert resultado.exit_code == 0, resultado.output
    assert "Documento: Requisitos tienda.md (md)" in resultado.output
    assert (tmp_path / "requisitos" / f"{cargado.id}.md").is_file()


@pytest.mark.parametrize(
    ("argumentos", "codigo", "mensaje"),
    [
        ([], 2, "solo uno de los dos"),
        (["algo.txt", "--documento", "0" * 32], 2, "solo uno de los dos"),
        (["--documento", "../../.env"], 2, "Id de documento no válido"),
        (["--documento", "0" * 32], 1, "No existe el documento"),
        (["no-existe.pdf"], 1, "No existe el archivo"),
    ],
)
def test_comando_extraer_rechaza_entradas_invalidas(
    tmp_path, monkeypatch, argumentos, codigo, mensaje
):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(tmp_path))
    resultado = runner.invoke(app, ["requisitos", "extraer", *argumentos])
    assert resultado.exit_code == codigo
    assert mensaje in resultado.output


def test_comando_extraer_informa_un_documento_rechazado(tmp_path):
    ruta = tmp_path / "requisitos.docx"
    ruta.write_text("no es un docx", encoding="utf-8")
    resultado = runner.invoke(app, ["requisitos", "extraer", str(ruta)])
    assert resultado.exit_code == 1
    assert "no es un DOCX válido" in resultado.output
