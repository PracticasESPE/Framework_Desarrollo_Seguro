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
    sarif: Annotated[
        Path | None,
        typer.Option("--sarif", help="Carpeta con los SARIF del Gate 1 (fase 4)."),
    ] = None,
    grafo: Annotated[
        bool | None,
        typer.Option(
            "--grafo/--sin-grafo",
            help="Registrar los hallazgos en Neo4j. Por defecto, solo si NEO4J_PASSWORD existe.",
        ),
    ] = None,
    ejecucion: Annotated[
        str | None,
        typer.Option("--ejecucion", help="Ejecución de Neo4j a la que se añaden los hallazgos."),
    ] = None,
    descripcion: Annotated[
        str | None,
        typer.Option(
            "--descripcion", help="Descripción de la ejecución en Neo4j si no hay documento."
        ),
    ] = None,
) -> None:
    """Ejecuta el pipeline completo o una sola fase."""
    if nivel not in {"bajo", "medio", "alto"}:
        raise typer.BadParameter("debe ser bajo, medio o alto", param_hint="--nivel")

    origen = documento or entrada
    if origen is not None and not origen.exists():
        raise typer.BadParameter(f"no existe la ruta '{origen}'")

    seleccionadas = [obtener_fase(fase)] if fase is not None else list(FASES)
    for actual in seleccionadas:
        if actual.numero == 4:
            _ejecutar_fase4(sarif, grafo, ejecucion, str(origen) if origen else descripcion)
        else:
            typer.echo(f"Fase {actual.numero}: {actual.nombre} - aún no implementada")


def _ejecutar_fase4(
    sarif: Path | None, grafo: bool | None, ejecucion: str | None, documento: str | None
) -> None:
    from orchestrator.gates.fase4 import (
        ErrorFase,
        ejecutar_fase4,
        guardar_resultado,
        publicar_resumen_en_actions,
        resumen_markdown,
    )

    config = obtener_configuracion()
    typer.echo(f"Fase 4: {obtener_fase(4).nombre}")
    try:
        resultado = ejecutar_fase4(config, sarif, grafo, ejecucion, documento)
    except ErrorFase as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    destino = guardar_resultado(resultado, config)
    typer.echo(f"  SARIF leídos: {', '.join(resultado.archivos_sarif)}")
    typer.echo(f"  Hallazgos: {resultado.total}")
    for severidad, total in resultado.por_severidad.items():
        typer.echo(f"    {severidad}: {total}")
    for herramienta, total in resultado.por_herramienta.items():
        typer.echo(f"    {herramienta}: {total}")
    if resultado.registrado_en_grafo:
        typer.echo(f"  Registrados en Neo4j, ejecución {resultado.ejecucion_id}")
    else:
        typer.echo(f"  Sin registro en Neo4j: {resultado.motivo_sin_grafo}")
    typer.echo(f"  Resultado guardado en {destino.as_posix()}")
    publicar_resumen_en_actions(resumen_markdown(resultado))


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


grafo_app = typer.Typer(help="Base de conocimiento en Neo4j.", no_args_is_help=True)
app.add_typer(grafo_app, name="grafo")


@grafo_app.command("esquema")
def grafo_esquema() -> None:
    """Aplica las restricciones e índices de los scripts de graph/."""
    from orchestrator.knowledge import ErrorGrafo, aplicar_esquema, conectar

    config = obtener_configuracion()
    try:
        driver = conectar(config)
        try:
            aplicadas = aplicar_esquema(driver, config.neo4j_database)
        finally:
            driver.close()
    except ErrorGrafo as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo(f"Esquema aplicado: {aplicadas} sentencias en {config.neo4j_uri}")


@grafo_app.command("estado")
def grafo_estado() -> None:
    """Lista las restricciones e índices presentes en Neo4j."""
    from orchestrator.knowledge import ErrorGrafo, conectar, estado_esquema

    config = obtener_configuracion()
    try:
        driver = conectar(config)
        try:
            estado = estado_esquema(driver, config.neo4j_database)
        finally:
            driver.close()
    except ErrorGrafo as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Restricciones ({len(estado['restricciones'])}):")
    for r in estado["restricciones"]:
        typer.echo(f"  {r['name']}: {r['type']} {r['labelsOrTypes']} {r['properties']}")
    typer.echo(f"Índices ({len(estado['indices'])}):")
    for i in estado["indices"]:
        origen = f" (de {i['owningConstraint']})" if i.get("owningConstraint") else ""
        typer.echo(
            f"  {i['name']}: {i['type']} {i['labelsOrTypes']} {i['properties']} "
            f"{i['state']}{origen}"
        )


@grafo_app.command("resumen")
def grafo_resumen() -> None:
    """Cuenta los nodos por etiqueta y las relaciones por tipo."""
    from orchestrator.knowledge import ErrorGrafo, conectar, resumen_grafo

    config = obtener_configuracion()
    try:
        driver = conectar(config)
        try:
            resumen = resumen_grafo(driver, config.neo4j_database)
        finally:
            driver.close()
    except ErrorGrafo as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo("Nodos:")
    for etiqueta, total in resumen["nodos"].items() or [("(ninguno)", 0)]:
        typer.echo(f"  {etiqueta}: {total}")
    typer.echo("Relaciones:")
    for relacion, total in resumen["relaciones"].items() or [("(ninguna)", 0)]:
        typer.echo(f"  {relacion}: {total}")


hallazgos_app = typer.Typer(
    help="Hallazgos de seguridad registrados en Neo4j.", no_args_is_help=True
)
app.add_typer(hallazgos_app, name="hallazgos")


@hallazgos_app.command("registrar")
def hallazgos_registrar(
    origen: Annotated[Path, typer.Argument(help="Archivo .sarif o carpeta con archivos .sarif.")],
    ejecucion: Annotated[
        str | None,
        typer.Option("--ejecucion", help="Ejecución existente; si se omite se crea una nueva."),
    ] = None,
    documento: Annotated[
        str | None, typer.Option("--documento", help="Documento de requisitos de la ejecución.")
    ] = None,
    fase: Annotated[
        int, typer.Option("--fase", min=1, max=len(FASES), help="Fase que produjo los hallazgos.")
    ] = 4,
) -> None:
    """Lee resultados SARIF y los registra como nodos Hallazgo de una ejecución."""
    from orchestrator.gates import ErrorSarif, contar_por_severidad, leer_carpeta_sarif, leer_sarif
    from orchestrator.knowledge import (
        ErrorGrafo,
        conectar,
        crear_ejecucion,
        registrar_hallazgos,
    )

    if not origen.exists():
        raise typer.BadParameter(f"no existe la ruta '{origen}'", param_hint="ORIGEN")
    try:
        hallazgos = leer_carpeta_sarif(origen) if origen.is_dir() else leer_sarif(origen)
    except ErrorSarif as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    config = obtener_configuracion()
    try:
        driver = conectar(config)
        try:
            ejecucion_id = ejecucion or crear_ejecucion(
                driver, documento=documento, base_datos=config.neo4j_database
            )
            registrados = registrar_hallazgos(
                driver, ejecucion_id, hallazgos, fase=fase, base_datos=config.neo4j_database
            )
        finally:
            driver.close()
    except ErrorGrafo as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Ejecución: {ejecucion_id}")
    typer.echo(f"Hallazgos registrados: {registrados}")
    for severidad, total in contar_por_severidad(hallazgos).items():
        typer.echo(f"  {severidad}: {total}")


@hallazgos_app.command("listar")
def hallazgos_listar(
    ejecucion: Annotated[
        str | None,
        typer.Option("--ejecucion", help="Ejecución a consultar; por defecto la más reciente."),
    ] = None,
) -> None:
    """Muestra los hallazgos de una ejecución, del más grave al más leve."""
    from orchestrator.knowledge import ErrorGrafo, conectar, listar_hallazgos, ultima_ejecucion

    config = obtener_configuracion()
    try:
        driver = conectar(config)
        try:
            ejecucion_id = ejecucion or ultima_ejecucion(driver, config.neo4j_database)
            filas = (
                listar_hallazgos(driver, ejecucion_id, config.neo4j_database)
                if ejecucion_id
                else []
            )
        finally:
            driver.close()
    except ErrorGrafo as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from error

    if ejecucion_id is None:
        typer.echo("No hay ejecuciones registradas.")
        return
    typer.echo(f"Ejecución: {ejecucion_id} ({len(filas)} hallazgos)")
    for f in filas:
        ubicacion = f"{f['archivo']}:{f['linea_inicio']}" if f["archivo"] else "-"
        cwe = ", ".join(f["cwe"] or []) or "-"
        typer.echo(f"  [{f['severidad']}] {f['herramienta']} {f['regla_id']} {ubicacion} {cwe}")


conocimiento_app = typer.Typer(
    help="Base de conocimiento en YAML (knowledge_base/).", no_args_is_help=True
)
app.add_typer(conocimiento_app, name="conocimiento")


@conocimiento_app.command("validar")
def conocimiento_validar(
    raiz: Annotated[
        Path | None, typer.Option("--raiz", help="Carpeta de la base de conocimiento.")
    ] = None,
) -> None:
    """Valida todos los archivos YAML de la base de conocimiento."""
    from orchestrator.knowledge.base_conocimiento import (
        RAIZ_POR_DEFECTO,
        ErrorBaseConocimiento,
        cargar_base_conocimiento,
    )

    try:
        base = cargar_base_conocimiento(raiz or RAIZ_POR_DEFECTO)
    except ErrorBaseConocimiento as error:
        typer.echo(f"Base de conocimiento inválida ({len(error.errores)} error(es)):", err=True)
        for detalle in error.errores:
            typer.echo(f"  - {detalle}", err=True)
        raise typer.Exit(1) from error

    typer.echo("Base de conocimiento válida")
    for clave, valor in base.resumen().items():
        typer.echo(f"  {clave}: {valor}")


@conocimiento_app.command("cargar")
def conocimiento_cargar(
    raiz: Annotated[
        Path | None, typer.Option("--raiz", help="Carpeta de la base de conocimiento.")
    ] = None,
) -> None:
    """Valida la base de conocimiento y la carga en Neo4j como nodos y relaciones."""
    from orchestrator.knowledge import ErrorGrafo, aplicar_esquema, conectar
    from orchestrator.knowledge.base_conocimiento import (
        RAIZ_POR_DEFECTO,
        ErrorBaseConocimiento,
        cargar_base_conocimiento,
    )
    from orchestrator.knowledge.cargador import calcular_version, cargar_en_grafo

    carpeta = raiz or RAIZ_POR_DEFECTO
    try:
        base = cargar_base_conocimiento(carpeta)
    except ErrorBaseConocimiento as error:
        typer.echo(f"Base de conocimiento inválida ({len(error.errores)} error(es)):", err=True)
        for detalle in error.errores:
            typer.echo(f"  - {detalle}", err=True)
        raise typer.Exit(1) from error

    config = obtener_configuracion()
    try:
        driver = conectar(config)
    except ErrorGrafo as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    try:
        aplicar_esquema(driver, config.neo4j_database)
        resultado = cargar_en_grafo(
            driver, base, calcular_version(carpeta), base_datos=config.neo4j_database
        )
    except ErrorGrafo as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    finally:
        driver.close()

    typer.echo(f"Conocimiento cargado en Neo4j (versión {resultado['version']})")
    typer.echo("  Nodos:")
    for etiqueta, total in resultado["nodos"].items():
        typer.echo(f"    {etiqueta}: {total}")
    typer.echo("  Relaciones:")
    for tipo, total in sorted(resultado["relaciones"].items()):
        typer.echo(f"    {tipo}: {total}")
    typer.echo(
        f"  Retirados de versiones anteriores: {resultado['nodos_retirados']} nodos, "
        f"{resultado['relaciones_retiradas']} relaciones"
    )


@conocimiento_app.command("embeddings")
def conocimiento_embeddings(
    raiz: Annotated[
        Path | None, typer.Option("--raiz", help="Carpeta de la base de conocimiento.")
    ] = None,
) -> None:
    """Carga el conocimiento, genera sus fragmentos con embeddings y crea el índice vectorial."""
    from orchestrator.knowledge import ErrorGrafo, aplicar_esquema, conectar
    from orchestrator.knowledge.base_conocimiento import (
        RAIZ_POR_DEFECTO,
        ErrorBaseConocimiento,
        cargar_base_conocimiento,
    )
    from orchestrator.knowledge.cargador import calcular_version, cargar_en_grafo
    from orchestrator.knowledge.embeddings import EmbeddingsLocales, ErrorEmbeddings
    from orchestrator.knowledge.fragmentos import cargar_fragmentos

    carpeta = raiz or RAIZ_POR_DEFECTO
    try:
        base = cargar_base_conocimiento(carpeta)
    except ErrorBaseConocimiento as error:
        typer.echo(f"Base de conocimiento inválida ({len(error.errores)} error(es)):", err=True)
        for detalle in error.errores:
            typer.echo(f"  - {detalle}", err=True)
        raise typer.Exit(1) from error

    config = obtener_configuracion()
    typer.echo(f"Cargando el modelo de embeddings {config.embeddings_modelo}...")
    try:
        proveedor = EmbeddingsLocales(config.embeddings_modelo, config.embeddings_cache)
        driver = conectar(config)
    except (ErrorEmbeddings, ErrorGrafo) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    try:
        version = calcular_version(carpeta)
        aplicar_esquema(driver, config.neo4j_database)
        cargar_en_grafo(driver, base, version, base_datos=config.neo4j_database)
        resultado = cargar_fragmentos(
            driver, base, proveedor, version, base_datos=config.neo4j_database
        )
    except (ErrorEmbeddings, ErrorGrafo) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    finally:
        driver.close()

    typer.echo("Fragmentos con embeddings cargados en Neo4j")
    typer.echo(f"  Modelo: {resultado['modelo']} ({resultado['dimensiones']} dimensiones)")
    typer.echo(f"  Índice vectorial: {resultado['indice']} ({resultado['estado_indice']})")
    typer.echo(f"  Fragmentos: {resultado['fragmentos']}")
    typer.echo(f"  Relaciones DESCRIBE: {resultado['enlaces_describe']}")
    typer.echo(
        f"  Fragmentos retirados de versiones anteriores: {resultado['fragmentos_retirados']}"
    )


@conocimiento_app.command("consultar")
def conocimiento_consultar(
    pregunta: Annotated[str, typer.Argument(help="Pregunta en lenguaje natural.")],
    k: Annotated[
        int, typer.Option("--k", min=1, max=20, help="Fragmentos más parecidos a recuperar.")
    ] = 5,
    umbral: Annotated[
        float, typer.Option("--umbral", min=0.0, max=1.0, help="Parecido mínimo (0 a 1).")
    ] = 0.0,
    contexto: Annotated[
        bool, typer.Option("--contexto", help="Muestra el texto que recibiría el LLM.")
    ] = False,
) -> None:
    """Consulta GraphRAG: fragmentos parecidos a la pregunta y el conocimiento conectado."""
    from orchestrator.knowledge import ErrorGrafo, conectar
    from orchestrator.knowledge.embeddings import EmbeddingsLocales, ErrorEmbeddings
    from orchestrator.knowledge.graphrag import consultar

    config = obtener_configuracion()
    try:
        proveedor = EmbeddingsLocales(config.embeddings_modelo, config.embeddings_cache)
        driver = conectar(config)
    except (ErrorEmbeddings, ErrorGrafo) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    try:
        resultado = consultar(
            driver, proveedor, pregunta, k=k, umbral=umbral, base_datos=config.neo4j_database
        )
    except (ErrorEmbeddings, ErrorGrafo) as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error
    finally:
        driver.close()

    if contexto:
        typer.echo(resultado.a_texto())
        return

    typer.echo(f"Pregunta: {pregunta}")
    if not resultado.coincidencias:
        typer.echo("Sin resultados. ¿Se cargaron los embeddings con 'conocimiento embeddings'?")
        return
    typer.echo("\nFragmentos más parecidos (búsqueda vectorial):")
    for c in resultado.coincidencias:
        typer.echo(f"  {c.puntuacion:.3f}  [{c.origen_tipo}] {c.origen_id}")
    typer.echo("\nConocimiento conectado (grafo):")
    secciones = [
        ("CWE", resultado.cwe),
        ("Patrones", resultado.patrones),
        ("Directrices", resultado.directrices),
        ("Controles ASVS", resultado.controles),
        ("Riesgos API Top 10", resultado.riesgos),
    ]
    for titulo, elementos in secciones:
        typer.echo(f"  {titulo} ({len(elementos)}):")
        for e in elementos:
            typer.echo(f"    - {e.id}: {e.nombre}")


if __name__ == "__main__":
    app()
