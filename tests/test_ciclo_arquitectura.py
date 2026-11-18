"""Ciclo LLM ↔ OPA de la fase 2, registro de intentos y nodos Decision en Neo4j.

El LLM se simula. Las pruebas del comando usan el OPA real (se omiten si no está instalado) y las
de Neo4j un driver simulado; la de integración necesita Neo4j y NEO4J_INTEGRACION=1.
"""

import json
import os
import shutil

import pytest
from typer.testing import CliRunner

from orchestrator.architecture import (
    Arquitectura,
    ResultadoCiclo,
    ciclo_llm_opa,
    construir_arquitectura,
)
from orchestrator.architecture.validacion import (
    Criterio,
    DecisionArquitectura,
    Motivo,
    PatronInferido,
)
from orchestrator.cli import app
from orchestrator.config import obtener_configuracion
from orchestrator.knowledge import ErrorGrafo, conectar, crear_ejecucion, registrar_requisitos
from orchestrator.knowledge.registro import (
    decisiones_del_ciclo,
    ejecucion_de_documento,
    listar_decisiones,
    registrar_decisiones,
)
from orchestrator.llm import ErrorProveedorLLM
from tests.test_arquitectura import LLMSimulado, _modelo, _propuesta, _servicio
from tests.test_registro import DriverSimulado

runner = CliRunner()
con_opa = pytest.mark.skipif(shutil.which("opa") is None, reason="Requiere el ejecutable opa")

CRITERIOS = [
    "arquitectura.base_datos_propia",
    "arquitectura.sin_ciclos",
    "arquitectura.dependencias_conocidas",
    "arquitectura.servicios_unicos",
]


def _arquitectura(**cambios) -> Arquitectura:
    return construir_arquitectura(_propuesta(**cambios), _modelo())


def _base_compartida() -> Arquitectura:
    """pedidos usa la base de usuarios: OPA la rechaza (Database per Service)."""
    servicios = [
        _servicio("usuarios", ["RF-01"]),
        _servicio("pedidos", ["RF-02"], [("usuarios", "sincrona")]) | {"base_datos": "usuarios_db"},
        _servicio("notificaciones", ["RF-03"], [("pedidos", "asincrona")]),
    ]
    return _arquitectura(servicios=servicios)


def _decision(aprobado: bool) -> DecisionArquitectura:
    bloqueantes = (
        []
        if aprobado
        else [Motivo(regla="arquitectura.sin_ciclos", motivo="Dependencias circulares entre a, b")]
    )
    return DecisionArquitectura(
        aprobado=aprobado,
        bloqueantes=bloqueantes,
        advertencias=[],
        criterios=[
            Criterio(regla=r, cumple=aprobado or r != "arquitectura.sin_ciclos", detalle="d")
            for r in CRITERIOS
        ],
        rasgos=[],
        patrones=(
            [
                PatronInferido(
                    id="arq.gateway.001",
                    patron="api_gateway",
                    implementacion="traefik",
                    controles=["ASVS-V4.1.1"],
                    cwe=["CWE-284"],
                    por=["autenticacion_centralizada"],
                    motivo="Hay requisitos de autenticación y varios servicios",
                )
            ]
            if aprobado
            else []
        ),
        justificacion="Arquitectura aprobada" if aprobado else "Arquitectura rechazada",
    )


class Propuestas:
    """Doble de proponer_arquitectura: devuelve propuestas fijas y guarda los motivos recibidos."""

    def __init__(self, *arquitecturas):
        self.arquitecturas = list(arquitecturas)
        self.motivos: list[list[str] | None] = []

    def __call__(self, modelo, llm, nivel="razonamiento", retroalimentacion=None):
        self.motivos.append(retroalimentacion)
        return self.arquitecturas.pop(0)


def _validar_por_turnos(*aprobados):
    pendientes = list(aprobados)
    return lambda arquitectura: _decision(pendientes.pop(0))


# --- Ciclo -------------------------------------------------------------------------------------


def test_aprobada_al_primer_intento():
    proponer = Propuestas(_arquitectura())
    resultado = ciclo_llm_opa(
        _modelo(), object(), validar=_validar_por_turnos(True), proponer=proponer
    )
    assert resultado.aprobada
    assert [i.numero for i in resultado.intentos] == [1]
    assert resultado.final.origen == "llm"
    assert resultado.final.retroalimentacion == []
    assert proponer.motivos == [None]


def test_los_motivos_de_opa_vuelven_al_llm():
    proponer = Propuestas(_arquitectura(), _arquitectura())
    vistos = []
    resultado = ciclo_llm_opa(
        _modelo(),
        object(),
        validar=_validar_por_turnos(False, True),
        proponer=proponer,
        al_intento=vistos.append,
    )
    assert resultado.aprobada
    assert len(resultado.intentos) == 2
    assert proponer.motivos == [None, ["Dependencias circulares entre a, b"]]
    assert resultado.intentos[1].retroalimentacion == ["Dependencias circulares entre a, b"]
    assert [i.decision.aprobado for i in vistos] == [False, True]


def test_los_motivos_se_acumulan_entre_rechazos():
    rechazos = iter(
        [
            DecisionArquitectura(
                **_decision(False).model_dump()
                | {"bloqueantes": [{"regla": "arquitectura.base_datos_propia", "motivo": "base"}]}
            ),
            _decision(False),
            _decision(True),
        ]
    )
    proponer = Propuestas(_arquitectura(), _arquitectura(), _arquitectura())
    ciclo_llm_opa(_modelo(), object(), validar=lambda a: next(rechazos), proponer=proponer)
    assert proponer.motivos == [
        None,
        ["base"],
        ["base", "Dependencias circulares entre a, b"],
    ]


def test_sin_aprobacion_en_tres_intentos_queda_para_revision_humana():
    proponer = Propuestas(_arquitectura(), _arquitectura(), _arquitectura())
    resultado = ciclo_llm_opa(
        _modelo(), object(), validar=_validar_por_turnos(False, False, False), proponer=proponer
    )
    assert not resultado.aprobada
    assert len(resultado.intentos) == resultado.maximo_intentos == 3
    assert len(proponer.motivos) == 3


def test_una_arquitectura_inicial_se_valida_antes_de_llamar_al_llm():
    proponer = Propuestas(_arquitectura())
    inicial = _base_compartida()
    resultado = ciclo_llm_opa(
        _modelo(),
        object(),
        inicial=inicial,
        validar=_validar_por_turnos(False, True),
        proponer=proponer,
    )
    assert [i.origen for i in resultado.intentos] == ["inicial", "llm"]
    assert resultado.intentos[0].arquitectura == inicial
    assert proponer.motivos == [["Dependencias circulares entre a, b"]]

    proponer = Propuestas()
    resultado = ciclo_llm_opa(
        _modelo(), object(), inicial=inicial, validar=_validar_por_turnos(True), proponer=proponer
    )
    assert resultado.aprobada and proponer.motivos == []


def test_los_errores_se_propagan_y_los_intentos_se_validan():
    def falla(*args, **kwargs):
        raise ErrorProveedorLLM("groq: error 401 de la API")

    with pytest.raises(ErrorProveedorLLM):
        ciclo_llm_opa(_modelo(), object(), validar=_validar_por_turnos(True), proponer=falla)
    with pytest.raises(ValueError, match="intentos"):
        ciclo_llm_opa(_modelo(), object(), intentos=0)


# --- Decisiones para Neo4j ---------------------------------------------------------------------


def _resultado(aprobado: bool) -> ResultadoCiclo:
    return ciclo_llm_opa(
        _modelo(),
        object(),
        intentos=1,
        validar=_validar_por_turnos(aprobado),
        proponer=Propuestas(_arquitectura()),
    )


def test_decisiones_de_una_arquitectura_aprobada():
    decisiones = decisiones_del_ciclo(_resultado(True))
    assert [(d["id"], d["tipo"]) for d in decisiones] == [
        ("D-01", "arquitectura"),
        ("P-api_gateway", "patron"),
    ]
    arquitectura, patron = decisiones
    assert arquitectura["requisitos"] == ["RF-01", "RF-02", "RF-03"]
    assert [r["regla"] for r in arquitectura["reglas"]] == CRITERIOS
    assert all(r["cumple"] for r in arquitectura["reglas"])
    assert patron["patrones"] == [{"id": "arq.gateway.001", "patron": "api_gateway"}]
    assert patron["justificacion"] == "Hay requisitos de autenticación y varios servicios"


def test_el_rechazo_final_es_una_decision_para_revision_humana():
    (rechazo,) = decisiones_del_ciclo(_resultado(False))
    assert (rechazo["id"], rechazo["tipo"], rechazo["estado"]) == (
        "RECHAZO",
        "rechazo",
        "rechazada",
    )
    assert rechazo["motivos"] == ["Dependencias circulares entre a, b"]
    incumplida = next(r for r in rechazo["reglas"] if r["regla"] == "arquitectura.sin_ciclos")
    assert incumplida == {
        "regla": "arquitectura.sin_ciclos",
        "cumple": False,
        "detalle": "d",
        "motivos": ["Dependencias circulares entre a, b"],
    }


def test_registrar_decisiones_en_una_consulta():
    driver = DriverSimulado()
    assert registrar_decisiones(driver, "ej-1", _resultado(True), base_datos="b", version="v") == 2

    consulta, parametros, base = driver.consulta_con("UNWIND $decisiones")
    assert base == "b"
    for fragmento in (
        "MERGE (d:Decision {ejecucion_id: $ejecucion_id, id: dato.id})",
        "MERGE (e)-[:TIENE_DECISION]->(d)",
        "MERGE (r)-[:ORIGINA]->(d)",
        "MERGE (d)-[b:BASADA_EN]->(g)",
        "MERGE (d)-[:APLICA]->(p)",
        "DETACH DELETE vieja",
    ):
        assert fragmento in consulta
    assert parametros["aprobada"] is True
    assert parametros["intentos"] == 1
    assert parametros["version"] == "v"
    assert [d["id"] for d in parametros["decisiones"]] == ["D-01", "P-api_gateway"]


def test_registrar_decisiones_en_ejecucion_inexistente():
    with pytest.raises(ErrorGrafo, match="No existe la ejecución"):
        registrar_decisiones(DriverSimulado(existe=False), "ej-x", _resultado(True))


def test_ejecucion_de_documento_busca_por_la_huella():
    driver = DriverSimulado()
    assert ejecucion_de_documento(driver, "a" * 64) is None
    consulta, parametros, _ = driver.consultas[0]
    assert "documento_sha256: $sha256" in consulta
    assert parametros == {"sha256": "a" * 64}


# --- Comando -----------------------------------------------------------------------------------


@pytest.fixture
def archivo_modelo(tmp_path):
    archivo = tmp_path / "requisitos-md.modelo_requisitos.json"
    archivo.write_text(_modelo().model_dump_json(), encoding="utf-8")
    return archivo


def _proponer(tmp_path, *argumentos):
    return runner.invoke(
        app,
        [
            "arquitectura",
            "proponer",
            str(tmp_path / "requisitos-md.modelo_requisitos.json"),
            "--destino",
            str(tmp_path),
            *argumentos,
        ],
    )


@con_opa
def test_comando_reintenta_con_los_motivos_de_opa(archivo_modelo, tmp_path, monkeypatch):
    propuesta_rechazada = _propuesta(
        servicios=[
            _servicio("usuarios", ["RF-01"]),
            _servicio("pedidos", ["RF-02"]) | {"base_datos": "usuarios_db"},
            _servicio("notificaciones", ["RF-03"], [("pedidos", "asincrona")]),
        ]
    )
    llm = LLMSimulado(propuesta_rechazada, _propuesta())
    monkeypatch.setattr("orchestrator.llm.crear_proveedor", lambda nombre=None: llm)

    resultado = _proponer(tmp_path)

    assert resultado.exit_code == 0, resultado.output
    assert "Intento 1 (propuesta del LLM): Arquitectura rechazada" in resultado.output
    assert "OPA rechaza: Los servicios pedidos, usuarios comparten la base de datos" in (
        resultado.output
    )
    assert "Se vuelve a pedir al LLM con estos motivos." in resultado.output
    assert "Intento 2 (propuesta del LLM): Arquitectura aprobada" in resultado.output
    assert "Patrones inferidos por OPA:" in resultado.output
    # El segundo prompt lleva el motivo del rechazo de OPA.
    assert "comparten la base de datos usuarios_db" in llm.llamadas[1]["prompt"]

    registro = ResultadoCiclo.model_validate_json(
        (tmp_path / "requisitos-md.intentos.json").read_bytes()
    )
    assert registro.aprobada
    assert [i.decision.aprobado for i in registro.intentos] == [False, True]
    assert registro.intentos[1].retroalimentacion[0].startswith("Los servicios pedidos, usuarios")
    aprobada = Arquitectura.model_validate_json(
        (tmp_path / "requisitos-md.arquitectura.json").read_bytes()
    )
    assert aprobada == registro.final.arquitectura


@con_opa
def test_comando_sin_aprobacion_no_guarda_la_arquitectura(archivo_modelo, tmp_path, monkeypatch):
    rechazada = _propuesta(
        servicios=[
            _servicio("usuarios", ["RF-01"], [("pedidos", "sincrona")]),
            _servicio("pedidos", ["RF-02"], [("usuarios", "sincrona")]),
            _servicio("notificaciones", ["RF-03"]),
        ]
    )
    llm = LLMSimulado(rechazada, rechazada)
    monkeypatch.setattr("orchestrator.llm.crear_proveedor", lambda nombre=None: llm)

    resultado = _proponer(tmp_path, "--intentos", "2")

    assert resultado.exit_code == 1
    assert "revisión humana" in resultado.output
    assert not (tmp_path / "requisitos-md.arquitectura.json").exists()
    registro = json.loads((tmp_path / "requisitos-md.intentos.json").read_text("utf-8"))
    assert registro["aprobada"] is False
    assert len(registro["intentos"]) == 2


@con_opa
def test_comando_desde_una_arquitectura_valida_no_llama_al_llm(
    archivo_modelo, tmp_path, monkeypatch
):
    inicial = tmp_path / "corregida.json"
    inicial.write_text(_arquitectura().model_dump_json(), encoding="utf-8")
    llm = LLMSimulado()
    monkeypatch.setattr("orchestrator.llm.crear_proveedor", lambda nombre=None: llm)

    resultado = _proponer(tmp_path, "--desde", str(inicial))

    assert resultado.exit_code == 0, resultado.output
    assert "Intento 1 (arquitectura inicial): Arquitectura aprobada" in resultado.output
    assert llm.llamadas == []


@con_opa
def test_comando_registra_las_decisiones_en_neo4j(archivo_modelo, tmp_path, monkeypatch):
    driver = DriverSimulado()
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: driver)
    monkeypatch.setattr("orchestrator.knowledge.registro.version_conocimiento", lambda: "v1")
    monkeypatch.setattr(
        "orchestrator.llm.crear_proveedor", lambda nombre=None: LLMSimulado(_propuesta())
    )

    resultado = _proponer(tmp_path, "--grafo")

    assert resultado.exit_code == 0, resultado.output
    # No había ejecución con los requisitos de este documento: se crea y se registran.
    assert any("CREATE (e:Ejecucion" in c[0] for c in driver.consultas)
    assert any("UNWIND $requisitos" in c[0] for c in driver.consultas)
    _, parametros, _ = driver.consulta_con("UNWIND $decisiones")
    assert parametros["decisiones"][0]["id"] == "D-01"
    assert "Decisiones registradas en Neo4j:" in resultado.output


@con_opa
def test_comando_avisa_si_neo4j_falla_pero_guarda_la_arquitectura(
    archivo_modelo, tmp_path, monkeypatch
):
    monkeypatch.setattr(
        "orchestrator.knowledge.conectar", lambda config: DriverSimulado(falla=True)
    )
    monkeypatch.setattr(
        "orchestrator.llm.crear_proveedor", lambda nombre=None: LLMSimulado(_propuesta())
    )
    resultado = _proponer(tmp_path, "--grafo", "--ejecucion", "ej-1")
    assert resultado.exit_code == 0, resultado.output
    assert "Sin registro en Neo4j" in resultado.output
    assert (tmp_path / "requisitos-md.arquitectura.json").exists()


# --- Integración con Neo4j real ----------------------------------------------------------------


@pytest.mark.integracion
@pytest.mark.skipif(
    os.environ.get("NEO4J_INTEGRACION") != "1",
    reason="Requiere Neo4j levantado y NEO4J_INTEGRACION=1",
)
def test_integracion_decisiones_en_neo4j():
    config = obtener_configuracion()
    driver = conectar(config)
    base = config.neo4j_database
    ejecucion_id = crear_ejecucion(driver, documento="prueba-integracion", base_datos=base)
    try:
        registrar_requisitos(driver, ejecucion_id, _modelo(), base_datos=base)
        registrar_decisiones(driver, ejecucion_id, _resultado(True), base_datos=base)
        # Un segundo ciclo reemplaza las decisiones del primero.
        registrar_decisiones(driver, ejecucion_id, _resultado(True), base_datos=base)

        filas = {f["id"]: f for f in listar_decisiones(driver, ejecucion_id, base)}
        assert set(filas) == {"D-01", "P-api_gateway"}
        assert sorted(filas["D-01"]["requisitos"]) == ["RF-01", "RF-02", "RF-03"]
        assert {r["regla"] for r in filas["D-01"]["reglas"]} == set(CRITERIOS)
        assert filas["P-api_gateway"]["patron"] == "arq.gateway.001"
        assert ejecucion_de_documento(driver, _modelo().documento.sha256, base) is not None

        registrar_decisiones(driver, ejecucion_id, _resultado(False), base_datos=base)
        assert [f["id"] for f in listar_decisiones(driver, ejecucion_id, base)] == ["RECHAZO"]
    finally:
        driver.execute_query(
            "MATCH (n) WHERE n.id = $id OR n.ejecucion_id = $id DETACH DELETE n",
            {"id": ejecucion_id},
            database_=base,
        )
        driver.close()
