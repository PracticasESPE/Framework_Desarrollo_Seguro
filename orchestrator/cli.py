"""Interfaz de línea de comandos del framework."""

from pathlib import Path
from typing import Annotated

import typer

from orchestrator import __version__
from orchestrator.config import obtener_configuracion
from orchestrator.fases import FASES, obtener_fase

app = typer.Typer(
    name="framework",
    help="Framework de desarrollo seguro guiado por conocimiento.",
    no_args_is_help=True,
    add_completion=False,
)


def _mostrar_version(valor: bool) -> None:
    if valor:
        typer.echo(f"framework {__version__}")
        raise typer.Exit()


@app.callback()
def principal(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_mostrar_version,
            is_eager=True,
            help="Muestra la versión y termina.",
        ),
    ] = False,
) -> None:
    """Framework de desarrollo seguro guiado por conocimiento."""


@app.command()
def run(
    documento: Annotated[
        Path | None,
        typer.Argument(help="Documento de requisitos (PDF, DOCX o TXT)."),
    ] = None,
    fase: Annotated[
        int | None,
        typer.Option("--fase", min=1, max=len(FASES), help="Ejecuta solo la fase indicada (1-11)."),
    ] = None,
    entrada: Annotated[
        Path | None,
        typer.Option("--entrada", help="Carpeta con los documentos de requisitos."),
    ] = None,
    nivel: Annotated[
        str,
        typer.Option("--nivel", help="Nivel de seguridad exigido: bajo, medio o alto."),
    ] = "medio",
) -> None:
    """Ejecuta el pipeline completo o una sola fase."""
    if nivel not in {"bajo", "medio", "alto"}:
        raise typer.BadParameter("debe ser bajo, medio o alto", param_hint="--nivel")

    origen = documento or entrada
    if origen is not None and not origen.exists():
        raise typer.BadParameter(f"no existe la ruta '{origen}'")

    seleccionadas = [obtener_fase(fase)] if fase is not None else list(FASES)
    for actual in seleccionadas:
        typer.echo(f"Fase {actual.numero}: {actual.nombre} - aún no implementada")


@app.command()
def fases() -> None:
    """Lista las fases del pipeline."""
    for fase in FASES:
        marca = " [gate]" if fase.es_gate else ""
        typer.echo(f"{fase.numero:>2}. {fase.nombre}{marca}")


@app.command()
def config() -> None:
    """Muestra la configuración activa sin revelar secretos."""
    for clave, valor in obtener_configuracion().resumen().items():
        typer.echo(f"{clave}: {valor}")


@app.command()
def api(
    host: Annotated[str, typer.Option("--host", help="Dirección de escucha.")] = "127.0.0.1",
    puerto: Annotated[int, typer.Option("--puerto", help="Puerto de escucha.")] = 8000,
    recarga: Annotated[
        bool, typer.Option("--recarga", help="Recarga automática al cambiar el código.")
    ] = False,
) -> None:
    """Levanta la API del motor."""
    import uvicorn

    uvicorn.run("orchestrator.api:app", host=host, port=puerto, reload=recarga)


if __name__ == "__main__":
    app()
