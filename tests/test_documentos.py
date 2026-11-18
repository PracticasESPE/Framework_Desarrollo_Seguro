"""Carga del documento de requisitos (orchestrator/documentos.py) y sus endpoints en la API."""

import io
import re
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from orchestrator import documentos
from orchestrator.api import app, carpeta_documentos, montar_dashboard
from orchestrator.documentos import (
    TAMANO_MAXIMO,
    ContenidoNoValido,
    DocumentoDemasiadoGrande,
    FormatoNoPermitido,
    detectar_formato,
    guardar_documento,
    listar_documentos,
    nombre_visible,
    validar_contenido,
)

RAIZ = Path(__file__).resolve().parent.parent
DATASETS = RAIZ / "evaluation" / "datasets"
VALIDACION_TS = RAIZ / "dashboard" / "src" / "validacion.ts"
PDF = b"%PDF-1.7\n%prueba\n"


def docx(entradas: dict[str, bytes] | None = None) -> bytes:
    if entradas is None:
        entradas = {"[Content_Types].xml": b"<Types/>", "word/document.xml": b"<w:document/>"}
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w", compression=zipfile.ZIP_DEFLATED) as archivo:
        for nombre, contenido in entradas.items():
            archivo.writestr(nombre, contenido)
    return memoria.getvalue()


@pytest.fixture
def carpeta(tmp_path: Path):
    destino = tmp_path / "documentos"
    app.dependency_overrides[carpeta_documentos] = lambda: destino
    yield destino
    app.dependency_overrides.clear()


@pytest.fixture
def cliente(carpeta: Path) -> TestClient:
    return TestClient(app)


def subir(cliente: TestClient, nombre: str, datos: bytes):
    return cliente.post(
        "/documentos",
        params={"nombre": nombre},
        content=datos,
        headers={"Content-Type": "application/octet-stream"},
    )


# --- Módulo ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "esperado"),
    [
        ("requisitos.pdf", "requisitos.pdf"),
        ("../../etc/requisitos.pdf", "requisitos.pdf"),
        ("C:\\Users\\x\\requisitos.docx", "requisitos.docx"),
        ("requi\x00sitos\n.txt", "requisitos.txt"),
    ],
)
def test_nombre_visible_quita_carpetas_y_control(nombre: str, esperado: str):
    assert nombre_visible(nombre) == esperado


def test_nombre_visible_recorta_sin_perder_la_extension():
    nombre = nombre_visible("a" * 300 + ".pdf")
    assert len(nombre) == 120
    assert nombre.endswith(".pdf")


@pytest.mark.parametrize(
    ("nombre", "formato"),
    [("r.pdf", "pdf"), ("R.PDF", "pdf"), ("r.docx", "docx"), ("r.txt", "txt"), ("r.md", "md")],
)
def test_detectar_formato_permitido(nombre: str, formato: str):
    assert detectar_formato(nombre) == formato


@pytest.mark.parametrize("nombre", ["r.exe", "r.pdf.exe", "r.html", "r.doc", "r", "r.svg", "."])
def test_detectar_formato_rechaza_lo_que_no_esta_en_la_lista(nombre: str):
    with pytest.raises(FormatoNoPermitido):
        detectar_formato(nombre)


@pytest.mark.parametrize(
    ("formato", "datos"),
    [
        ("pdf", b"<html>no soy un pdf</html>"),
        ("pdf", b""),
        ("docx", b"PK\x03\x04 roto"),
        ("docx", docx({"[Content_Types].xml": b"<Types/>"})),
        ("txt", b"texto\x00binario"),
        ("md", "requisitos en latin-1: ñ".encode("latin-1")),
    ],
)
def test_validar_contenido_rechaza_lo_que_no_corresponde(formato, datos: bytes):
    with pytest.raises(ContenidoNoValido):
        validar_contenido(formato, datos)


def test_validar_contenido_rechaza_docx_con_demasiadas_entradas(monkeypatch):
    monkeypatch.setattr(documentos, "DOCX_MAX_ENTRADAS", 2)
    with pytest.raises(ContenidoNoValido, match="demasiados"):
        validar_contenido("docx", docx({**{f"x{i}": b"" for i in range(3)}}))


def test_validar_contenido_rechaza_docx_que_descomprimido_es_enorme(monkeypatch):
    monkeypatch.setattr(documentos, "DOCX_MAX_DESCOMPRIMIDO", 1000)
    datos = docx(
        {
            "[Content_Types].xml": b"<Types/>",
            "word/document.xml": b"0" * 5000,  # se comprime a unos pocos bytes
        }
    )
    assert len(datos) < 1000
    with pytest.raises(ContenidoNoValido, match="descomprimido"):
        validar_contenido("docx", datos)


def test_validar_contenido_rechaza_el_exceso_de_tamano():
    with pytest.raises(DocumentoDemasiadoGrande):
        validar_contenido("txt", b"a" * (TAMANO_MAXIMO + 1))


@pytest.mark.parametrize("formato", ["pdf", "docx", "txt", "md"])
def test_los_documentos_del_dataset_se_aceptan(formato: str):
    for archivo in sorted(DATASETS.glob(f"*/requisitos.{formato}")):
        validar_contenido(formato, archivo.read_bytes())


def test_guardar_usa_un_nombre_generado_por_el_servidor(tmp_path: Path):
    documento = guardar_documento(PDF, "../../fuera.pdf", tmp_path)
    assert re.fullmatch(r"[0-9a-f]{32}", documento.id)
    assert documento.nombre == "fuera.pdf"
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        f"{documento.id}.json",
        f"{documento.id}.pdf",
    ]
    assert (tmp_path / f"{documento.id}.pdf").read_bytes() == PDF
    assert not (tmp_path.parent / "fuera.pdf").exists()


def test_listar_del_mas_reciente_al_mas_antiguo_e_ignora_fichas_rotas(tmp_path: Path):
    primero = guardar_documento(PDF, "a.pdf", tmp_path)
    segundo = guardar_documento(b"hola", "b.txt", tmp_path)
    (tmp_path / "rota.json").write_text("{no es json", encoding="utf-8")
    assert [d.id for d in listar_documentos(tmp_path)] == [segundo.id, primero.id]
    assert listar_documentos(tmp_path / "no-existe") == []


def test_los_limites_coinciden_con_el_dashboard():
    fuente = VALIDACION_TS.read_text(encoding="utf-8")
    assert "export const TAMANO_MAXIMO = 10 * 1024 * 1024" in fuente
    assert TAMANO_MAXIMO == 10 * 1024 * 1024
    extensiones = re.search(r"EXTENSIONES = \[([^\]]*)\]", fuente)
    assert extensiones is not None
    assert re.findall(r"'(\.\w+)'", extensiones.group(1)) == list(documentos.FORMATOS)


# --- API ------------------------------------------------------------------------------------


def test_cargar_documento(cliente: TestClient, carpeta: Path):
    datos = (DATASETS / "01_tienda_en_linea" / "requisitos.docx").read_bytes()
    respuesta = subir(cliente, "requisitos.docx", datos)
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["nombre"] == "requisitos.docx"
    assert cuerpo["formato"] == "docx"
    assert cuerpo["tamano"] == len(datos)
    assert (carpeta / f"{cuerpo['id']}.docx").read_bytes() == datos

    listado = cliente.get("/documentos")
    assert listado.status_code == 200
    assert [d["id"] for d in listado.json()] == [cuerpo["id"]]


def test_cargar_requisitos_escritos_en_el_dashboard(cliente: TestClient, carpeta: Path):
    texto = "1. El cliente se registra con su contraseña.\n- Como dueño, quiero ver las ventas."
    respuesta = subir(cliente, "requisitos-escritos.md", texto.encode("utf-8"))
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert (cuerpo["nombre"], cuerpo["formato"]) == ("requisitos-escritos.md", "md")
    assert (carpeta / f"{cuerpo['id']}.md").read_text(encoding="utf-8") == texto


@pytest.mark.parametrize(
    ("nombre", "datos", "codigo"),
    [
        ("malicioso.exe", b"MZ", 415),
        ("pagina.html", b"<script>alert(1)</script>", 415),
        ("falso.pdf", b"<html></html>", 400),
        ("vacio.txt", b"", 400),
    ],
)
def test_cargar_rechaza(cliente: TestClient, carpeta: Path, nombre: str, datos: bytes, codigo: int):
    respuesta = subir(cliente, nombre, datos)
    assert respuesta.status_code == codigo
    assert isinstance(respuesta.json()["detail"], str)
    assert not carpeta.exists() or not any(carpeta.iterdir())


def test_cargar_corta_un_cuerpo_demasiado_grande(cliente: TestClient, carpeta: Path):
    respuesta = subir(cliente, "grande.txt", b"a" * (TAMANO_MAXIMO + 1))
    assert respuesta.status_code == 413
    assert not carpeta.exists()


def test_cargar_corta_aunque_no_declare_el_tamano(cliente: TestClient, carpeta: Path):
    def trozos():
        for _ in range(11):
            yield b"a" * (1024 * 1024)

    respuesta = cliente.post("/documentos", params={"nombre": "grande.txt"}, content=trozos())
    assert respuesta.status_code == 413
    assert not carpeta.exists()


def test_cargar_exige_el_nombre(cliente: TestClient):
    assert cliente.post("/documentos", content=PDF).status_code == 422


def test_cabeceras_de_seguridad(cliente: TestClient):
    respuesta = cliente.get("/salud")
    assert respuesta.headers["X-Content-Type-Options"] == "nosniff"
    assert respuesta.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in respuesta.headers["Content-Security-Policy"]
    assert "Content-Security-Policy" not in cliente.get("/docs").headers


def test_montar_dashboard(tmp_path: Path):
    aplicacion = FastAPI()

    @aplicacion.get("/salud")
    def salud() -> dict[str, str]:
        return {"estado": "ok"}

    assert montar_dashboard(aplicacion, tmp_path) is False
    (tmp_path / "index.html").write_text("<h1>dashboard</h1>", encoding="utf-8")
    assert montar_dashboard(aplicacion, tmp_path) is True

    cliente = TestClient(aplicacion)
    assert "dashboard" in cliente.get("/").text
    assert cliente.get("/salud").json() == {"estado": "ok"}
    assert cliente.get("/../pyproject.toml").status_code == 404
