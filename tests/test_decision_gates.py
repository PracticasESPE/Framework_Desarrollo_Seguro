"""Pruebas de las decisiones de los gates con OPA y de su registro en Neo4j.

Las que llaman a OPA necesitan el ejecutable `opa` (en CI lo instala el paso "Preparar OPA");
si no está, se saltan. La de integración necesita además Neo4j y NEO4J_INTEGRACION=1.
"""

import json
import os
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.config import obtener_configuracion
from orchestrator.gates.decision import (
    DecisionGate,
    ErrorDecision,
    construir_entrada,
    evaluar,
    resumen_markdown,
)

EJEMPLO = Path(__file__).parent / "datos" / "gates"
runner = CliRunner()

con_opa = pytest.mark.skipif(shutil.which("opa") is None, reason="Requiere el ejecutable opa")


# --- Entrada de cada gate ---------------------------------------------------------------------


def test_entrada_del_gate1():
    entrada = construir_entrada(1, EJEMPLO, compilacion_ok=True)

    datos = entrada.datos
    assert datos["compilacion_ok"] is True
    estados = {h["nombre"]: h["estado"] for h in datos["herramientas"]}
    assert estados == {
        "semgrep": "hallazgos",
        "gitleaks": "hallazgos",
        "trivy fs": "hallazgos",
        "trivy config": "ok",
        "hadolint": "hallazgos",
    }
    # El nombre de la herramienta sale del archivo, que es el que conocen las políticas.
    assert {h["herramienta"] for h in datos["hallazgos"]} == {
        "semgrep",
        "gitleaks",
        "trivy fs",
        "hadolint",
    }


def test_entrada_del_gate2_detecta_el_contrato():
    datos = construir_entrada(2, EJEMPLO).datos
    assert datos["contrato_ok"] is True
    assert [h["herramienta"] for h in datos["hallazgos"]] == ["conftest"]


def test_entrada_del_gate3_separa_dast_e_imagen():
    datos = construir_entrada(3, EJEMPLO).datos
    assert {h["herramienta"] for h in datos["dast"]} == {"zap"}
    assert datos["imagen"] == []
    assert datos["sbom_generado"] is True
    assert datos["pruebas"] == {"total": 16, "fallidas": 0}


def test_sin_artefactos_todo_queda_ausente(tmp_path):
    datos = construir_entrada(3, tmp_path).datos
    assert all(h["estado"] == "error" for h in datos["herramientas"])
    assert datos["sbom_generado"] is False
    assert "pruebas" not in datos

    assert construir_entrada(2, tmp_path).datos["contrato_ok"] is False


def test_un_sarif_ilegible_cuenta_como_herramienta_caida(tmp_path):
    carpeta = tmp_path / "security" / "sarif"
    carpeta.mkdir(parents=True)
    (carpeta / "spectral.sarif").write_text("no es json", encoding="utf-8")
    datos = construir_entrada(2, tmp_path).datos
    assert {"nombre": "spectral", "estado": "error"} in datos["herramientas"]


def test_gate_inexistente():
    with pytest.raises(ValueError, match="gates son 1, 2 y 3"):
        construir_entrada(4, EJEMPLO)


# --- Evaluación con OPA -----------------------------------------------------------------------


@con_opa
def test_gate1_rechazado_con_sus_bloqueantes():
    decision = evaluar(construir_entrada(1, EJEMPLO, compilacion_ok=True))

    assert not decision.aprobado
    incumplidos = {c.regla for c in decision.criterios if not c.cumple}
    assert incumplidos == {"gate1.severidad", "gate1.secreto"}
    assert any(b.huella for b in decision.bloqueantes)
    assert decision.conteo["critica"] == 1


@con_opa
def test_gate2_aprobado_con_advertencia():
    decision = evaluar(construir_entrada(2, EJEMPLO))

    assert decision.aprobado
    assert all(c.cumple for c in decision.criterios)
    assert len(decision.advertencias) == 1
    assert decision.justificacion.startswith("Gate 2 aprobado")


@con_opa
def test_gate3_rechazado_por_el_dast():
    decision = evaluar(construir_entrada(3, EJEMPLO))

    assert not decision.aprobado
    assert {b.regla for b in decision.bloqueantes} == {"gate3.dast"}
    assert "SQL Injection" not in decision.justificacion  # la justificación nombra criterios


@con_opa
def test_politicas_inexistentes(tmp_path):
    with pytest.raises(ErrorDecision, match="no devolvió una decisión"):
        evaluar(construir_entrada(1, EJEMPLO), politicas=tmp_path)


def test_sin_opa():
    with pytest.raises(ErrorDecision, match="No se pudo ejecutar OPA"):
        evaluar(construir_entrada(1, EJEMPLO), opa="no-existe-este-opa")


def test_resumen_markdown():
    decision = DecisionGate(
        gate=1,
        aprobado=False,
        bloqueantes=[{"regla": "gate1.secreto", "motivo": "Secreto en a.ts:5"}],
        advertencias=[],
        criterios=[{"regla": "gate1.secreto", "cumple": False, "detalle": "Sin secretos"}],
        conteo={},
        justificacion="Gate 1 rechazado: incumple 1 de 1 criterios (gate1.secreto)",
    )
    texto = resumen_markdown(decision)
    assert "Decisión OPA del Gate 1: rechazado" in texto
    assert "| `gate1.secreto` | **no** | Sin secretos |" in texto


# --- CLI --------------------------------------------------------------------------------------


@con_opa
def test_comando_decidir_guarda_la_decision(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(tmp_path))
    resultado = runner.invoke(
        app,
        ["gates", "decidir", "--gate", "2", "--salida", str(EJEMPLO), "--sin-grafo"],
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Gate 2: APROBADO" in resultado.output
    guardado = json.loads((tmp_path / "gates" / "gate2.json").read_text(encoding="utf-8"))
    assert guardado["decision"]["aprobado"] is True
    assert guardado["entrada"]["contrato_ok"] is True


@con_opa
def test_comando_decidir_rechazo_termina_con_error(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(tmp_path))
    argumentos = ["gates", "decidir", "--gate", "3", "--salida", str(EJEMPLO), "--sin-grafo"]

    assert runner.invoke(app, argumentos).exit_code == 1
    assert runner.invoke(app, [*argumentos, "--no-bloquear"]).exit_code == 0


@con_opa
def test_comando_decidir_registra_en_el_grafo(tmp_path, monkeypatch):
    monkeypatch.setenv("DIRECTORIO_SALIDA", str(tmp_path))
    llamadas = {}

    class Driver:
        def close(self):
            llamadas["cerrado"] = True

    monkeypatch.setattr("orchestrator.knowledge.conectar", lambda config: Driver())
    monkeypatch.setattr(
        "orchestrator.knowledge.crear_ejecucion", lambda d, documento, base_datos: "ej-1"
    )
    monkeypatch.setattr(
        "orchestrator.knowledge.registrar_hallazgos",
        lambda d, e, h, fase, base_datos: llamadas.update(fase=fase, hallazgos=len(h)),
    )
    monkeypatch.setattr(
        "orchestrator.knowledge.registrar_resultado_gate",
        lambda d, e, decision, base_datos: llamadas.update(ejecucion=e, gate=decision.gate),
    )
    argumentos = ["gates", "decidir", "--gate", "1", "--salida", str(EJEMPLO), "--compilacion-ok"]
    resultado = runner.invoke(app, [*argumentos, "--grafo", "--no-bloquear"])

    assert resultado.exit_code == 0, resultado.output
    assert llamadas == {"fase": 4, "hallazgos": 9, "ejecucion": "ej-1", "gate": 1, "cerrado": True}
    assert "Registrada en Neo4j, ejecución ej-1" in resultado.output

    # El siguiente gate del mismo pipeline se registra en la misma ejecución.
    monkeypatch.setattr(
        "orchestrator.knowledge.crear_ejecucion",
        lambda d, documento, base_datos: pytest.fail("No debía crear otra ejecución"),
    )
    argumentos = ["gates", "decidir", "--gate", "2", "--salida", str(EJEMPLO), "--grafo"]
    resultado = runner.invoke(app, argumentos)
    assert resultado.exit_code == 0, resultado.output
    assert llamadas["ejecucion"] == "ej-1"
    assert llamadas["gate"] == 2


# --- Registro en Neo4j (driver simulado e integración) ---------------------------------------


def test_registrar_resultado_envia_criterios_y_bloqueos():
    from orchestrator.knowledge import registrar_resultado_gate

    consultas = []

    class Driver:
        def execute_query(self, consulta, parametros=None, database_="neo4j"):
            consultas.append((consulta, parametros or {}))
            if "count(e) AS total" in consulta:
                return SimpleNamespace(records=[{"total": 1}])
            return SimpleNamespace(records=[])

    decision = DecisionGate(
        gate=1,
        aprobado=False,
        bloqueantes=[
            {"regla": "gate1.secreto", "motivo": "Secreto en a.ts:5", "huella": "h1"},
            {"regla": "gate1.compilacion", "motivo": "No compila"},
        ],
        advertencias=[],
        criterios=[
            {"regla": "gate1.secreto", "cumple": False, "detalle": "Sin secretos"},
            {"regla": "gate1.compilacion", "cumple": False, "detalle": "Compila"},
            {"regla": "gate1.severidad", "cumple": True, "detalle": "Sin altos"},
        ],
        conteo={"alta": 2},
        justificacion="Gate 1 rechazado",
    )
    registrar_resultado_gate(Driver(), "ej-1", decision, version="v1")

    parametros = consultas[-1][1]
    assert parametros["id"] == "gate1"
    assert parametros["fase"] == 4
    assert parametros["conteo"] == {"critica": 0, "alta": 2, "media": 0, "baja": 0, "info": 0}
    assert parametros["bloqueos"] == [{"huella": "h1", "regla": "gate1.secreto"}]
    secreto = next(c for c in parametros["criterios"] if c["regla"] == "gate1.secreto")
    assert secreto["motivos"] == ["Secreto en a.ts:5"]


@pytest.mark.integracion
@con_opa
@pytest.mark.skipif(
    os.environ.get("NEO4J_INTEGRACION") != "1",
    reason="Requiere Neo4j levantado y NEO4J_INTEGRACION=1",
)
def test_integracion_decisiones_registradas_en_neo4j():
    from orchestrator.knowledge import (
        conectar,
        crear_ejecucion,
        listar_resultados_gate,
        registrar_hallazgos,
        registrar_resultado_gate,
    )

    config = obtener_configuracion()
    driver = conectar(config)
    db = config.neo4j_database
    ejecucion = crear_ejecucion(driver, documento="prueba-integracion-gates", base_datos=db)
    try:
        for gate, fase in ((1, 4), (2, 8), (3, 11)):
            entrada = construir_entrada(gate, EJEMPLO, compilacion_ok=True)
            registrar_hallazgos(driver, ejecucion, entrada.hallazgos, fase=fase, base_datos=db)
            registrar_resultado_gate(driver, ejecucion, evaluar(entrada), base_datos=db)
        # Registrar otra vez la misma decisión no duplica nada.
        entrada = construir_entrada(1, EJEMPLO, compilacion_ok=True)
        registrar_resultado_gate(driver, ejecucion, evaluar(entrada), base_datos=db)

        resultados = listar_resultados_gate(driver, ejecucion, db)
        assert [(r["gate"], r["aprobado"]) for r in resultados] == [
            (1, False),
            (2, True),
            (3, False),
        ]
        assert resultados[0]["hallazgos_bloqueantes"] >= 2
        assert len(resultados[1]["criterios"]) == 5
    finally:
        driver.execute_query(
            "MATCH (e:Ejecucion {id: $id}) "
            "OPTIONAL MATCH (e)-[:REGISTRA|TIENE_RESULTADO]->(n) DETACH DELETE e, n",
            {"id": ejecucion},
            database_=db,
        )
        driver.close()
