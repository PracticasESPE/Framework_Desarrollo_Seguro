"""Ejecuciones de la fase 1 desde la API y su progreso con Server-Sent Events.

El LLM se simula, como en test_clasificacion: las pruebas no gastan cuota ni dependen de la red.
El documento es Markdown, que se lee sin Docling, para que la fase 1 tarde milisegundos.
"""

import json
import re
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orchestrator.api import (
    app,
    carpeta_documentos,
    carpeta_requisitos,
    fabrica_llm,
    registro_ejecuciones,
)
from orchestrator.documentos import DocumentoNoEncontrado, guardar_documento, obtener_documento
from orchestrator.ejecuciones import Ejecucion, RegistroEjecuciones
from orchestrator.llm import ErrorProveedorLLM

TEXTO = """\
# Tienda

## 1. Contexto

La empresa vende ropa por internet.

## 3. Cuenta del cliente

1. El cliente se registra con su correo y una contraseña.
2. Las contraseñas nunca se guardan tal como se escriben.
"""


class LLMSimulado:
    """El contexto no es requisito; el resto, funcional. Puede fallar o esperar una señal."""

    nombre = "simulado"

    def __init__(self, error: Exception | None = None, esperar: threading.Event | None = None):
        self.error = error
        self.esperar = esperar

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        if self.esperar is not None:
            self.esperar.wait(timeout=10)
        if self.error is not None:
            raise self.error
        ubicaciones = re.findall(r'<unidad-[0-9a-f]{8} ubicacion="([^"]+)">', prompt)
        return esquema.model_validate(
            {"clasificaciones": [_clasificacion(u, "Contexto" in prompt) for u in ubicaciones]}
        )


def _clasificacion(ubicacion: str, es_contexto: bool) -> dict:
    if es_contexto:
        return {"ubicacion": ubicacion, "es_requisito": False}
    return {
        "ubicacion": ubicacion,
        "es_requisito": True,
        "tipo": "funcional",
        "actor": "cliente",
        "accion": "registrarse",
        "entidades": ["Cliente"],
        "servicio_sugerido": "usuarios",
        "etiquetas": ["autenticacion"],
    }


@pytest.fixture
def entorno(tmp_path: Path):
    """API con carpetas temporales, un registro vacío y el LLM simulado."""
    estado = {"llm": LLMSimulado()}
    documentos = tmp_path / "documentos"
    requisitos = tmp_path / "requisitos"
    app.dependency_overrides[carpeta_documentos] = lambda: documentos
    app.dependency_overrides[carpeta_requisitos] = lambda: requisitos
    registro = RegistroEjecuciones()
    app.dependency_overrides[registro_ejecuciones] = lambda: registro
    app.dependency_overrides[fabrica_llm] = lambda: lambda: estado["llm"]
    documento = guardar_documento(TEXTO.encode("utf-8"), "requisitos.md", documentos)
    yield {
        "cliente": TestClient(app),
        "documento": documento,
        "requisitos": requisitos,
        "estado": estado,
    }
    app.dependency_overrides.clear()


def eventos(cliente: TestClient, id_ejecucion: str, ultimo: int | None = None) -> list[dict]:
    """Lee el flujo SSE hasta que el servidor lo cierra y devuelve los datos de cada evento."""
    cabeceras = {} if ultimo is None else {"Last-Event-ID": str(ultimo)}
    recibidos: list[dict] = []
    ids: list[str] = []
    url = f"/ejecuciones/{id_ejecucion}/eventos"
    with cliente.stream("GET", url, headers=cabeceras) as respuesta:
        assert respuesta.status_code == 200
        assert respuesta.headers["content-type"].startswith("text/event-stream")
        assert respuesta.headers["cache-control"] == "no-cache"
        for linea in respuesta.iter_lines():
            if linea.startswith("id: "):
                ids.append(linea.removeprefix("id: "))
            elif linea.startswith("data: "):
                recibidos.append(json.loads(linea.removeprefix("data: ")))
    assert ids == [str(e["id"]) for e in recibidos]  # el id SSE es el del evento
    return recibidos


def iniciar(entorno) -> str:
    respuesta = entorno["cliente"].post("/ejecuciones", json={"documento": entorno["documento"].id})
    assert respuesta.status_code == 201, respuesta.text
    cuerpo = respuesta.json()
    assert cuerpo["documento"] == entorno["documento"].id
    assert cuerpo["estado"] == "en_curso"
    return cuerpo["id"]


# --- Fase 1 de principio a fin ---------------------------------------------------------------


def test_la_fase_1_completa_llega_por_sse(entorno):
    lista = eventos(entorno["cliente"], iniciar(entorno))

    assert [e["id"] for e in lista] == list(range(1, len(lista) + 1))
    assert (lista[0]["tipo"], lista[0]["fase"], lista[0]["estado"]) == ("fase", 1, "en_curso")
    mensajes = [e["mensaje"] for e in lista if e["tipo"] == "avance"]
    assert mensajes[0] == "Extrayendo el texto de requisitos.md"
    assert mensajes[1].startswith("Texto extraído con lectura directa")
    assert "Clasificando «3. Cuenta del cliente» (2 unidades)" in mensajes

    progresos = [e["progreso"] for e in lista if e["progreso"] is not None]
    assert progresos == sorted(progresos)
    assert progresos[-1] == 1.0

    resultado = next(e for e in lista if e["tipo"] == "resultado")["resultado"]
    assert (resultado["funcionales"], resultado["no_funcionales"]) == (2, 0)
    assert resultado["descartadas"] == 1
    assert resultado["etiquetas"] == {"autenticacion": 2}
    assert [r["id"] for r in resultado["requisitos"]] == ["RF-01", "RF-02"]

    assert [(e["tipo"], e["estado"]) for e in lista[-2:]] == [
        ("fase", "completada"),
        ("fin", "completada"),
    ]
    guardado = entorno["requisitos"] / f"{entorno['documento'].id}.modelo_requisitos.json"
    assert resultado["archivo"] == guardado.name
    assert len(json.loads(guardado.read_text(encoding="utf-8"))["requisitos"]) == 2


def test_al_reconectar_solo_llega_lo_que_faltaba(entorno):
    id_ejecucion = iniciar(entorno)
    todos = eventos(entorno["cliente"], id_ejecucion)

    assert eventos(entorno["cliente"], id_ejecucion, ultimo=3) == todos[3:]
    # Con el «fin» ya recibido, el servidor cierra el flujo sin enviar nada.
    assert eventos(entorno["cliente"], id_ejecucion, ultimo=todos[-1]["id"]) == []


def test_si_falla_el_llm_la_fase_queda_fallida_con_el_motivo(entorno):
    entorno["estado"]["llm"] = LLMSimulado(error=ErrorProveedorLLM("Groq rechazó la clave"))
    lista = eventos(entorno["cliente"], iniciar(entorno))

    assert [(e["tipo"], e["estado"], e["mensaje"]) for e in lista[-2:]] == [
        ("fase", "fallida", "Groq rechazó la clave"),
        ("fin", "fallida", "Groq rechazó la clave"),
    ]
    assert not entorno["requisitos"].exists()


def test_un_error_inesperado_no_muestra_detalles_internos(entorno):
    entorno["estado"]["llm"] = LLMSimulado(error=RuntimeError("C:\\secreto\\traza interna"))
    lista = eventos(entorno["cliente"], iniciar(entorno))

    assert lista[-1]["estado"] == "fallida"
    assert lista[-1]["mensaje"] == "Error interno del motor; revisa el log de la API"
    assert all("secreto" not in e["mensaje"] for e in lista)


def test_solo_una_ejecucion_a_la_vez(entorno):
    senal = threading.Event()
    entorno["estado"]["llm"] = LLMSimulado(esperar=senal)
    primera = iniciar(entorno)

    segunda = entorno["cliente"].post("/ejecuciones", json={"documento": entorno["documento"].id})
    assert segunda.status_code == 409
    assert primera in segunda.json()["detail"]

    senal.set()
    assert eventos(entorno["cliente"], primera)[-1]["estado"] == "completada"
    assert iniciar(entorno) != primera  # terminada la primera, se puede lanzar otra


# --- Validación de la entrada ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("cuerpo", "codigo"),
    [
        ({"documento": "0" * 32}, 404),
        ({"documento": "../../pyproject.toml"}, 422),
        ({"documento": "A" * 32}, 422),
        ({"documento": "0" * 32, "ruta": "/etc/passwd"}, 422),
        ({}, 422),
    ],
)
def test_iniciar_rechaza(entorno, cuerpo, codigo):
    assert entorno["cliente"].post("/ejecuciones", json=cuerpo).status_code == codigo


@pytest.mark.parametrize(
    ("id_ejecucion", "codigo"), [("0" * 32, 404), ("no-es-un-id", 422), ("..%2F..%2Fx", 404)]
)
def test_eventos_de_una_ejecucion_que_no_existe(entorno, id_ejecucion, codigo):
    respuesta = entorno["cliente"].get(f"/ejecuciones/{id_ejecucion}/eventos")
    assert respuesta.status_code == codigo


def test_obtener_documento_solo_acepta_ids_del_servidor(tmp_path: Path):
    documento = guardar_documento(b"hola", "a.txt", tmp_path)
    ficha, ruta = obtener_documento(tmp_path, documento.id)
    assert (ficha.id, ruta) == (documento.id, tmp_path / f"{documento.id}.txt")

    for invalido in ["../a", documento.id.upper(), documento.id + "x", "0" * 32]:
        with pytest.raises(DocumentoNoEncontrado):
            obtener_documento(tmp_path, invalido)
    (tmp_path / f"{documento.id}.txt").unlink()
    with pytest.raises(DocumentoNoEncontrado):
        obtener_documento(tmp_path, documento.id)


# --- Registro --------------------------------------------------------------------------------


def test_el_registro_descarta_las_terminadas_mas_antiguas():
    registro = RegistroEjecuciones(maximo=2)
    terminadas: list[Ejecucion] = []
    for _ in range(3):
        listo = threading.Event()
        ejecucion = registro.iniciar("d" * 32, lambda _e, listo=listo: listo.set())
        listo.wait(timeout=5)
        while not ejecucion.terminada:
            threading.Event().wait(0.01)
        terminadas.append(ejecucion)

    assert registro.obtener(terminadas[0].id) is None
    assert [registro.obtener(e.id) for e in terminadas[1:]] == terminadas[1:]
