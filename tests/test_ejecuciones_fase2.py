"""Fase 2 desde la API: el ciclo LLM ↔ OPA, los ADR y el diagrama C4 con progreso por SSE.

El LLM y Neo4j se simulan, como en test_ejecuciones. Las pruebas que consultan a OPA usan el
ejecutable real y se omiten si no está instalado.
"""

import json
import shutil
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orchestrator import opa
from orchestrator.api import (
    app,
    carpeta_arquitectura,
    carpeta_documentos,
    carpeta_requisitos,
    fabrica_llm,
    registrador_decisiones,
    registrador_neo4j,
    registro_ejecuciones,
)
from orchestrator.architecture import PropuestaArquitectura
from orchestrator.documentos import guardar_documento
from orchestrator.ejecuciones import RegistroEjecuciones
from orchestrator.knowledge import ErrorGrafo
from orchestrator.llm import ErrorProveedorLLM
from tests.test_arquitectura import _servicio
from tests.test_ejecuciones import TEXTO, LLMSimulado, eventos

con_opa = pytest.mark.skipif(shutil.which("opa") is None, reason="Requiere el ejecutable opa")

DECISION = {
    "id": "D-01",
    "titulo": "Usuarios y pedidos separados",
    "decision": "Separar el registro de clientes de la gestión de pedidos.",
    "justificacion": "Cada uno cambia por motivos distintos (RF-01 y RF-02).",
    "requisitos": ["RF-01", "RF-02"],
}


def _propuesta(base_compartida: bool = False) -> PropuestaArquitectura:
    pedidos = _servicio("pedidos", ["RF-02"], [("usuarios", "sincrona")])
    if base_compartida:
        pedidos = pedidos | {"base_datos": "usuarios_db"}  # OPA: Database per Service
    return PropuestaArquitectura.model_validate(
        {
            "servicios": [_servicio("usuarios", ["RF-01"]), pedidos],
            "transversales": [],
            "decisiones": [DECISION],
        }
    )


class LLMFases:
    """Clasifica como en la fase 1, propone las arquitecturas dadas y no redacta ADR (plantilla)."""

    nombre = "simulado"

    def __init__(self, *propuestas: PropuestaArquitectura, esperar: threading.Event | None = None):
        self.clasificador = LLMSimulado()
        self.propuestas = list(propuestas)
        self.prompts: list[str] = []
        self.esperar = esperar

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        if esquema is PropuestaArquitectura:
            self.prompts.append(prompt)
            if self.esperar is not None:
                self.esperar.wait(timeout=10)
            return self.propuestas.pop(0)
        if esquema.__name__ == "RedaccionADR":
            raise ErrorProveedorLLM("sin cuota en la prueba")
        return self.clasificador.generar_estructurado(prompt, esquema, nivel, sistema)


@pytest.fixture
def entorno(tmp_path: Path):
    estado: dict = {"llm": LLMFases(_propuesta()), "decisiones": [], "neo4j_caido": False}
    documentos = tmp_path / "documentos"
    requisitos = tmp_path / "requisitos"
    arquitectura = tmp_path / "arquitectura"
    app.dependency_overrides[carpeta_documentos] = lambda: documentos
    app.dependency_overrides[carpeta_requisitos] = lambda: requisitos
    app.dependency_overrides[carpeta_arquitectura] = lambda: arquitectura
    registro = RegistroEjecuciones()
    app.dependency_overrides[registro_ejecuciones] = lambda: registro
    app.dependency_overrides[fabrica_llm] = lambda: lambda: estado["llm"]
    app.dependency_overrides[registrador_neo4j] = lambda: lambda modelo: "ej-fase1"

    def registrar_decisiones(modelo, resultado):
        if estado["neo4j_caido"]:
            raise ErrorGrafo("No se pudo conectar con Neo4j en bolt://localhost:7687.")
        estado["decisiones"].append(resultado)
        return "ej-fase1", len(resultado.final.arquitectura.decisiones)

    app.dependency_overrides[registrador_decisiones] = lambda: registrar_decisiones
    documento = guardar_documento(TEXTO.encode("utf-8"), "requisitos.md", documentos)
    yield {
        "cliente": TestClient(app),
        "documento": documento,
        "requisitos": requisitos,
        "arquitectura": arquitectura,
        "estado": estado,
    }
    app.dependency_overrides.clear()


def lanzar(entorno, fase: int) -> str:
    cuerpo = {"documento": entorno["documento"].id, "fase": fase}
    respuesta = entorno["cliente"].post("/ejecuciones", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["id"]


def fase_1(entorno) -> None:
    lista = eventos(entorno["cliente"], lanzar(entorno, 1))
    assert lista[-1]["estado"] == "completada"


def fase_2(entorno) -> list[dict]:
    return eventos(entorno["cliente"], lanzar(entorno, 2))


def resultado_de(lista: list[dict]) -> dict:
    return next(e for e in lista if e["tipo"] == "resultado")["arquitectura"]


# --- La fase 2 no arranca sola ------------------------------------------------------------------


def test_la_fase_1_no_llama_al_llm_de_arquitectura(entorno):
    fase_1(entorno)

    assert entorno["estado"]["llm"].prompts == []
    assert not entorno["arquitectura"].exists()
    detalle = entorno["cliente"].get("/ejecuciones").json()
    assert [e["fase_actual"] for e in detalle] == [1]


def test_sin_la_fase_1_no_se_puede_proponer_la_arquitectura(entorno):
    respuesta = entorno["cliente"].post(
        "/ejecuciones", json={"documento": entorno["documento"].id, "fase": 2}
    )

    assert respuesta.status_code == 409
    assert "Falta la fase 1" in respuesta.json()["detail"]
    assert entorno["estado"]["llm"].prompts == []


@pytest.mark.parametrize("fase", [0, 4, "2", None])
def test_solo_existen_las_fases_1_a_3_en_el_motor(entorno, fase):
    cuerpo = {"documento": entorno["documento"].id, "fase": fase}
    assert entorno["cliente"].post("/ejecuciones", json=cuerpo).status_code == 422


def test_sin_indicar_la_fase_se_lanza_la_1(entorno):
    respuesta = entorno["cliente"].post("/ejecuciones", json={"documento": entorno["documento"].id})
    assert respuesta.status_code == 201
    eventos(entorno["cliente"], respuesta.json()["id"])
    assert entorno["requisitos"].exists()
    assert entorno["estado"]["llm"].prompts == []


# --- Fase 2 de principio a fin -------------------------------------------------------------------


@con_opa
def test_la_fase_2_completa_llega_por_sse(entorno):
    fase_1(entorno)
    id_ejecucion = lanzar(entorno, 2)
    lista = eventos(entorno["cliente"], id_ejecucion)

    assert (lista[0]["tipo"], lista[0]["fase"], lista[0]["estado"]) == ("fase", 2, "en_curso")
    assert [e["id"] for e in lista] == list(range(1, len(lista) + 1))
    progresos = [e["progreso"] for e in lista if e["progreso"] is not None]
    assert progresos == sorted(progresos)
    assert progresos[-1] == 1.0
    assert all(e["fase"] == 2 for e in lista if e["tipo"] != "fin")
    mensajes = [e["mensaje"] for e in lista if e["tipo"] == "avance"]
    assert any("Pidiendo al LLM la arquitectura (intento 1 de 3)" in m for m in mensajes)
    assert any(m.startswith("Intento 1: OPA aprueba") for m in mensajes)
    assert any("Decisiones registradas en Neo4j: 1 (ejecución ej-fase1)" in m for m in mensajes)
    assert any(m.startswith("Diagrama C4 escrito en") for m in mensajes)
    assert [(e["tipo"], e["estado"]) for e in lista[-2:]] == [
        ("fase", "completada"),
        ("fin", "completada"),
    ]

    resumen = resultado_de(lista)
    assert resumen["aprobada"] is True
    assert [i["aprobado"] for i in resumen["intentos"]] == [True]
    assert [s["nombre"] for s in resumen["servicios"]] == ["usuarios", "pedidos"]
    assert [(d["servicio"], d["tipo"]) for d in resumen["servicios"][1]["depende_de"]] == [
        ("usuarios", "sincrona")
    ]
    assert resumen["etiquetas_transversales"] == []
    assert [d["id"] for d in resumen["decisiones"]] == ["D-01"]
    assert resumen["ejecucion_neo4j"] == "ej-fase1"
    assert resumen["decisiones_neo4j"] == 1
    assert len(resumen["adr"]) >= 1
    assert all("plantilla del motor" in a["redactado_por"] for a in resumen["adr"])
    assert "```mermaid" in resumen["diagrama"]

    carpeta = entorno["arquitectura"]
    base = entorno["documento"].id
    assert resumen["archivo_arquitectura"] == f"{base}.arquitectura.json"
    guardada = json.loads((carpeta / resumen["archivo_arquitectura"]).read_text(encoding="utf-8"))
    assert [s["nombre"] for s in guardada["servicios"]] == ["usuarios", "pedidos"]
    assert json.loads((carpeta / resumen["archivo_intentos"]).read_text(encoding="utf-8"))[
        "aprobada"
    ]
    assert (carpeta / f"{base}.arquitectura.md").read_text(encoding="utf-8") == resumen["diagrama"]
    escritos = sorted(p.name for p in (carpeta / resumen["carpeta_adr"]).glob("*.md"))
    assert escritos == sorted([a["archivo"] for a in resumen["adr"]] + ["README.md"])
    assert len(entorno["estado"]["llm"].prompts) == 1  # una sola llamada de razonamiento

    detalle = entorno["cliente"].get(f"/ejecuciones/{id_ejecucion}").json()
    assert detalle["estado"] == "completada"
    assert detalle["arquitectura"]["aprobada"] is True
    assert detalle["resultado"] is None
    fases = {f["numero"]: f["estado"] for f in detalle["fases"]}
    assert (fases[1], fases[2]) == ("pendiente", "completada")  # la fase 1 fue otra ejecución


@con_opa
def test_los_motivos_de_opa_vuelven_al_llm_y_el_segundo_intento_se_aprueba(entorno):
    entorno["estado"]["llm"] = LLMFases(_propuesta(base_compartida=True), _propuesta())
    fase_1(entorno)
    lista = fase_2(entorno)

    resumen = resultado_de(lista)
    assert resumen["aprobada"] is True
    assert [i["aprobado"] for i in resumen["intentos"]] == [False, True]
    assert "comparten la base de datos usuarios_db" in resumen["intentos"][0]["bloqueantes"][0]
    mensajes = [e["mensaje"] for e in lista if e["tipo"] == "avance"]
    assert any(
        m.startswith("OPA rechaza: Los servicios pedidos, usuarios comparten") for m in mensajes
    )
    assert any("(intento 2 de 3) con los motivos de OPA" in m for m in mensajes)
    prompts = entorno["estado"]["llm"].prompts
    assert "comparten la base de datos usuarios_db" in prompts[1]
    assert "Tu propuesta anterior se rechazó" not in prompts[0]


@con_opa
def test_si_opa_no_aprueba_nada_la_fase_falla_y_queda_para_revision(entorno):
    rechazada = _propuesta(base_compartida=True)
    entorno["estado"]["llm"] = LLMFases(rechazada, rechazada, rechazada)
    fase_1(entorno)
    lista = fase_2(entorno)

    mensaje = "OPA no aprobó ninguna propuesta en 3 intentos: la arquitectura queda para revisión"
    assert lista[-1]["estado"] == "fallida"
    assert lista[-1]["mensaje"].startswith(mensaje)
    assert [(e["tipo"], e["estado"]) for e in lista[-2:]] == [
        ("fase", "fallida"),
        ("fin", "fallida"),
    ]
    resumen = resultado_de(lista)
    assert resumen["aprobada"] is False
    assert [i["aprobado"] for i in resumen["intentos"]] == [False, False, False]
    assert resumen["servicios"] and resumen["decisiones"]  # la última propuesta, para revisarla
    assert resumen["adr"] == [] and resumen["diagrama"] is None
    carpeta = entorno["arquitectura"]
    assert (carpeta / resumen["archivo_intentos"]).is_file()
    assert sorted(p.name for p in carpeta.iterdir()) == [resumen["archivo_intentos"]]
    assert len(entorno["estado"]["llm"].prompts) == 3
    assert len(entorno["estado"]["decisiones"]) == 1  # las decisiones rechazadas también quedan


@con_opa
def test_si_neo4j_no_esta_la_fase_2_termina_igual(entorno):
    entorno["estado"]["neo4j_caido"] = True
    fase_1(entorno)
    lista = fase_2(entorno)

    assert lista[-1]["estado"] == "completada"
    assert any(
        e["mensaje"].startswith("No se registraron en Neo4j: No se pudo conectar") for e in lista
    )
    resumen = resultado_de(lista)
    assert resumen["aprobada"] and resumen["ejecucion_neo4j"] is None


# --- Fallos y cancelación ----------------------------------------------------------------------


def test_si_opa_no_esta_instalado_se_explica_en_la_fase(entorno, monkeypatch):
    monkeypatch.setattr(opa.shutil, "which", lambda _nombre: None)
    fase_1(entorno)
    lista = fase_2(entorno)

    assert lista[-1]["estado"] == "fallida"
    assert "No se encontró OPA" in lista[-1]["mensaje"]
    assert not any(e["tipo"] == "resultado" for e in lista)


def test_si_falla_el_llm_la_fase_2_queda_fallida_con_el_motivo(entorno):
    class Caido(LLMFases):
        def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
            if esquema is PropuestaArquitectura:
                raise ErrorProveedorLLM("Groq rechazó la clave")
            return super().generar_estructurado(prompt, esquema, nivel, sistema)

    entorno["estado"]["llm"] = Caido()
    fase_1(entorno)
    lista = fase_2(entorno)

    assert [(e["tipo"], e["estado"], e["mensaje"]) for e in lista[-2:]] == [
        ("fase", "fallida", "Groq rechazó la clave"),
        ("fin", "fallida", "Groq rechazó la clave"),
    ]
    assert not entorno["arquitectura"].exists()


def test_un_modelo_de_requisitos_corrupto_no_se_propone(entorno):
    fase_1(entorno)
    modelo = entorno["requisitos"] / f"{entorno['documento'].id}.modelo_requisitos.json"
    modelo.write_text('{"requisitos": "C:\\\\secreto"}', encoding="utf-8")
    lista = fase_2(entorno)

    assert lista[-1]["estado"] == "fallida"
    assert "no es válido" in lista[-1]["mensaje"]
    assert "secreto" not in lista[-1]["mensaje"]
    assert entorno["estado"]["llm"].prompts == []


@con_opa
def test_cancelar_en_la_fase_2_no_deja_arquitectura_a_medias(entorno):
    senal = threading.Event()
    entorno["estado"]["llm"] = LLMFases(_propuesta(), esperar=senal)
    fase_1(entorno)
    id_ejecucion = lanzar(entorno, 2)
    cliente = entorno["cliente"]

    try:
        assert cliente.post(f"/ejecuciones/{id_ejecucion}/cancelar").status_code == 202
    finally:
        senal.set()
    lista = eventos(cliente, id_ejecucion)

    assert (lista[-1]["tipo"], lista[-1]["estado"]) == ("fin", "cancelada")
    assert not entorno["arquitectura"].exists()
    assert not any(e["tipo"] == "resultado" for e in lista)


def test_solo_una_ejecucion_a_la_vez_tambien_con_la_fase_2(entorno):
    senal = threading.Event()
    entorno["estado"]["llm"] = LLMFases(_propuesta(), esperar=senal)
    fase_1(entorno)
    primera = lanzar(entorno, 2)

    try:
        segunda = entorno["cliente"].post(
            "/ejecuciones", json={"documento": entorno["documento"].id, "fase": 2}
        )
        assert segunda.status_code == 409
        assert primera in segunda.json()["detail"]
    finally:
        senal.set()
        eventos(entorno["cliente"], primera)
