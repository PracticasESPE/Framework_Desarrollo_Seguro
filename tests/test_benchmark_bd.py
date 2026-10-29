"""Pruebas de la parte de cálculo y presentación del benchmark (no necesitan bases de datos)."""

import pytest

from evaluation.benchmark_bd.benchmark import (
    DESCRIPCIONES,
    NEO4J,
    POSTGRES,
    EmbeddingsEnCache,
    _parametros_pg,
    _vector,
    contar_datos,
    percentil,
    resumir,
    tabla_markdown,
)
from orchestrator.knowledge.base_conocimiento import cargar_base_conocimiento


def test_percentil_con_interpolacion_lineal():
    valores = [1.0, 2.0, 3.0, 4.0, 5.0]
    assert percentil(valores, 50) == 3.0
    assert percentil(valores, 95) == pytest.approx(4.8)
    assert percentil(valores, 0) == 1.0
    assert percentil(valores, 100) == 5.0
    assert percentil([7.0], 95) == 7.0


def test_percentil_sin_valores():
    with pytest.raises(ValueError):
        percentil([], 50)


def test_resumir():
    resumen = resumir([1.0, 2.0, 3.0, 4.0, 10.0])
    assert resumen == {"media": 4.0, "p50": 3.0, "p95": 8.8, "muestras": 5}


def test_las_tres_consultas_existen_en_los_dos_motores():
    assert set(NEO4J) == set(POSTGRES) == set(DESCRIPCIONES)


def test_vector_en_formato_pgvector():
    assert _vector([0.5, -0.25]) == "[0.5000000,-0.2500000]"
    assert _parametros_pg({"vector": [1.0], "id": "CWE-89"}) == {
        "vector": "[1.0000000]",
        "id": "CWE-89",
    }


def test_la_cache_calcula_cada_embedding_una_vez():
    class Proveedor:
        modelo, dimensiones = "x", 2
        llamadas: list[list[str]] = []

        def embeber(self, textos):
            self.llamadas.append(list(textos))
            return [[float(len(t)), 0.0] for t in textos]

    proveedor = Proveedor()
    cache = EmbeddingsEnCache(proveedor)

    assert cache.embeber(["ab", "abc", "ab"]) == [[2.0, 0.0], [3.0, 0.0], [2.0, 0.0]]
    assert cache.embeber(["abc", "abcd"]) == [[3.0, 0.0], [4.0, 0.0]]
    assert proveedor.llamadas == [["ab", "abc"], ["abcd"]]


def test_contar_datos_de_la_base_real():
    datos = contar_datos(cargar_base_conocimiento(), 384)
    assert datos == {"nodos": 86, "relaciones": 108, "fragmentos": 86, "dimensiones": 384}


def _latencias(neo, pg):
    estadistica = {"media": neo, "p50": neo, "p95": neo, "muestras": 3}
    otra = {"media": pg, "p50": pg, "p95": pg, "muestras": 3}
    return {
        "neo4j": estadistica,
        "postgres": otra,
        "neo4j_transaccion": estadistica,
        "neo4j_servidor": estadistica,
        "postgres_servidor": otra,
    }


def test_tabla_markdown():
    resultados = {
        "fecha": "2026-10-28",
        "equipo": "pruebas",
        "iteraciones": 3,
        "calentamiento": 1,
        "datos": {"nodos": 86, "relaciones": 108, "fragmentos": 86, "dimensiones": 384},
        "verificacion": {
            "trazabilidad": 10,
            "total_trazabilidad": 10,
            "controles_cwe": 42,
            "total_controles_cwe": 42,
            "vectorial": 0.88,
        },
        "latencias": {
            "trazabilidad": _latencias(2.0, 8.0),
            "controles_cwe": _latencias(9.0, 3.0),
            "vectorial": _latencias(4.0, 4.0),
        },
    }
    tabla = tabla_markdown(resultados)

    assert "| Neo4j (4.0×) |" in tabla
    assert "| PostgreSQL (3.0×) |" in tabla
    assert "10 de 10 riesgos" in tabla
    assert "42 de 42 CWE" in tabla
    assert "88%" in tabla
    assert "## Tiempo dentro de cada base (servidor)" in tabla
