"""Pruebas de la consulta GraphRAG (búsqueda vectorial más relaciones del grafo).

Usan embeddings simulados. La de integración necesita Neo4j levantado y NEO4J_INTEGRACION=1.
"""

import hashlib
import os
from types import SimpleNamespace

import neo4j
import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.config import obtener_configuracion
from orchestrator.knowledge import ErrorGrafo, conectar
from orchestrator.knowledge.base_conocimiento import cargar_base_conocimiento
from orchestrator.knowledge.cargador import calcular_version, cargar_en_grafo
from orchestrator.knowledge.fragmentos import cargar_fragmentos, generar_fragmentos
from orchestrator.knowledge.graphrag import consultar

runner = CliRunner()


class EmbeddingsSimulados:
    def __init__(self, dimensiones: int = 8, modelo: str = "simulado"):
        self.modelo = modelo
        self.dimensiones = dimensiones
        self.textos: list[str] = []

    def embeber(self, textos):
        self.textos += textos
        return [
            [b / 255 + 0.01 for b in hashlib.shake_256(t.encode("utf-8")).digest(self.dimensiones)]
            for t in textos
        ]


FILAS = [
    {
        "fragmento": "frag.CWE-89.1",
        "texto": "CWE-89 SQL Injection. Datos del usuario dentro de una consulta SQL",
        "score": 0.91234,
        "origen_id": "CWE-89",
        "origen_tipo": "CWE",
        "cwe": [{"id": "CWE-89", "nombre": "SQL Injection"}],
        "practicas": [
            {"id": "sbd.entrada.001", "nombre": "validacion_entrada", "tipo": "Directriz"},
        ],
        "controles": [{"id": "ASVS-V5.3.4", "descripcion": "Consultas parametrizadas"}],
        "riesgos": [],
    },
    {
        "fragmento": "frag.arq.gateway.001.1",
        "texto": "Patrón de microservicios api_gateway: Punto único de entrada",
        "score": 0.8,
        "origen_id": "arq.gateway.001",
        "origen_tipo": "Patron",
        "cwe": [{"id": "CWE-284", "nombre": "Improper Access Control"}],
        "practicas": [{"id": "arq.gateway.001", "nombre": "api_gateway", "tipo": "Patron"}],
        "controles": [
            {"id": "ASVS-V4.1.1", "descripcion": "Control de acceso en capa de confianza"},
            {"id": "ASVS-V5.3.4", "descripcion": "Consultas parametrizadas"},
        ],
        "riesgos": [{"id": "API1:2023", "nombre": "Broken Object Level Authorization"}],
    },
]


class DriverSimulado:
    def __init__(self, filas=FILAS, falla=False):
        self.filas = filas
        self.falla = falla
        self.consultas: list[tuple[str, dict]] = []

    def execute_query(self, consulta, parametros=None, database_="neo4j"):
        self.consultas.append((consulta, parametros or {}))
        if self.falla:
            raise neo4j.exceptions.ClientError("índice inexistente")
        return SimpleNamespace(records=self.filas)

    def close(self):
        pass


def test_consulta_usa_el_indice_y_el_vector_de_la_pregunta():
    driver = DriverSimulado()
    proveedor = EmbeddingsSimulados()

    consultar(driver, proveedor, "inyección SQL", k=3, umbral=0.5)

    consulta, parametros = driver.consultas[0]
    assert "db.index.vector.queryNodes" in consulta
    assert "[:DESCRIBE]" in consulta
    assert parametros["indice"] == "fragmento_embedding"
    assert parametros["k"] == 3
    assert parametros["umbral"] == 0.5
    assert proveedor.textos == ["inyección SQL"]
    assert len(parametros["vector"]) == 8


def test_reune_el_conocimiento_sin_repetidos_y_en_orden():
    resultado = consultar(DriverSimulado(), EmbeddingsSimulados(), "inyección SQL")

    assert [c.origen_id for c in resultado.coincidencias] == ["CWE-89", "arq.gateway.001"]
    assert resultado.coincidencias[0].puntuacion == 0.9123
    assert [e.id for e in resultado.cwe] == ["CWE-89", "CWE-284"]
    assert [e.id for e in resultado.directrices] == ["sbd.entrada.001"]
    assert [e.id for e in resultado.patrones] == ["arq.gateway.001"]
    # ASVS-V5.3.4 aparece en las dos coincidencias y se cuenta una vez.
    assert [e.id for e in resultado.controles] == ["ASVS-V5.3.4", "ASVS-V4.1.1"]
    assert [e.id for e in resultado.riesgos] == ["API1:2023"]


def test_contexto_para_el_prompt():
    texto = consultar(DriverSimulado(), EmbeddingsSimulados(), "SQL").a_texto()

    assert texto.startswith("Conocimiento relacionado de la base del framework:")
    assert "- CWE-89 SQL Injection." in texto
    assert "Patrones de microservicios: arq.gateway.001 (api_gateway)" in texto
    assert "Controles OWASP ASVS: ASVS-V5.3.4" in texto
    assert "Riesgos OWASP API Top 10: API1:2023" in texto


def test_sin_resultados():
    resultado = consultar(DriverSimulado(filas=[]), EmbeddingsSimulados(), "nada")
    assert resultado.coincidencias == []
    assert "No se encontró" in resultado.a_texto()


@pytest.mark.parametrize(("pregunta", "k"), [("   ", 5), ("algo", 0)])
def test_parametros_invalidos(pregunta, k):
    with pytest.raises(ValueError):
        consultar(DriverSimulado(), EmbeddingsSimulados(), pregunta, k=k)


def test_error_de_neo4j():
    with pytest.raises(ErrorGrafo, match="GraphRAG"):
        consultar(DriverSimulado(falla=True), EmbeddingsSimulados(), "algo")


def _preparar_cli(monkeypatch, driver):
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: driver)
    monkeypatch.setattr(
        "orchestrator.knowledge.embeddings.EmbeddingsLocales",
        lambda modelo, cache: EmbeddingsSimulados(),
    )


def test_comando_consultar(monkeypatch):
    _preparar_cli(monkeypatch, DriverSimulado())
    resultado = runner.invoke(app, ["conocimiento", "consultar", "inyección SQL", "--k", "2"])

    assert resultado.exit_code == 0, resultado.output
    assert "0.912  [CWE] CWE-89" in resultado.output
    assert "Patrones (1):" in resultado.output
    assert "- arq.gateway.001: api_gateway" in resultado.output
    assert "Controles ASVS (2):" in resultado.output


def test_comando_consultar_contexto(monkeypatch):
    _preparar_cli(monkeypatch, DriverSimulado())
    resultado = runner.invoke(app, ["conocimiento", "consultar", "SQL", "--contexto"])

    assert resultado.exit_code == 0
    assert resultado.output.startswith("Conocimiento relacionado")


def test_comando_consultar_sin_resultados(monkeypatch):
    _preparar_cli(monkeypatch, DriverSimulado(filas=[]))
    resultado = runner.invoke(app, ["conocimiento", "consultar", "nada"])

    assert resultado.exit_code == 0
    assert "conocimiento embeddings" in resultado.output


@pytest.mark.integracion
@pytest.mark.skipif(
    os.environ.get("NEO4J_INTEGRACION") != "1",
    reason="Requiere Neo4j levantado y NEO4J_INTEGRACION=1",
)
def test_integracion_graphrag_recorre_el_grafo():
    config = obtener_configuracion()
    driver = conectar(config)
    db = config.neo4j_database
    base = cargar_base_conocimiento()
    proveedor = EmbeddingsSimulados(dimensiones=384, modelo="simulado-integracion")
    try:
        cargar_en_grafo(driver, base, calcular_version(), base_datos=db)
        cargar_fragmentos(driver, base, proveedor, "integracion", base_datos=db)
        driver.execute_query("CALL db.awaitIndexes(60)", database_=db)

        # Con embeddings simulados, preguntar con el texto exacto de un fragmento lo encuentra.
        texto = next(f.texto for f in generar_fragmentos(base) if f.id == "frag.CWE-89.1")
        resultado = consultar(driver, proveedor, texto, k=1, base_datos=db)

        assert resultado.coincidencias[0].origen_id == "CWE-89"
        assert "sbd.entrada.001" in {d.id for d in resultado.directrices}
        assert "ASVS-V5.3.4" in {c.id for c in resultado.controles}

        texto = next(f.texto for f in generar_fragmentos(base) if f.id == "frag.arq.gateway.001.1")
        resultado = consultar(driver, proveedor, texto, k=1, base_datos=db)
        assert [p.id for p in resultado.patrones][0] == "arq.gateway.001"
        assert {"ASVS-V4.1.1", "ASVS-V1.4.1"} <= {c.id for c in resultado.controles}
        assert {"CWE-284", "CWE-306"} <= {c.id for c in resultado.cwe}
    finally:
        driver.execute_query(
            "MATCH (f:Fragmento) WHERE f.version STARTS WITH 'integracion' DETACH DELETE f",
            database_=db,
        )
        driver.close()
