"""Pruebas de fragmentos, embeddings e índice vectorial.

Usan un proveedor de embeddings simulado: las pruebas no descargan ningún modelo.
La de integración necesita Neo4j levantado y NEO4J_INTEGRACION=1.
"""

import hashlib
import os
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.config import obtener_configuracion
from orchestrator.knowledge import ErrorGrafo, conectar
from orchestrator.knowledge.base_conocimiento import BaseConocimiento, cargar_base_conocimiento
from orchestrator.knowledge.cargador import calcular_version, cargar_en_grafo
from orchestrator.knowledge.embeddings import ProveedorEmbeddings
from orchestrator.knowledge.fragmentos import (
    NOMBRE_INDICE,
    asegurar_indice,
    cargar_fragmentos,
    dividir,
    generar_fragmentos,
)

runner = CliRunner()


class EmbeddingsSimulados:
    """Vectores deterministas a partir del texto, sin modelo real."""

    def __init__(self, dimensiones: int = 8, modelo: str = "simulado"):
        self.modelo = modelo
        self.dimensiones = dimensiones
        self.llamadas = 0

    def embeber(self, textos):
        self.llamadas += 1
        vectores = []
        for texto in textos:
            semilla = hashlib.shake_256(texto.encode("utf-8")).digest(self.dimensiones)
            vectores.append([b / 255 + 0.01 for b in semilla])
        return vectores


class DriverSimulado:
    def __init__(self, dimensiones_existentes=None):
        self.consultas: list[tuple[str, dict]] = []
        self.dimensiones_existentes = dimensiones_existentes
        self.indice_creado = False

    def execute_query(self, consulta, parametros=None, database_="neo4j"):
        self.consultas.append((consulta, parametros or {}))
        if "SHOW VECTOR INDEXES" in consulta:
            if self.dimensiones_existentes is not None:
                filas = [{"state": "ONLINE", "dimensiones": self.dimensiones_existentes}]
            elif self.indice_creado:
                filas = [{"state": "POPULATING", "dimensiones": 8}]
            else:
                filas = []
        elif "CREATE VECTOR INDEX" in consulta:
            self.indice_creado = True
            filas = []
        elif "DETACH DELETE" in consulta:
            filas = [{"total": 0}]
        elif "RETURN count(DISTINCT n)" in consulta:
            filas = [{"fragmentos": 7, "enlaces": 7}]
        else:
            filas = []
        return SimpleNamespace(records=filas)

    def close(self):
        pass


# --- División en trozos ---------------------------------------------------------------------


def test_dividir_texto_corto():
    assert dividir("uno  dos\ntres") == ["uno dos tres"]
    assert dividir("   ") == []


def test_dividir_texto_largo_con_solape():
    palabras = [f"p{i}" for i in range(25)]
    trozos = dividir(" ".join(palabras), max_palabras=10, solape=3)

    assert trozos[0].split() == palabras[:10]
    assert trozos[1].split()[:3] == palabras[7:10]
    assert trozos[-1].split()[-1] == "p24"
    assert all(len(t.split()) <= 10 for t in trozos)


def test_dividir_rechaza_solape_mayor_que_el_trozo():
    with pytest.raises(ValueError):
        dividir("a b c", max_palabras=3, solape=3)


# --- Fragmentos de la base real -------------------------------------------------------------


def test_un_fragmento_por_elemento_de_la_base():
    base = cargar_base_conocimiento()
    fragmentos = generar_fragmentos(base)

    total = (
        len(base.debilidades)
        + len(base.controles)
        + len(base.riesgos_api)
        + len(base.patrones)
        + len(base.directrices)
    )
    assert len({f.origen_id for f in fragmentos}) == total
    assert len({f.id for f in fragmentos}) == len(fragmentos)


def test_los_fragmentos_llevan_el_contexto_del_elemento():
    fragmentos = {f.id: f for f in generar_fragmentos(cargar_base_conocimiento())}

    assert "SQL Injection" in fragmentos["frag.CWE-89.1"].texto
    assert fragmentos["frag.CWE-89.1"].origen_tipo == "CWE"
    assert "V4 Control de acceso" in fragmentos["frag.ASVS-V4.1.3.1"].texto
    assert "traefik" in fragmentos["frag.arq.gateway.001.1"].texto
    assert "Prácticas:" in fragmentos["frag.sbd.secretos.001.1"].texto


# --- Carga en Neo4j con driver simulado -----------------------------------------------------


def test_el_proveedor_simulado_cumple_la_interfaz():
    assert isinstance(EmbeddingsSimulados(), ProveedorEmbeddings)


def test_carga_crea_el_indice_y_envia_los_vectores():
    base = cargar_base_conocimiento()
    driver = DriverSimulado()
    proveedor = EmbeddingsSimulados()

    resultado = cargar_fragmentos(driver, base, proveedor, "v1")

    creacion = next(c for c, _ in driver.consultas if "CREATE VECTOR INDEX" in c)
    assert "`vector.dimensions`: 8" in creacion
    assert "'cosine'" in creacion
    carga = next(p for c, p in driver.consultas if "MERGE (n:Fragmento" in c)
    assert carga["version"] == "v1:simulado"
    assert all(len(f["embedding"]) == 8 for f in carga["filas"])
    assert proveedor.llamadas == 1
    assert resultado["indice"] == NOMBRE_INDICE
    assert resultado["estado_indice"] == "POPULATING"
    assert resultado["fragmentos"] == 7


def test_no_recrea_un_indice_existente_con_la_misma_dimension():
    driver = DriverSimulado(dimensiones_existentes=8)
    assert asegurar_indice(driver, 8) == "ONLINE"
    assert not any("CREATE VECTOR INDEX" in c for c, _ in driver.consultas)


def test_indice_con_otra_dimension():
    driver = DriverSimulado(dimensiones_existentes=384)
    with pytest.raises(ErrorGrafo, match="DROP INDEX fragmento_embedding"):
        asegurar_indice(driver, 768)


def test_vectores_con_dimension_incorrecta():
    class Defectuoso(EmbeddingsSimulados):
        def embeber(self, textos):
            return [[0.1, 0.2] for _ in textos]

    with pytest.raises(ErrorGrafo, match="dimensiones"):
        cargar_fragmentos(DriverSimulado(), cargar_base_conocimiento(), Defectuoso(), "v")


def test_base_vacia_no_envia_fragmentos():
    driver = DriverSimulado()
    cargar_fragmentos(driver, BaseConocimiento(), EmbeddingsSimulados(), "v")
    assert not any("MERGE (n:Fragmento" in c for c, _ in driver.consultas)


# --- Comando de la CLI -----------------------------------------------------------------------


def test_comando_embeddings(monkeypatch):
    driver = DriverSimulado()
    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: driver)
    monkeypatch.setattr("orchestrator.knowledge.aplicar_esquema", lambda d, base: 22)
    monkeypatch.setattr(
        "orchestrator.knowledge.embeddings.EmbeddingsLocales",
        lambda modelo, cache: EmbeddingsSimulados(modelo=modelo),
    )

    resultado = runner.invoke(app, ["conocimiento", "embeddings"])

    assert resultado.exit_code == 0, resultado.output
    assert "Índice vectorial: fragmento_embedding" in resultado.output
    assert "Fragmentos: 7" in resultado.output
    assert "paraphrase-multilingual-MiniLM-L12-v2" in resultado.output


def test_comando_embeddings_sin_neo4j(monkeypatch):
    def sin_conexion(config):
        raise ErrorGrafo("No se pudo conectar con Neo4j")

    monkeypatch.setattr("orchestrator.knowledge.conectar", sin_conexion)
    monkeypatch.setattr(
        "orchestrator.knowledge.embeddings.EmbeddingsLocales",
        lambda modelo, cache: EmbeddingsSimulados(),
    )
    resultado = runner.invoke(app, ["conocimiento", "embeddings"])

    assert resultado.exit_code == 1
    assert "No se pudo conectar" in resultado.output


# --- Integración con Neo4j real --------------------------------------------------------------


@pytest.mark.integracion
@pytest.mark.skipif(
    os.environ.get("NEO4J_INTEGRACION") != "1",
    reason="Requiere Neo4j levantado y NEO4J_INTEGRACION=1",
)
def test_integracion_indice_y_busqueda_vectorial():
    config = obtener_configuracion()
    driver = conectar(config)
    db = config.neo4j_database
    base = cargar_base_conocimiento()
    # Misma dimensión que el modelo real, para convivir con el índice existente.
    proveedor = EmbeddingsSimulados(dimensiones=384, modelo="simulado-integracion")
    try:
        cargar_en_grafo(driver, base, calcular_version(), base_datos=db)
        resultado = cargar_fragmentos(driver, base, proveedor, "integracion", base_datos=db)
        assert resultado["fragmentos"] == len(generar_fragmentos(base))
        assert resultado["enlaces_describe"] == resultado["fragmentos"]

        indices = driver.execute_query("SHOW VECTOR INDEXES", database_=db).records
        assert any(i["name"] == NOMBRE_INDICE for i in indices)

        # El vector de un fragmento debe encontrarse a sí mismo como el más parecido.
        driver.execute_query("CALL db.awaitIndexes(60)", database_=db)
        objetivo = next(f for f in generar_fragmentos(base) if f.id == "frag.CWE-89.1")
        vector = proveedor.embeber([objetivo.texto])[0]
        vecinos = driver.execute_query(
            "CALL db.index.vector.queryNodes($indice, 3, $vector) YIELD node, score "
            "RETURN node.id AS id, score",
            {"indice": NOMBRE_INDICE, "vector": vector},
            database_=db,
        ).records
        assert vecinos[0]["id"] == "frag.CWE-89.1"
    finally:
        driver.execute_query(
            "MATCH (f:Fragmento) WHERE f.version STARTS WITH 'integracion' DETACH DELETE f",
            database_=db,
        )
        driver.close()
