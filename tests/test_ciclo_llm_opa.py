"""Ciclo LLM ↔ OPA de demostración (scripts/demo/ciclo_llm_opa.py), con dobles de OPA y del LLM.

Es temporal hasta que la #58 integre el ciclo; esta prueba solo evita que se rompa sin avisar.
"""

import importlib.util
import sys
from pathlib import Path

from orchestrator.architecture.validacion import Criterio, DecisionArquitectura, Motivo
from tests.test_arquitectura import _modelo
from tests.test_validacion_arquitectura import _arquitectura

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "demo" / "ciclo_llm_opa.py"
_spec = importlib.util.spec_from_file_location("ciclo_llm_opa", SCRIPT)
ciclo = importlib.util.module_from_spec(_spec)
sys.modules["ciclo_llm_opa"] = ciclo  # dataclass busca su módulo aquí
_spec.loader.exec_module(ciclo)


def _decision(aprobado: bool) -> DecisionArquitectura:
    return DecisionArquitectura(
        aprobado=aprobado,
        bloqueantes=[]
        if aprobado
        else [Motivo(regla="arquitectura.sin_ciclos", motivo="Dependencias circulares entre a, b")],
        advertencias=[],
        criterios=[Criterio(regla="arquitectura.sin_ciclos", cumple=aprobado, detalle="")],
        rasgos=[],
        patrones=[],
        justificacion="aprobada" if aprobado else "rechazada",
    )


class Dobles:
    """OPA rechaza las primeras `rechazos` veces; el LLM devuelve una arquitectura nueva."""

    def __init__(self, rechazos: int):
        self.rechazos = rechazos
        self.validadas = 0
        self.retroalimentaciones: list[list[str]] = []

    def validar(self, _arquitectura):
        self.validadas += 1
        return _decision(aprobado=self.validadas > self.rechazos)

    def proponer(self, _modelo, _llm, retroalimentacion):
        self.retroalimentaciones.append(retroalimentacion)
        return _arquitectura()


def _ciclo(dobles: Dobles):
    return ciclo.ciclo_llm_opa(
        _arquitectura(), _modelo(), llm=None, validar=dobles.validar, proponer=dobles.proponer
    )


def test_si_opa_aprueba_a_la_primera_no_se_llama_al_llm():
    dobles = Dobles(rechazos=0)
    historial = _ciclo(dobles)
    assert [i.decision.aprobado for i in historial] == [True]
    assert dobles.retroalimentaciones == []


def test_el_llm_recibe_los_motivos_del_rechazo_hasta_que_opa_aprueba():
    dobles = Dobles(rechazos=2)
    historial = _ciclo(dobles)
    assert [i.decision.aprobado for i in historial] == [False, False, True]
    assert [i.numero for i in historial] == [1, 2, 3]
    assert dobles.retroalimentaciones == [["Dependencias circulares entre a, b"]] * 2


def test_como_mucho_tres_intentos():
    dobles = Dobles(rechazos=5)
    historial = _ciclo(dobles)
    assert len(historial) == 3 and not historial[-1].decision.aprobado
    assert len(dobles.retroalimentaciones) == 2  # tras el tercer rechazo ya no se pide otra


def test_sin_argumentos_muestra_el_uso(capsys):
    assert ciclo.main([]) == 2
    assert "Uso:" in capsys.readouterr().err
