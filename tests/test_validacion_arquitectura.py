"""Validación de arquitectura.json con OPA y la base de conocimiento (fase 2).

Las reglas se prueban con `opa test policies/arquitectura`; aquí se prueba el puente del motor:
la entrada que arma, la lectura de la decisión y la coherencia con la base de conocimiento.
"""

import re
import shutil
from pathlib import Path

import pytest

from orchestrator.architecture import (
    PropuestaArquitectura,
    construir_arquitectura,
    validar_arquitectura,
)
from orchestrator.architecture.validacion import construir_entrada
from orchestrator.knowledge.base_conocimiento import cargar_base_conocimiento
from orchestrator.opa import ErrorOPA
from tests.test_arquitectura import _modelo, _propuesta, _servicio

RAIZ = Path(__file__).resolve().parent.parent
POLITICA = RAIZ / "policies" / "arquitectura" / "arquitectura.rego"
con_opa = pytest.mark.skipif(shutil.which("opa") is None, reason="Requiere el ejecutable opa")


def _arquitectura(**cambios):
    return construir_arquitectura(_propuesta(**cambios), _modelo())


def test_la_entrada_lleva_la_arquitectura_y_los_patrones_de_la_base():
    entrada = construir_entrada(_arquitectura())
    assert entrada["arquitectura"]["servicios"][1]["depende_de"][0]["servicio"] == "usuarios"
    patrones = {p["patron"]: p for p in entrada["patrones"]}
    assert set(patrones) == {
        "api_gateway",
        "bff",
        "circuit_breaker",
        "database_per_service",
        "event_driven",
        "saga",
    }
    # Sin claves nulas: cada condición trae solo «etiqueta» o solo «numero_servicios_minimo».
    for condicion in patrones["saga"]["aplica_cuando"]:
        assert len(condicion) == 1


def test_los_rasgos_de_la_politica_existen_en_la_base_de_conocimiento():
    """Una etiqueta mal escrita en la política haría que un patrón no se infiera nunca."""
    usados = {
        c.etiqueta
        for p in cargar_base_conocimiento().patrones
        for c in p.aplica_cuando
        if c.etiqueta
    }
    producidos = set(re.findall(r'"etiqueta": "([a-z_]+)"', POLITICA.read_text(encoding="utf-8")))
    assert producidos
    assert producidos <= usados, producidos - usados


@con_opa
def test_una_arquitectura_valida_se_aprueba_con_sus_patrones():
    decision = validar_arquitectura(_arquitectura())

    assert decision.aprobado, decision.justificacion
    assert decision.retroalimentacion() == []
    assert all(c.cumple for c in decision.criterios)
    ids = [p.id for p in decision.patrones]
    assert ids == sorted(ids)  # orden estable, aunque OPA devuelva conjuntos
    # pedidos llama a usuarios y notificaciones escucha a pedidos; RF-01 pide autenticación.
    assert {p.patron for p in decision.patrones} == {
        "api_gateway",
        "circuit_breaker",
        "database_per_service",
        "event_driven",
    }
    gateway = next(p for p in decision.patrones if p.patron == "api_gateway")
    assert gateway.por == ["autenticacion_centralizada"]
    assert gateway.controles and gateway.cwe


@con_opa
def test_compartir_la_base_de_datos_se_rechaza_con_motivos_para_el_llm():
    servicios = [
        _servicio("usuarios", ["RF-01"]),
        _servicio("pedidos", ["RF-02"]) | {"base_datos": "usuarios_db"},
        _servicio("notificaciones", ["RF-03"], [("pedidos", "asincrona")]),
    ]
    decision = validar_arquitectura(_arquitectura(servicios=servicios))

    assert not decision.aprobado
    assert decision.retroalimentacion() == [
        "Los servicios pedidos, usuarios comparten la base de datos usuarios_db; "
        "cada servicio debe tener la suya"
    ]
    assert "incumple 1 de 4 criterios" in decision.justificacion


@con_opa
def test_un_ciclo_se_rechaza():
    servicios = [
        _servicio("usuarios", ["RF-01"], [("pedidos", "sincrona")]),
        _servicio("pedidos", ["RF-02"], [("usuarios", "sincrona")]),
        _servicio("notificaciones", ["RF-03"]),
    ]
    decision = validar_arquitectura(_arquitectura(servicios=servicios))
    assert [b.regla for b in decision.bloqueantes] == ["arquitectura.sin_ciclos"]


def test_sin_opa():
    with pytest.raises(ErrorOPA, match="No se pudo ejecutar OPA"):
        validar_arquitectura(_arquitectura(), opa="no-existe-este-opa")


@con_opa
def test_politicas_inexistentes(tmp_path):
    with pytest.raises(ErrorOPA, match="no devolvió una decisión"):
        validar_arquitectura(_arquitectura(), politicas=tmp_path)


def test_la_propuesta_de_prueba_es_valida():
    assert isinstance(_propuesta(), PropuestaArquitectura)
