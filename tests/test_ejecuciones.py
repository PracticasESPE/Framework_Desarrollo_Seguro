"""Ejecuciones de la fase 1 desde la API y su progreso con Server-Sent Events.

El LLM se simula, como en test_clasificacion: las pruebas no gastan cuota ni dependen de la red.
El documento es Markdown, que se lee sin Docling, para que la fase 1 tarde milisegundos.
"""

import json
import os
import re
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from orchestrator.api import (
    app,
    carpeta_documentos,
    carpeta_requisitos,
    fabrica_llm,
    registrador_neo4j,
    registro_ejecuciones,
)
from orchestrator.documentos import DocumentoNoEncontrado, guardar_documento, obtener_documento
from orchestrator.ejecuciones import Ejecucion, RegistroEjecuciones
from orchestrator.knowledge import ErrorGrafo
from orchestrator.llm import ErrorLimiteLLM, ErrorProveedorLLM, ProveedorEnCadena

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
    # Neo4j simulado: las pruebas no dependen de que esté levantado ni escriben en el real.
    registrados: list = []

    def registrar(modelo):
        if estado.get("neo4j_caido"):
            raise ErrorGrafo("No se pudo conectar con Neo4j en bolt://localhost:7687.")
        registrados.append(modelo)
        return "ej-20261111-000000-abcdef"

    estado["registrados"] = registrados
    app.dependency_overrides[registrador_neo4j] = lambda: registrar
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


# --- Estado, cancelación y resultado (#53) ----------------------------------------------------


def test_la_creacion_indica_donde_consultar_el_estado(entorno):
    respuesta = entorno["cliente"].post("/ejecuciones", json={"documento": entorno["documento"].id})
    cuerpo = respuesta.json()
    assert respuesta.headers["location"] == f"/ejecuciones/{cuerpo['id']}"
    assert cuerpo["nombre_documento"] == "requisitos.md"
    assert cuerpo["cancelacion_pedida"] is False
    eventos(entorno["cliente"], cuerpo["id"])


def test_estado_de_cada_fase_al_terminar(entorno):
    id_ejecucion = iniciar(entorno)
    todos = eventos(entorno["cliente"], id_ejecucion)

    detalle = entorno["cliente"].get(f"/ejecuciones/{id_ejecucion}").json()
    assert (detalle["estado"], detalle["fase_actual"], detalle["progreso"]) == (
        "completada",
        1,
        1.0,
    )
    assert detalle["mensaje"] == "Ejecución completada"
    assert detalle["eventos"] == len(todos)
    assert detalle["fin"] is not None
    assert [f["numero"] for f in detalle["fases"]] == list(range(1, 12))
    fase1, *resto = detalle["fases"]
    assert fase1["estado"] == "completada"
    assert fase1["mensaje"].startswith("2 requisitos identificados")
    assert {f["estado"] for f in resto} == {"pendiente"}
    assert [f["numero"] for f in resto if f["es_gate"]] == [4, 8, 11]
    assert [r["id"] for r in detalle["resultado"]["requisitos"]] == ["RF-01", "RF-02"]


def test_estado_mientras_se_ejecuta_y_filtro_por_estado(entorno):
    senal = threading.Event()
    entorno["estado"]["llm"] = LLMSimulado(esperar=senal)
    id_ejecucion = iniciar(entorno)
    cliente = entorno["cliente"]

    try:
        detalle = cliente.get(f"/ejecuciones/{id_ejecucion}").json()
        assert detalle["estado"] == "en_curso"
        assert detalle["fin"] is None
        assert detalle["resultado"] is None
        assert [e["id"] for e in cliente.get("/ejecuciones?estado=en_curso").json()] == [
            id_ejecucion
        ]
        assert cliente.get("/ejecuciones?estado=completada").json() == []
    finally:
        senal.set()
    eventos(cliente, id_ejecucion)

    segunda = iniciar(entorno)
    eventos(cliente, segunda)
    assert [e["id"] for e in cliente.get("/ejecuciones").json()] == [segunda, id_ejecucion]
    assert cliente.get("/ejecuciones?estado=en_curso").json() == []
    assert cliente.get("/ejecuciones?estado=otro").status_code == 422


def test_cancelar_detiene_la_ejecucion_antes_de_la_siguiente_seccion(entorno):
    senal = threading.Event()
    llm = LLMSimulado(esperar=senal)
    entorno["estado"]["llm"] = llm
    id_ejecucion = iniciar(entorno)
    cliente = entorno["cliente"]

    respuesta = cliente.post(f"/ejecuciones/{id_ejecucion}/cancelar")
    assert respuesta.status_code == 202
    assert respuesta.json()["cancelacion_pedida"] is True
    senal.set()  # la llamada al LLM ya empezada termina; la siguiente sección no se clasifica

    lista = eventos(cliente, id_ejecucion)
    assert [(e["tipo"], e["estado"]) for e in lista[-2:]] == [
        ("fase", "cancelada"),
        ("fin", "cancelada"),
    ]
    assert lista[-1]["mensaje"] == "Ejecución cancelada a petición del usuario"
    assert not any(e["mensaje"].startswith("Clasificando «3.") for e in lista)
    assert not entorno["requisitos"].exists()

    detalle = cliente.get(f"/ejecuciones/{id_ejecucion}").json()
    assert (detalle["estado"], detalle["fases"][0]["estado"]) == ("cancelada", "cancelada")
    assert cliente.post(f"/ejecuciones/{id_ejecucion}/cancelar").status_code == 409


@pytest.mark.parametrize(
    ("ruta", "codigo"),
    [
        ("/ejecuciones/" + "0" * 32, 404),
        ("/ejecuciones/no-es-un-id", 422),
        ("/ejecuciones/" + "0" * 32 + "/cancelar", 404),
    ],
)
def test_ejecucion_que_no_existe(entorno, ruta, codigo):
    cliente = entorno["cliente"]
    respuesta = cliente.post(ruta) if ruta.endswith("cancelar") else cliente.get(ruta)
    assert respuesta.status_code == codigo


def test_requisitos_del_documento_procesado(entorno):
    cliente = entorno["cliente"]
    url = f"/documentos/{entorno['documento'].id}/requisitos"
    sin_procesar = cliente.get(url)
    assert sin_procesar.status_code == 404
    assert sin_procesar.json()["detail"] == "El documento todavía no se ha procesado"

    eventos(cliente, iniciar(entorno))
    modelo = cliente.get(url).json()
    assert modelo["documento"]["nombre"] == "requisitos.md"
    assert [r["id"] for r in modelo["requisitos"]] == ["RF-01", "RF-02"]

    archivo = entorno["requisitos"] / f"{entorno['documento'].id}.modelo_requisitos.json"
    archivo.write_text('{"version_esquema": "1.0"}', encoding="utf-8")
    roto = cliente.get(url)
    assert roto.status_code == 500
    assert "C:" not in roto.text and "Traceback" not in roto.text


@pytest.mark.parametrize(
    ("id_documento", "codigo"), [("0" * 32, 404), ("no-es-un-id", 422), ("A" * 32, 422)]
)
def test_requisitos_de_un_documento_que_no_existe(entorno, id_documento, codigo):
    respuesta = entorno["cliente"].get(f"/documentos/{id_documento}/requisitos")
    assert respuesta.status_code == codigo


def test_la_documentacion_agrupa_y_describe_los_endpoints(entorno):
    esquema = entorno["cliente"].get("/openapi.json").json()
    assert [t["name"] for t in esquema["tags"]] == ["motor", "documentos", "ejecuciones"]
    operaciones = {
        (metodo.upper(), ruta): datos
        for ruta, metodos in esquema["paths"].items()
        for metodo, datos in metodos.items()
    }
    ejecuciones = {
        clave for clave, datos in operaciones.items() if datos["tags"] == ["ejecuciones"]
    }
    assert ejecuciones == {
        ("POST", "/ejecuciones"),
        ("GET", "/ejecuciones"),
        ("GET", "/ejecuciones/{id_ejecucion}"),
        ("POST", "/ejecuciones/{id_ejecucion}/cancelar"),
        ("GET", "/ejecuciones/{id_ejecucion}/eventos"),
    }
    assert all(datos.get("summary") for datos in operaciones.values())
    assert {"404", "409"} <= set(operaciones[("POST", "/ejecuciones")]["responses"])
    assert "text/event-stream" in str(operaciones[("GET", "/ejecuciones/{id_ejecucion}/eventos")])


class LLMSinCuota:
    """Siempre rechaza por límite de uso, como Groq al agotar el plan gratuito."""

    nombre = "sin cuota"

    def __init__(self) -> None:
        self.llamado = threading.Event()

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        self.llamado.set()
        raise ErrorProveedorLLM("groq: límite de peticiones alcanzado")


def test_cancelar_corta_la_espera_por_el_limite_de_uso_del_llm(entorno):
    llm = LLMSinCuota()
    entorno["estado"]["llm"] = llm
    id_ejecucion = iniciar(entorno)
    cliente = entorno["cliente"]
    assert llm.llamado.wait(timeout=5)

    # La clasificación espera 20 s antes de reintentar; se avisa y la cancelación no espera.
    detalle = cliente.get(f"/ejecuciones/{id_ejecucion}").json()
    for _ in range(50):
        if "límite de uso" in (detalle["mensaje"] or ""):
            break
        threading.Event().wait(0.02)
        detalle = cliente.get(f"/ejecuciones/{id_ejecucion}").json()
    assert detalle["mensaje"] == (
        "El proveedor del LLM alcanzó su límite de uso: se reintenta en 20 s"
    )

    inicio = time.monotonic()
    assert cliente.post(f"/ejecuciones/{id_ejecucion}/cancelar").status_code == 202
    lista = eventos(cliente, id_ejecucion)
    assert time.monotonic() - inicio < 5
    assert (lista[-1]["tipo"], lista[-1]["estado"]) == ("fin", "cancelada")


class LLMAgotado:
    nombre = "groq"

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        raise ErrorLimiteLLM("groq: cuota diaria agotada; se renueva en 7 min", 432, diario=True)


def test_el_progreso_muestra_el_respaldo_y_el_uso_del_llm(entorno):
    entorno["estado"]["llm"] = ProveedorEnCadena([LLMAgotado(), LLMSimulado()])
    lista = eventos(entorno["cliente"], iniciar(entorno))

    mensajes = [e["mensaje"] for e in lista]
    assert "groq: cuota diaria agotada; se renueva en 7 min: la sección pasa a simulado" in mensajes
    assert any(m.startswith("Uso del LLM: ") for m in mensajes)
    assert lista[-1]["estado"] == "completada"


# --- Registro automático en Neo4j ------------------------------------------------------------


def test_al_terminar_la_fase_1_los_requisitos_se_registran_en_neo4j(entorno):
    id_ejecucion = iniciar(entorno)
    lista = eventos(entorno["cliente"], id_ejecucion)

    mensajes = [e["mensaje"] for e in lista]
    registro = mensajes.index(
        "Requisitos registrados en Neo4j: 2 (ejecución ej-20261111-000000-abcdef)"
    )
    resultado = next(i for i, e in enumerate(lista) if e["tipo"] == "resultado")
    assert mensajes[registro - 1] == "Registrando los requisitos en Neo4j"
    assert registro < resultado  # el resultado ya lleva la ejecución de Neo4j
    assert lista[resultado]["resultado"]["ejecucion_neo4j"] == "ej-20261111-000000-abcdef"
    assert lista[-1]["estado"] == "completada"

    (modelo,) = entorno["estado"]["registrados"]
    assert [r.id for r in modelo.requisitos] == ["RF-01", "RF-02"]
    assert modelo.documento.nombre == "requisitos.md"
    detalle = entorno["cliente"].get(f"/ejecuciones/{id_ejecucion}").json()
    assert detalle["resultado"]["ejecucion_neo4j"] == "ej-20261111-000000-abcdef"


def test_si_neo4j_no_esta_la_fase_1_termina_igual_y_lo_avisa(entorno):
    entorno["estado"]["neo4j_caido"] = True
    lista = eventos(entorno["cliente"], iniciar(entorno))

    aviso = next(e["mensaje"] for e in lista if e["mensaje"].startswith("No se registraron"))
    assert "No se pudo conectar con Neo4j" in aviso
    assert "«framework requisitos registrar»" in aviso
    resultado = next(e["resultado"] for e in lista if e["tipo"] == "resultado")
    assert resultado["ejecucion_neo4j"] is None
    assert lista[-1]["estado"] == "completada"
    assert (entorno["requisitos"] / f"{entorno['documento'].id}.modelo_requisitos.json").exists()


def test_un_error_inesperado_de_neo4j_no_pierde_la_clasificacion(entorno):
    def registrar(_modelo):
        raise RuntimeError(r"C:\interno\traza con detalles")

    app.dependency_overrides[registrador_neo4j] = lambda: registrar
    lista = eventos(entorno["cliente"], iniciar(entorno))

    mensajes = [e["mensaje"] for e in lista]
    assert any(m.startswith("No se registraron en Neo4j por un error interno") for m in mensajes)
    assert all("traza con detalles" not in m for m in mensajes)
    assert lista[-1]["estado"] == "completada"


@pytest.mark.parametrize("motivo", ["llm", "cancelacion"])
def test_no_se_registra_si_la_fase_1_no_termina(entorno, motivo):
    if motivo == "llm":
        entorno["estado"]["llm"] = LLMSimulado(error=ErrorProveedorLLM("groq: caído"))
        lista = eventos(entorno["cliente"], iniciar(entorno))
    else:
        senal = threading.Event()
        entorno["estado"]["llm"] = LLMSimulado(esperar=senal)
        id_ejecucion = iniciar(entorno)
        entorno["cliente"].post(f"/ejecuciones/{id_ejecucion}/cancelar")
        senal.set()
        lista = eventos(entorno["cliente"], id_ejecucion)
    assert lista[-1]["estado"] in ("fallida", "cancelada")
    assert entorno["estado"]["registrados"] == []
    assert not any("Neo4j" in e["mensaje"] for e in lista)


def test_sin_registrador_no_se_intenta_neo4j(entorno):
    app.dependency_overrides[registrador_neo4j] = lambda: None
    lista = eventos(entorno["cliente"], iniciar(entorno))
    assert not any("Neo4j" in e["mensaje"] for e in lista)
    resultado = next(e["resultado"] for e in lista if e["tipo"] == "resultado")
    assert resultado["ejecucion_neo4j"] is None


@pytest.mark.integracion
@pytest.mark.skipif(
    os.environ.get("NEO4J_INTEGRACION") != "1",
    reason="Requiere Neo4j levantado y NEO4J_INTEGRACION=1",
)
def test_integracion_registrar_en_neo4j():
    """Con Neo4j de verdad: lo que registra la fase 1 se lee con «requisitos listar»."""
    from orchestrator.config import obtener_configuracion
    from orchestrator.ejecuciones import registrar_en_neo4j
    from orchestrator.knowledge import conectar, listar_requisitos
    from tests.test_arquitectura import _modelo

    ejecucion_id = registrar_en_neo4j(_modelo())
    config = obtener_configuracion()
    driver = conectar(config)
    try:
        filas = listar_requisitos(driver, ejecucion_id, config.neo4j_database)
        assert [f["id"] for f in filas] == ["RF-01", "RF-02", "RF-03", "RNF-01"]
    finally:
        driver.execute_query(
            "MATCH (n) WHERE n.id = $id OR n.ejecucion_id = $id DETACH DELETE n",
            {"id": ejecucion_id},
            database_=config.neo4j_database,
        )
        driver.close()
