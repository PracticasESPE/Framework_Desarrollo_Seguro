"""Comandos del notificador que usa el workflow (orchestrator/notify/cli.py)."""

import json
import re
import sys
from pathlib import Path

import pytest

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
