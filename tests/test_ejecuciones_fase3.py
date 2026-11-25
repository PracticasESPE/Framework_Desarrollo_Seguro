"""Fase 3 desde la API: POST /ejecuciones con `fase: 3` y su seguimiento por SSE.

Los requisitos (fase 1) y la arquitectura aprobada (fase 2) se escriben directamente en disco. El
LLM se simula y no se compila (la compilación real la cubre orchestrator/generation/sistema.py).
"""

from __future__ import annotations

import functools
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import orchestrator.api as api
from orchestrator.api import (
    app,
    carpeta_arquitectura,
    carpeta_documentos,
    carpeta_requisitos,
    carpeta_servicios,
    fabrica_contexto,
    fabrica_llm,
    registro_ejecuciones,
)
from orchestrator.documentos import guardar_documento
from orchestrator.ejecuciones import (
    RegistroEjecuciones,
    nombre_arquitectura,
    nombre_modelo_requisitos,
)
from orchestrator.llm.prompts import contexto_vacio
from tests.test_arquitectura import _modelo
from tests.test_ejecuciones import TEXTO, eventos
from tests.test_parametros_estructura import _tienda
from tests.test_sistema_fase3 import LLMSimulado


@pytest.fixture
def entorno(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    estado: dict = {"llm": LLMSimulado(), "contexto": None}
    carpetas = {n: tmp_path / n for n in ("documentos", "requisitos", "arquitectura", "servicios")}
    app.dependency_overrides[carpeta_documentos] = lambda: carpetas["documentos"]
    app.dependency_overrides[carpeta_requisitos] = lambda: carpetas["requisitos"]
    app.dependency_overrides[carpeta_arquitectura] = lambda: carpetas["arquitectura"]
    app.dependency_overrides[carpeta_servicios] = lambda: carpetas["servicios"]
    registro = RegistroEjecuciones()
    app.dependency_overrides[registro_ejecuciones] = lambda: registro
    app.dependency_overrides[fabrica_llm] = lambda: lambda: estado["llm"]
    app.dependency_overrides[fabrica_contexto] = lambda: estado["contexto"]
    # Sin npm ni tsc: la API real compila.
    monkeypatch.setattr(api, "trabajo_fase3", functools.partial(api.trabajo_fase3, compilar=False))
    documento = guardar_documento(TEXTO.encode("utf-8"), "requisitos.md", carpetas["documentos"])
    yield {"cliente": TestClient(app), "documento": documento, "estado": estado, **carpetas}
    app.dependency_overrides.clear()


def _fase_1_y_2(entorno) -> None:
    for carpeta, nombre, contenido in (
        (entorno["requisitos"], nombre_modelo_requisitos, _modelo().model_dump_json()),
        (entorno["arquitectura"], nombre_arquitectura, _tienda().model_dump_json()),
    ):
        carpeta.mkdir(parents=True, exist_ok=True)
        (carpeta / nombre(entorno["documento"].id)).write_text(contenido, encoding="utf-8")


def _lanzar(entorno) -> tuple[str, list[dict]]:
    cuerpo = {"documento": entorno["documento"].id, "fase": 3}
    respuesta = entorno["cliente"].post("/ejecuciones", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    id_ejecucion = respuesta.json()["id"]
    return id_ejecucion, eventos(entorno["cliente"], id_ejecucion)


def _servicios(lista: list[dict]) -> dict:
    return next(e for e in lista if e["tipo"] == "resultado")["servicios"]


def test_sin_la_fase_1_no_se_generan_servicios(entorno):
    respuesta = entorno["cliente"].post(
        "/ejecuciones", json={"documento": entorno["documento"].id, "fase": 3}
    )
    assert respuesta.status_code == 409
    assert "Falta la fase 1" in respuesta.json()["detail"]


def test_sin_la_arquitectura_aprobada_no_se_generan_servicios(entorno):
    entorno["requisitos"].mkdir(parents=True)
    (entorno["requisitos"] / nombre_modelo_requisitos(entorno["documento"].id)).write_text(
        _modelo().model_dump_json(), encoding="utf-8"
    )
    respuesta = entorno["cliente"].post(
        "/ejecuciones", json={"documento": entorno["documento"].id, "fase": 3}
    )
    assert respuesta.status_code == 409
    assert "Falta la fase 2" in respuesta.json()["detail"]


def test_genera_los_servicios_y_publica_el_resultado(entorno):
    _fase_1_y_2(entorno)
    id_ejecucion, lista = _lanzar(entorno)

    assert lista[0] == lista[0] | {"tipo": "fase", "fase": 3, "estado": "en_curso"}
    assert lista[-1]["tipo"] == "fin" and lista[-1]["estado"] == "completada"
    avances = [e["mensaje"] for e in lista if e["tipo"] == "avance"]
    assert avances[0] == "Arquitectura cargada: 3 servicios y 4 requisitos"
    assert any(m.startswith("pedidos (2/3): lógica de negocio de pedido") for m in avances)
    resultado = _servicios(lista)
    assert resultado["completos"] == 3
    assert [s["servicio"] for s in resultado["servicios"]] == [
        "usuarios",
        "pedidos",
        "notificaciones",
    ]
    assert all(s["completo"] for s in resultado["servicios"])
    # La carpeta se muestra sin la ruta de la máquina, y cada ejecución usa una nueva.
    carpeta = resultado["carpeta"]
    assert carpeta.startswith(f"{entorno['documento'].id}-") and "/" not in carpeta
    assert (entorno["servicios"] / carpeta / "pedidos" / "src" / "pedido.service.ts").is_file()

    detalle = entorno["cliente"].get(f"/ejecuciones/{id_ejecucion}").json()
    assert detalle["fase_actual"] == 3 and detalle["servicios"]["completos"] == 3
    fase3 = next(f for f in detalle["fases"] if f["numero"] == 3)
    assert fase3["estado"] == "completada"


def test_un_servicio_que_falla_queda_en_el_resultado(entorno):
    _fase_1_y_2(entorno)
    entorno["estado"]["llm"] = LLMSimulado(falla_en="pedidos")
    _, lista = _lanzar(entorno)

    assert lista[-1]["estado"] == "completada"
    resultado = _servicios(lista)
    assert resultado["completos"] == 2
    pedidos = resultado["servicios"][1]
    assert not pedidos["completo"] and pedidos["error"] == "El proveedor no respondió"


def test_si_ningun_servicio_se_completa_la_fase_falla(entorno):
    _fase_1_y_2(entorno)

    class SinRespuesta(LLMSimulado):
        def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
            from orchestrator.llm import ErrorLLM

            raise ErrorLLM("Cuota agotada")

    entorno["estado"]["llm"] = SinRespuesta()
    _, lista = _lanzar(entorno)

    assert lista[-1]["estado"] == "fallida"
    assert lista[-1]["mensaje"].startswith("Ningún servicio se completó: 0 de 3")
    assert _servicios(lista)["completos"] == 0  # el detalle llega igual al dashboard


def test_usa_el_contexto_de_graphrag_y_cierra_neo4j(entorno):
    _fase_1_y_2(entorno)
    cerrado = []
    consultados = []

    def crear():
        def contexto_de(servicio):
            consultados.append(servicio.nombre)
            return contexto_vacio()

        return contexto_de, lambda: cerrado.append(True)

    entorno["estado"]["contexto"] = crear
    _, lista = _lanzar(entorno)

    assert lista[-1]["estado"] == "completada"
    assert consultados == ["usuarios", "pedidos", "notificaciones"]
    assert cerrado == [True]
    assert any(e["mensaje"] == "Contexto de seguridad: GraphRAG sobre Neo4j" for e in lista)


def test_sin_neo4j_sigue_sin_contexto(entorno):
    _fase_1_y_2(entorno)

    def crear():
        raise ConnectionError("Neo4j no responde")

    entorno["estado"]["contexto"] = crear
    _, lista = _lanzar(entorno)

    assert lista[-1]["estado"] == "completada"
    assert any("Sin contexto GraphRAG" in e["mensaje"] for e in lista)
