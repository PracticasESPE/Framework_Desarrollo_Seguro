"""Comandos del notificador que usa el workflow (orchestrator/notify/cli.py)."""

import json
import re
import sys
from pathlib import Path

import pytest
import yaml

from orchestrator.notify import cli, telegram

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "framework.yml"


@pytest.fixture
def telegram_falso(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTIFY_ESTADO", str(tmp_path / "estado.json"))
    monkeypatch.setenv("GITHUB_REPOSITORY", "org/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "99")
    envios, ediciones = [], []
    monkeypatch.setattr(telegram, "enviar", lambda t, c=None: envios.append(t) or 5)
    monkeypatch.setattr(
        telegram, "actualizar", lambda i, t, c=None: ediciones.append((i, t)) or True
    )
    return envios, ediciones, tmp_path / "estado.json"


def test_inicio_guarda_estado(telegram_falso):
    envios, _, estado = telegram_falso
    assert cli.main(["inicio"]) == 0
    datos = json.loads(estado.read_text(encoding="utf-8"))
    assert datos["message_id"] == 5 and len(datos["fases"]) == len(cli.FASES)
    assert "org/repo/actions/runs/99" in envios[0]


def test_inicio_usa_la_rama_del_pull_request(telegram_falso, monkeypatch):
    envios, _, _ = telegram_falso
    monkeypatch.setenv("GITHUB_REF_NAME", "157/merge")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feature/avisos")
    cli.main(["inicio"])
    assert "rama feature/avisos" in envios[0]


def test_ejecutar_marca_ok_y_devuelve_codigo_cero(telegram_falso):
    _, ediciones, _ = telegram_falso
    cli.main(["inicio"])
    assert cli.main(["ejecutar", "Fase 1: Requisitos", "--", sys.executable, "-c", "pass"]) == 0
    assert "🔄 Fase 1" in ediciones[0][1] and "✅ Fase 1" in ediciones[1][1]


def test_ejecutar_propaga_el_fallo(telegram_falso):
    _, ediciones, _ = telegram_falso
    cli.main(["inicio"])
    comando = [sys.executable, "-c", "raise SystemExit(3)"]
    assert cli.main(["ejecutar", "Fase 1: Requisitos", "--", *comando]) == 3
    assert "❌ Fase 1" in ediciones[-1][1]


def test_ejecutar_con_comando_inexistente_falla_sin_romper(telegram_falso):
    _, ediciones, _ = telegram_falso
    cli.main(["inicio"])
    assert cli.main(["ejecutar", "Fase 1: Requisitos", "--", "comando-que-no-existe-xyz"]) == 127
    assert "❌ Fase 1" in ediciones[-1][1]


def test_el_comando_no_recibe_las_credenciales_de_telegram(telegram_falso, monkeypatch, tmp_path):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:secreto")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100")
    salida = tmp_path / "entorno.txt"
    codigo = (
        "import os, sys; open(sys.argv[1], 'w').write("
        "os.environ.get('TELEGRAM_BOT_TOKEN', '') + os.environ.get('TELEGRAM_CHAT_ID', ''))"
    )
    cli.main(["ejecutar", "Fase 1: Requisitos", "--", sys.executable, "-c", codigo, str(salida)])
    assert salida.read_text() == ""


def test_omitir_marca_la_fase_como_omitida(telegram_falso):
    _, ediciones, estado = telegram_falso
    cli.main(["inicio"])
    assert cli.main(["omitir", "Fase 2: Arquitectura"]) == 0
    assert "⏭️ Fase 2" in ediciones[-1][1]
    fases = json.loads(estado.read_text(encoding="utf-8"))["fases"]
    assert fases["Fase 2: Arquitectura"] == "omitida"


def test_sin_estado_el_comando_se_ejecuta_igual(telegram_falso):
    assert cli.main(["ejecutar", "Fase 1: Requisitos", "--", sys.executable, "-c", "pass"]) == 0


def test_sin_credenciales_no_falla_nada(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTIFY_ESTADO", str(tmp_path / "estado.json"))
    assert cli.main(["inicio"]) == 0
    assert cli.main(["ejecutar", "Fase 1: Requisitos", "--", sys.executable, "-c", "pass"]) == 0
    assert cli.main(["omitir", "Fase 2: Arquitectura"]) == 0
    assert cli.main(["fin"]) == 0
    assert cli.main(["fallo"]) == 0


def test_fallo_envia_aviso_nuevo(telegram_falso):
    envios, _, _ = telegram_falso
    cli.main(["inicio"])
    cli.main(["fallo"])
    assert envios[-1].startswith("❌")


def _recorrer_hasta_gate_2_rechazado():
    cli.main(["inicio"])
    cli.main(["ejecutar", "Fase 4: Security Gate 1", "--", sys.executable, "-c", "pass"])
    rechazo = [sys.executable, "-c", "raise SystemExit(1)"]
    cli.main(["ejecutar", "Fase 8: Security Gate 2", "--", *rechazo])


def test_fin_informa_los_tres_gates(telegram_falso):
    envios, _, _ = telegram_falso
    cli.main(["inicio"])
    for fase in cli.GATES.values():
        cli.main(["ejecutar", fase, "--", sys.executable, "-c", "pass"])
    cli.main(["fin"])
    assert envios[-1].splitlines() == [
        "✅ Pipeline terminado correctamente",
        "✅ Gate 1 · ✅ Gate 2 · ✅ Gate 3",
        "https://github.com/org/repo/actions/runs/99",
    ]


def test_fallo_dice_que_gate_detuvo_la_cadena(telegram_falso):
    envios, ediciones, estado = telegram_falso
    _recorrer_hasta_gate_2_rechazado()
    ediciones_antes = len(ediciones)
    cli.main(["fallo"])

    assert envios[-1].splitlines()[:2] == [
        "❌ Pipeline detenido en Fase 8: Security Gate 2",
        "✅ Gate 1 · ❌ Gate 2 · 🚫 Gate 3",
    ]
    assert len(ediciones) == ediciones_antes + 1  # una sola edición, no una por fase
    assert "⏳" not in ediciones[-1][1]
    fases = json.loads(estado.read_text(encoding="utf-8"))["fases"]
    assert fases["Fase 11: DAST y Security Gate 3"] == "no_ejecutada"


def test_fallo_antes_de_las_fases_no_culpa_a_un_gate(telegram_falso):
    envios, _, _ = telegram_falso
    cli.main(["inicio"])
    cli.main(["fallo"])
    assert envios[-1].splitlines()[:2] == [
        "❌ El pipeline falló",
        "🚫 Gate 1 · 🚫 Gate 2 · 🚫 Gate 3",
    ]


def test_fallo_marca_como_fallida_la_fase_que_quedo_en_curso(telegram_falso):
    _, ediciones, estado = telegram_falso
    cli.main(["inicio"])
    datos = json.loads(estado.read_text(encoding="utf-8"))
    datos["fases"]["Fase 4: Security Gate 1"] = "ejecutando"
    estado.write_text(json.dumps(datos), encoding="utf-8")
    cli.main(["fallo"])
    assert "❌ Fase 4" in ediciones[-1][1]


def test_cancelado_no_deja_fases_en_curso_ni_culpa_a_un_gate(telegram_falso):
    envios, ediciones, estado = telegram_falso
    cli.main(["inicio"])
    datos = json.loads(estado.read_text(encoding="utf-8"))
    datos["fases"]["Fase 4: Security Gate 1"] = "ejecutando"
    estado.write_text(json.dumps(datos), encoding="utf-8")

    assert cli.main(["cancelado"]) == 0

    assert envios[-1].splitlines()[:2] == [
        "⚠️ Ejecución cancelada",
        "🚫 Gate 1 · 🚫 Gate 2 · 🚫 Gate 3",
    ]
    assert "🔄" not in ediciones[-1][1] and "⏳" not in ediciones[-1][1]


def test_sin_estado_los_avisos_finales_se_envian_igual(telegram_falso):
    envios, _, _ = telegram_falso
    for orden in ("fin", "fallo", "cancelado"):
        assert cli.main([orden]) == 0
    assert [t.splitlines()[0] for t in envios] == [
        "✅ Pipeline terminado correctamente",
        "❌ El pipeline falló",
        "⚠️ Ejecución cancelada",
    ]


def test_el_resumen_y_el_log_muestran_la_cadena_de_gates(
    telegram_falso, monkeypatch, tmp_path, capsys
):
    resumen = tmp_path / "resumen.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumen))
    _recorrer_hasta_gate_2_rechazado()
    capsys.readouterr()
    cli.main(["fallo"])
    log = capsys.readouterr().out
    for texto in (resumen.read_text(encoding="utf-8"), log):
        assert "| Gate 1 | Fase 4: Security Gate 1 | Aprobado |" in texto
        assert "| Gate 2 | Fase 8: Security Gate 2 | Rechazado |" in texto
        assert "| Gate 3 | Fase 11: DAST y Security Gate 3 | No ejecutado |" in texto


def test_el_resumen_no_impide_el_aviso_si_no_se_puede_escribir(
    telegram_falso, monkeypatch, tmp_path
):
    envios, _, _ = telegram_falso
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path))  # una carpeta, no un archivo
    cli.main(["inicio"])
    assert cli.main(["fin"]) == 0
    assert envios[-1].startswith("✅")


def test_uso_incorrecto():
    assert cli.main(["ejecutar", "Fase 1"]) == 2
    assert cli.main(["omitir"]) == 2
    assert cli.main(["desconocida"]) == 2


def test_las_fases_del_workflow_coinciden_con_el_notificador():
    """Un nombre distinto en el workflow crearía una fila nueva en el mensaje de Telegram."""
    texto = WORKFLOW.read_text(encoding="utf-8")
    usadas = re.findall(r'notify\.cli (?:ejecutar|omitir) "([^"]+)"', texto)
    assert sorted(set(usadas)) == sorted(cli.FASES)
    assert "notify.cli inicio" in texto and "notify.cli fin" in texto
    assert "notify.cli fallo" in texto
    assert "notify.cli cancelado" in texto


def _pasos_del_workflow() -> list[dict]:
    flujo = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return flujo["jobs"]["pipeline"]["steps"]


def test_los_gates_estan_encadenados_en_orden():
    pasos = _pasos_del_workflow()
    posiciones = [
        next(i for i, paso in enumerate(pasos) if f'ejecutar "{fase}"' in paso.get("run", ""))
        for fase in cli.GATES.values()
    ]
    assert posiciones == sorted(posiciones)
    for numero, posicion in enumerate(posiciones, start=1):
        assert f"scripts/gate{numero}.sh" in pasos[posicion]["run"]


def test_ningun_paso_de_fase_se_salta_la_cadena():
    """Un "if" o continue-on-error dejaría correr una fase tras un gate rechazado."""
    pasos = [p for p in _pasos_del_workflow() if "notify.cli ejecutar" in p.get("run", "")]
    pasos += [p for p in _pasos_del_workflow() if "notify.cli omitir" in p.get("run", "")]
    assert len(pasos) == len(cli.FASES)
    for paso in pasos:
        assert "if" not in paso and "continue-on-error" not in paso, paso["name"]


def test_cada_final_de_la_cadena_tiene_su_aviso():
    condiciones = {
        orden: paso.get("if")
        for paso in _pasos_del_workflow()
        for orden in ("fin", "fallo", "cancelado")
        if f"notify.cli {orden}" in paso.get("run", "")
    }
    assert condiciones == {"fin": "success()", "fallo": "failure()", "cancelado": "cancelled()"}
