"""API del motor del framework."""

from fastapi import FastAPI

from orchestrator import __version__
from orchestrator.config import obtener_configuracion
from orchestrator.fases import FASES, Fase

app = FastAPI(
    title="Framework de desarrollo seguro",
    description="API del motor del framework de desarrollo seguro guiado por conocimiento.",
    version=__version__,
)


@app.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok", "version": __version__}


@app.get("/fases")
def listar_fases() -> list[Fase]:
    return list(FASES)


@app.get("/configuracion")
def ver_configuracion() -> dict[str, object]:
    return obtener_configuracion().resumen()
