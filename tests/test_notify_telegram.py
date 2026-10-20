import json

import httpx
import pytest

from orchestrator.notify import telegram as t


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:TOKEN-DE-PRUEBA")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100999")


def cliente(respuestas, llamadas):
    def manejador(req: httpx.Request):
        llamadas.append((req.url.path.rsplit("/", 1)[-1], json.loads(req.content)))
        return respuestas.pop(0)

    return httpx.Client(transport=httpx.MockTransport(manejador))


def ok(**extra):
    return httpx.Response(200, json={"ok": True, "result": {"message_id": 7, **extra}})


def test_enviar_devuelve_message_id():
    llamadas = []
    assert t.enviar("hola", cliente([ok()], llamadas)) == 7
    assert llamadas == [("sendMessage", {"chat_id": "-100999", "text": "hola"})]


def test_sin_credenciales_no_hace_nada(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    assert t.enviar("hola") is None


def test_error_de_red_no_lanza_excepcion():
    def falla(req):
        raise httpx.ConnectError("sin red")

    c = httpx.Client(transport=httpx.MockTransport(falla))
    assert t.enviar("hola", c) is None
    assert t.actualizar(1, "hola", c) is False


def test_respuesta_ok_false_se_trata_como_fallo():
    r = httpx.Response(400, json={"ok": False, "description": "Bad Request"})
    assert t.enviar("hola", cliente([r], [])) is None


def test_progreso_edita_el_mismo_mensaje():
    llamadas = []
    p = t.Progreso("Titulo", "https://ejemplo/run/1", cliente=cliente([ok(), ok(), ok()], llamadas))
    p.iniciar(["Fase 1", "Fase 2"])
    p.marcar("Fase 1", "ejecutando")
    p.marcar("Fase 1", "ok")
    assert [m for m, _ in llamadas] == ["sendMessage", "editMessageText", "editMessageText"]
    assert llamadas[2][1]["message_id"] == 7
    assert "✅ Fase 1" in llamadas[2][1]["text"] and "⏳ Fase 2" in llamadas[2][1]["text"]


def test_progreso_reenvia_si_el_primer_envio_fallo():
    llamadas = []
    respuestas = [httpx.Response(500, json={"ok": False}), ok()]
    p = t.Progreso("Titulo", cliente=cliente(respuestas, llamadas))
    p.iniciar(["Fase 1"])
    assert p.message_id is None
    p.marcar("Fase 1", "ok")
    assert p.message_id == 7


def test_estado_invalido():
    p = t.Progreso("T", fases={"F": "pendiente"}, message_id=1)
    with pytest.raises(ValueError):
        p.marcar("F", "raro")


def test_demo_toma_las_credenciales_del_env(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN")
    monkeypatch.delenv("TELEGRAM_CHAT_ID")
    (tmp_path / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=999:DESDE-ENV\nTELEGRAM_CHAT_ID=-42\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    t._cargar_desde_env()
    assert t._config() == ("999:DESDE-ENV", "-42")
