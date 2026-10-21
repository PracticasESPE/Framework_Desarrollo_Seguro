"""Comandos del notificador para el workflow (un mensaje de Telegram por ejecución).

  python -m orchestrator.notify.cli inicio
  python -m orchestrator.notify.cli ejecutar "Fase 4: Security Gate 1" -- bash scripts/gate1.sh
  python -m orchestrator.notify.cli omitir "Fase 1: Requisitos"
  python -m orchestrator.notify.cli fin
  python -m orchestrator.notify.cli fallo

El estado (id del mensaje y fases) se guarda en un JSON entre pasos del mismo job.
Si Telegram falla, o no hay estado, el comando de la fase se ejecuta igual.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from orchestrator.notify import telegram

# Una fila por paso de fase del workflow (.github/workflows/framework.yml), con el mismo nombre.
FASES = [
    "Fase 1: Requisitos",
    "Fase 2: Arquitectura",
    "Fase 3: Generación",
    "Fase 4: Security Gate 1",
    "Fases 5-6: Refinamiento",
    "Fase 7: Integración",
    "Fase 8: Security Gate 2",
    "Fase 9: Pruebas",
    "Fase 10: Contenedores",
    "Fase 11: DAST y Security Gate 3",
]

# Las credenciales solo las usa el notificador; los comandos de cada fase no las reciben.
_SECRETOS = ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID")


def _ruta() -> Path:
    return Path(
        os.environ.get("NOTIFY_ESTADO")
        or Path(os.environ.get("RUNNER_TEMP", ".")) / "notify_estado.json"
    )


def _enlace() -> str:
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run = os.environ.get("GITHUB_RUN_ID")
    return f"{server}/{repo}/actions/runs/{run}" if repo and run else ""


def _guardar(p: telegram.Progreso) -> None:
    datos = {"titulo": p.titulo, "enlace": p.enlace, "fases": p.fases, "message_id": p.message_id}
    _ruta().write_text(json.dumps(datos), encoding="utf-8")


def _cargar() -> telegram.Progreso | None:
    try:
        d = json.loads(_ruta().read_text(encoding="utf-8"))
        return telegram.Progreso(d["titulo"], d["enlace"], d["fases"], d["message_id"])
    except Exception:
        return None


def _marcar(p: telegram.Progreso | None, fase: str, estado: str) -> None:
    if p is None:
        return
    try:
        p.marcar(fase, estado)
        _guardar(p)
    except Exception:
        pass  # la notificación nunca bloquea el pipeline


def inicio() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "framework")
    # En un pull request GITHUB_REF_NAME es "<n>/merge"; GITHUB_HEAD_REF trae la rama real.
    rama = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME", "local")
    numero = os.environ.get("GITHUB_RUN_NUMBER", "0")
    p = telegram.Progreso(f"Pipeline {repo} · rama {rama} · ejecución #{numero}", _enlace())
    try:
        p.iniciar(FASES)
        _guardar(p)
    except Exception:
        pass
    return 0


def ejecutar(fase: str, comando: list[str]) -> int:
    """Marca la fase en curso, ejecuta el comando y devuelve su código de salida."""
    p = _cargar()
    _marcar(p, fase, "ejecutando")
    entorno = {k: v for k, v in os.environ.items() if k not in _SECRETOS}
    try:
        codigo = subprocess.call(comando, env=entorno)
    except OSError as error:  # comando inexistente o sin permisos
        print(f"No se pudo ejecutar {comando[0]!r}: {error}", file=sys.stderr)
        codigo = 127
    _marcar(p, fase, "ok" if codigo == 0 else "fallo")
    return codigo


def omitir(fase: str) -> int:
    """Marca una fase que todavía no está implementada en el pipeline."""
    _marcar(_cargar(), fase, "omitida")
    return 0


def fin() -> int:
    telegram.enviar("✅ Pipeline terminado correctamente\n" + _enlace())
    return 0


def fallo() -> int:
    p = _cargar()
    if p is not None:
        for fase, estado in list(p.fases.items()):
            if estado == "ejecutando":
                _marcar(p, fase, "fallo")
    telegram.enviar("❌ El pipeline falló. Revisa los registros:\n" + _enlace())
    return 0


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 0
    orden = argv[0]
    if orden == "ejecutar":
        if "--" not in argv or len(argv) < 4:
            print('Uso: ejecutar "Nombre de fase" -- comando args...')
            return 2
        i = argv.index("--")
        return ejecutar(argv[1], argv[i + 1 :])
    if orden == "omitir":
        if len(argv) != 2:
            print('Uso: omitir "Nombre de fase"')
            return 2
        return omitir(argv[1])
    acciones = {"inicio": inicio, "fin": fin, "fallo": fallo}
    if orden in acciones:
        try:
            return acciones[orden]()
        except Exception:
            return 0
    print(f"Orden desconocida: {orden}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
