"""Notificador de Telegram: un mensaje de progreso que se edita.

Principios (plan técnico 8.3):
- La notificación NUNCA detiene el pipeline: todo error se traga y se devuelve None/False.
- Sin datos sensibles: solo resúmenes y enlaces; nunca código ni rutas vulnerables.
- El token no se escribe en logs (la URL con el token no aparece en ningún mensaje).
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass, field

import httpx

TIEMPO_ESPERA = 10
ICONOS = {"pendiente": "⏳", "ejecutando": "🔄", "ok": "✅", "fallo": "❌"}


def _config() -> tuple[str, str] | None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    return (token, chat) if token and chat else None


def _post(metodo: str, datos: dict, cliente: httpx.Client | None = None) -> dict | None:
    cfg = _config()
    if cfg is None:
        return None
    token, chat = cfg
    try:
        c = cliente or httpx.Client(timeout=TIEMPO_ESPERA)
        r = c.post(
            f"https://api.telegram.org/bot{token}/{metodo}",
            json={"chat_id": chat, **datos},
        )
        cuerpo = r.json()
        return cuerpo if cuerpo.get("ok") else None
    except Exception:
        return None  # la notificación nunca detiene el pipeline


def enviar(texto: str, cliente: httpx.Client | None = None) -> int | None:
    """Envía un mensaje nuevo y devuelve su message_id (o None si falla)."""
    cuerpo = _post("sendMessage", {"text": texto}, cliente)
    return cuerpo["result"]["message_id"] if cuerpo else None


def actualizar(message_id: int, texto: str, cliente: httpx.Client | None = None) -> bool:
    """Edita un mensaje existente. Devuelve True si Telegram lo aceptó."""
    datos = {"message_id": message_id, "text": texto}
    return _post("editMessageText", datos, cliente) is not None


@dataclass
class Progreso:
    """Mensaje de progreso único: se crea al inicio y se edita en cada cambio de fase."""

    titulo: str
    enlace: str = ""
    fases: dict[str, str] = field(default_factory=dict)
    message_id: int | None = None
    cliente: httpx.Client | None = None

    def _texto(self) -> str:
        lineas = [self.titulo]
        lineas += [f"{ICONOS[e]} {nombre}" for nombre, e in self.fases.items()]
        if self.enlace:
            lineas.append(f"🔗 {self.enlace}")
        return "\n".join(lineas)

    def iniciar(self, nombres_fases: list[str]) -> None:
        self.fases = {n: "pendiente" for n in nombres_fases}
        self.message_id = enviar(self._texto(), self.cliente)

    def marcar(self, fase: str, estado: str) -> None:
        if estado not in ICONOS:
            raise ValueError(f"estado desconocido: {estado}")
        self.fases[fase] = estado
        if self.message_id is None:  # el envío inicial falló: se reintenta como mensaje nuevo
            self.message_id = enviar(self._texto(), self.cliente)
        else:
            actualizar(self.message_id, self._texto(), self.cliente)


if __name__ == "__main__":
    # Demostración para la captura: uv run python -m orchestrator.notify.telegram
    if _config() is None:
        sys.exit("Faltan TELEGRAM_BOT_TOKEN y/o TELEGRAM_CHAT_ID en el entorno.")
    p = Progreso(
        "Framework de desarrollo seguro - prueba del notificador",
        "https://github.com/PracticasESPE/Framework_Desarrollo_Seguro/actions",
    )
    p.iniciar(
        [
            "Fase 1: Requisitos",
            "Fase 2: Arquitectura",
            "Fase 3: Generación",
            "Fase 4: Security Gate 1",
        ]
    )
    if p.message_id is None:
        sys.exit("Telegram no respondió: revisa el token, el chat id y que el bot esté en el chat.")
    for fase in list(p.fases):
        time.sleep(2)
        p.marcar(fase, "ejecutando")
        time.sleep(3)
        p.marcar(fase, "ok")
    print(f"Listo: mensaje {p.message_id} editado {len(p.fases) * 2} veces.")
