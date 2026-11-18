"""Dataset de evaluación (evaluation/datasets): documentos de requisitos y su respuesta esperada."""

import hashlib
import html
import json
import re
import zipfile
from pathlib import Path

import pytest
import yaml

from orchestrator.knowledge.base_conocimiento import cargar_base_conocimiento

DATASETS = Path(__file__).resolve().parent.parent / "evaluation" / "datasets"
VOCABULARIO = yaml.safe_load((DATASETS / "vocabulario.yaml").read_text(encoding="utf-8"))
DOCUMENTOS = sorted(p.parent for p in DATASETS.glob("*/referencia.yaml"))
FORMATOS = ("requisitos.md", "requisitos.txt", "requisitos.docx", "requisitos.pdf")
TIPO_POR_PREFIJO = {"RF": "funcional", "RNF": "no_funcional"}


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def _huella_texto(texto: str) -> str:
    """Igual que generar_formatos.py: no depende de los finales de línea de Git en Windows."""
    return hashlib.sha256(texto.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def _referencia(carpeta: Path) -> dict:
    return yaml.safe_load((carpeta / "referencia.yaml").read_text(encoding="utf-8"))


def _texto_docx(ruta: Path) -> str:
    with zipfile.ZipFile(ruta) as docx:
        xml = docx.read("word/document.xml").decode("utf-8")
    parrafos = xml.split("</w:p>")
    return "\n".join(
        html.unescape("".join(re.findall(r"<w:t(?: [^>]*)?>([^<]*)</w:t>", p))) for p in parrafos
    )


def _frases(referencia: dict) -> list[str]:
    return [r["texto"] for r in referencia["requisitos"]] + referencia["fuera_de_alcance"]


@pytest.fixture(scope="module")
def base():
    return cargar_base_conocimiento()


def test_hay_documentos():
    assert DOCUMENTOS, "evaluation/datasets no tiene ningún documento con referencia.yaml"


@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda p: p.name)
def test_estan_todos_los_formatos(carpeta):
    faltan = [f for f in (*FORMATOS, "formatos.json") if not (carpeta / f).is_file()]
    assert faltan == []
    assert (carpeta / "requisitos.pdf").read_bytes().startswith(b"%PDF-")


@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda p: p.name)
def test_la_referencia_usa_el_vocabulario_y_la_base_de_conocimiento(carpeta, base):
    referencia = _referencia(carpeta)
    controles = {c.id for c in base.controles}
    riesgos = {r.id for r in base.riesgos_api}
    servicios = {s["nombre"] for s in referencia["servicios"]}
    permitidos = servicios | {VOCABULARIO["servicio_transversal"]}
    errores = []

    ids = [r["id"] for r in referencia["requisitos"]]
    errores += [f"id repetido: {i}" for i in sorted({i for i in ids if ids.count(i) > 1})]
    for r in referencia["requisitos"]:
        prefijo = r["id"].split("-")[0]
        if TIPO_POR_PREFIJO.get(prefijo) != r["tipo"]:
            errores.append(f"{r['id']}: el tipo {r['tipo']!r} no corresponde al prefijo")
        errores += [
            f"{r['id']}: etiqueta {e!r} fuera del vocabulario"
            for e in r["etiquetas"]
            if e not in VOCABULARIO["etiquetas"]
        ]
        errores += [
            f"{r['id']}: {c} no está en la base de conocimiento"
            for c in r["controles_asvs"]
            if c not in controles
        ]
        errores += [
            f"{r['id']}: {c} no está en la base de conocimiento"
            for c in r["riesgos_api"]
            if c not in riesgos
        ]
        if r["servicio"] not in permitidos:
            errores.append(f"{r['id']}: servicio {r['servicio']!r} no declarado")
    errores += [
        f"patrón {p['patron']!r} no está en knowledge_base/patrones"
        for p in referencia["patrones"]
        if p["patron"] not in {q.patron for q in base.patrones}
    ]
    usados = {r["servicio"] for r in referencia["requisitos"]}
    errores += [f"el servicio {s!r} no tiene requisitos" for s in sorted(servicios - usados)]
    assert errores == []


@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda p: p.name)
def test_cada_frase_de_la_referencia_esta_en_el_documento(carpeta):
    """Así la fase 1 se puede medir comparando con el texto literal. El PDF lo comprueba
    generar_formatos.py al crearlo, y test_los_formatos_estan_al_dia que no ha cambiado."""
    textos = {
        "requisitos.md": (carpeta / "requisitos.md").read_text(encoding="utf-8"),
        "requisitos.txt": (carpeta / "requisitos.txt").read_text(encoding="utf-8"),
        "requisitos.docx": _texto_docx(carpeta / "requisitos.docx"),
    }
    faltan = [
        f"{formato}: {frase[:60]}"
        for formato, texto in textos.items()
        for frase in _frases(_referencia(carpeta))
        if _normalizar(frase) not in _normalizar(texto)
    ]
    assert faltan == []


@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda p: p.name)
def test_los_formatos_estan_al_dia(carpeta):
    """Si se edita requisitos.md hay que volver a ejecutar generar_formatos.py."""
    huellas = json.loads((carpeta / "formatos.json").read_text(encoding="utf-8"))
    fuente = (carpeta / "requisitos.md").read_text(encoding="utf-8")
    assert huellas["fuente_sha256"] == _huella_texto(fuente), "formatos generados con otra fuente"
    txt = (carpeta / "requisitos.txt").read_text(encoding="utf-8")
    assert huellas["formatos"]["requisitos.txt"] == _huella_texto(txt)
    for nombre in ("requisitos.docx", "requisitos.pdf"):
        actual = hashlib.sha256((carpeta / nombre).read_bytes()).hexdigest()
        assert huellas["formatos"][nombre] == actual, f"{nombre} cambió después de generarse"


@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda p: p.name)
def test_el_documento_no_revela_la_respuesta(carpeta):
    """El framework recibe el documento: no debe traer la clasificación ni las etiquetas."""
    documento = (carpeta / "requisitos.md").read_text(encoding="utf-8")
    assert not re.search(r"\bRN?F-\d", documento)
    assert [e for e in VOCABULARIO["etiquetas"] if e in documento] == []


@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda p: p.name)
def test_la_fuente_cabe_en_latin1(carpeta):
    """El PDF usa una fuente estándar: un carácter fuera de Latin-1 no se podría regenerar."""
    (carpeta / "requisitos.md").read_text(encoding="utf-8").encode("latin-1")


@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda p: p.name)
def test_ninguna_frase_fuera_de_alcance_es_un_requisito(carpeta):
    referencia = _referencia(carpeta)
    requisitos = {_normalizar(r["texto"]) for r in referencia["requisitos"]}
    assert [f for f in referencia["fuera_de_alcance"] if _normalizar(f) in requisitos] == []
