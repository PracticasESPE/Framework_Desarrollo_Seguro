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
    # Un error no controlado no debe imprimir las variables locales: entre ellas está la
    # configuración, y un secreto pegado en una variable que no es SecretStr quedaría a la vista.
    pretty_exceptions_show_locals=False,
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


gates_app = typer.Typer(
    help="Decisiones de los Security Gates con OPA (policies/gates).", no_args_is_help=True
)
app.add_typer(gates_app, name="gates")


def _ejecucion_del_pipeline(salida: Path) -> str | None:
    """Ejecución de Neo4j de este mismo pipeline: la de la fase 4 o la del primer gate decidido."""
    import json

    for archivo in (salida / "hallazgos" / "fase4.json", salida / "gates" / "ejecucion.json"):
        try:
            ejecucion_id = json.loads(archivo.read_text(encoding="utf-8")).get("ejecucion_id")
        except (OSError, ValueError, AttributeError):
            continue
        if ejecucion_id:
            return ejecucion_id
    return None


def _guardar_ejecucion_del_pipeline(salida: Path, ejecucion_id: str) -> None:
    """Deja la ejecución creada para que los demás gates del pipeline se registren en ella."""
    import json

    archivo = salida / "gates" / "ejecucion.json"
    archivo.parent.mkdir(parents=True, exist_ok=True)
    archivo.write_text(json.dumps({"ejecucion_id": ejecucion_id}), encoding="utf-8")


@gates_app.command("decidir")
def gates_decidir(
    gate: Annotated[int, typer.Option("--gate", min=1, max=3, help="Gate a decidir (1, 2 o 3).")],
    sarif: Annotated[
        Path | None, typer.Option("--sarif", help="Carpeta con los SARIF de los gates.")
    ] = None,
    compilacion_ok: Annotated[
        bool,
        typer.Option("--compilacion-ok", help="Gate 1: el código compiló (fase 3 correcta)."),
    ] = False,
    grafo: Annotated[
        bool | None,
        typer.Option(
            "--grafo/--sin-grafo",
            help="Registrar la decisión en Neo4j. Por defecto, solo si NEO4J_PASSWORD existe.",
        ),
    ] = None,
    ejecucion: Annotated[
        str | None,
        typer.Option(
            "--ejecucion", help="Ejecución de Neo4j; por defecto la de la fase 4 o una nueva."
        ),
    ] = None,
    bloquear: Annotated[
        bool,
        typer.Option(
            "--bloquear/--no-bloquear", help="Terminar con código 1 si el gate se rechaza."
        ),
    ] = True,
    carpeta_salida: Annotated[
        Path | None,
        typer.Option(
            "--salida", help="Carpeta de resultados del pipeline; por defecto la configurada."
        ),
    ] = None,
) -> None:
    """Pide a OPA la decisión de un gate, la muestra, la guarda y la registra en Neo4j."""
    import json

    from orchestrator.gates.decision import (
        FASE_DEL_GATE,
        ErrorDecision,
        construir_entrada,
        evaluar,
        resumen_markdown,
    )
    from orchestrator.gates.fase4 import publicar_resumen_en_actions

    config = obtener_configuracion()
    salida = carpeta_salida or config.directorio_salida
    entrada = construir_entrada(gate, salida, sarif, compilacion_ok)
    try:
        decision = evaluar(entrada)
    except ErrorDecision as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    destino = config.directorio_salida / "gates" / f"gate{gate}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(
            {"entrada": entrada.datos, "decision": decision.model_dump()},
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    estado = "APROBADO" if decision.aprobado else "RECHAZADO"
    typer.echo(f"Gate {gate}: {estado}")
    typer.echo(f"  {decision.justificacion}")
    for criterio in decision.criterios:
        marca = "cumple   " if criterio.cumple else "NO cumple"
        typer.echo(f"  [{marca}] {criterio.regla}: {criterio.detalle}")
    for bloqueante in decision.bloqueantes:
        typer.echo(f"  Bloqueante {bloqueante.regla}: {bloqueante.motivo}")
    if decision.advertencias:
        typer.echo(f"  Advertencias (no bloquean): {len(decision.advertencias)}")
    typer.echo(f"  Decisión guardada en {destino.as_posix()}")

    usar_grafo = grafo if grafo is not None else config.neo4j_password is not None
    if usar_grafo:
        from orchestrator.knowledge import (
            ErrorGrafo,
            conectar,
            crear_ejecucion,
            registrar_hallazgos,
            registrar_resultado_gate,
        )

        try:
            driver = conectar(config)
            try:
                db = config.neo4j_database
                ejecucion_id = ejecucion or _ejecucion_del_pipeline(config.directorio_salida)
                if ejecucion_id is None:
                    ejecucion_id = crear_ejecucion(
                        driver, documento="Decisión de gates", base_datos=db
                    )
                    _guardar_ejecucion_del_pipeline(config.directorio_salida, ejecucion_id)
                registrar_hallazgos(
                    driver, ejecucion_id, entrada.hallazgos, fase=FASE_DEL_GATE[gate], base_datos=db
                )
                registrar_resultado_gate(driver, ejecucion_id, decision, base_datos=db)
            finally:
                driver.close()
        except ErrorGrafo as error:
            typer.echo(f"  Sin registro en Neo4j: {error}", err=True)
        else:
            typer.echo(f"  Registrada en Neo4j, ejecución {ejecucion_id}")

    publicar_resumen_en_actions(resumen_markdown(decision))
    if bloquear and not decision.aprobado:
        raise typer.Exit(1)


@gates_app.command("servicios")
def gates_servicios(
    sarif: Annotated[
        Path | None,
        typer.Option(
            "--sarif",
            help="Carpeta con una subcarpeta de SARIF por servicio (scripts/gate1-servicios.sh).",
        ),
    ] = None,
    bloquear: Annotated[
        bool,
        typer.Option(
            "--bloquear/--no-bloquear",
            help="Terminar con código 1 si se rechaza algún servicio.",
        ),
    ] = True,
    carpeta_salida: Annotated[
        Path | None,
        typer.Option(
            "--salida", help="Carpeta de resultados del pipeline; por defecto la configurada."
        ),
    ] = None,
) -> None:
    """Decisión OPA del Gate 1 sobre cada servicio generado, con la política del Gate 1."""
    from orchestrator.gates.decision import ErrorDecision
    from orchestrator.gates.fase4 import publicar_resumen_en_actions
    from orchestrator.gates.servicios import decidir_servicios, resumen_markdown

    salida = carpeta_salida or obtener_configuracion().directorio_salida
    carpeta = sarif or salida / "security" / "sarif" / "servicios"
    if not carpeta.is_dir() or not any(p.is_dir() for p in carpeta.iterdir()):
        typer.echo(
            f"Error: no hay SARIF de servicios en {carpeta.as_posix()}; "
            "ejecuta antes scripts/gate1-servicios.sh",
            err=True,
        )
        raise typer.Exit(1)
    try:
        decisiones = decidir_servicios(carpeta, salida)
    except ErrorDecision as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    for d in decisiones:
        estado = "APROBADO" if d.decision.aprobado else "RECHAZADO"
        typer.echo(f"Gate 1 de {d.servicio}: {estado}")
        typer.echo(f"  {d.decision.justificacion}")
        for criterio in d.decision.criterios:
            marca = "cumple   " if criterio.cumple else "NO cumple"
            typer.echo(f"  [{marca}] {criterio.regla}: {criterio.detalle}")
        for bloqueante in d.decision.bloqueantes:
            typer.echo(f"  Bloqueante {bloqueante.regla}: {bloqueante.motivo}")
        if d.decision.advertencias:
            typer.echo(f"  Advertencias (no bloquean): {len(d.decision.advertencias)}")
        typer.echo(f"  Decisión guardada en {d.destino.as_posix()}")
    resumen = resumen_markdown(decisiones)
    publicar_resumen_en_actions(resumen)
    rechazados = [d.servicio for d in decisiones if not d.decision.aprobado]
    typer.echo(
        f"{len(decisiones) - len(rechazados)} de {len(decisiones)} servicios aprobados"
        + (f"; rechazados: {', '.join(rechazados)}" if rechazados else "")
    )
    if rechazados and bloquear:
        raise typer.Exit(1)


@gates_app.command("listar")
def gates_listar(
    ejecucion: Annotated[
        str | None,
        typer.Option("--ejecucion", help="Ejecución a consultar; por defecto la más reciente."),
    ] = None,
) -> None:
    """Muestra las decisiones de los gates registradas en Neo4j para una ejecución."""
    from orchestrator.knowledge import ErrorGrafo, conectar, listar_resultados_gate
    from orchestrator.knowledge.registro import ultima_ejecucion

    config = obtener_configuracion()
    try:
        driver = conectar(config)
        try:
            db = config.neo4j_database
            ejecucion_id = ejecucion or _ejecucion_del_pipeline(config.directorio_salida)
            ejecucion_id = ejecucion_id or ultima_ejecucion(driver, db)
            if ejecucion_id is None:
                typer.echo("No hay ejecuciones registradas en Neo4j.")
                return
            resultados = listar_resultados_gate(driver, ejecucion_id, db)
        finally:
            driver.close()
    except ErrorGrafo as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(1) from error

    typer.echo(f"Ejecución: {ejecucion_id} ({len(resultados)} decisiones de gates)")
    for r in resultados:
        estado = "aprobado" if r["aprobado"] else "rechazado"
        cumplidos = sum(1 for c in r["criterios"] if c["cumple"])
        typer.echo(
            f"  Gate {r['gate']}: {estado} | criterios {cumplidos}/{len(r['criterios'])} "
            f"| bloqueantes {r['bloqueantes']} "
            f"| hallazgos que bloquean {r['hallazgos_bloqueantes']}"
        )
        typer.echo(f"    {r['justificacion']}")


requisitos_app = typer.Typer(
    help="Fase 1: documento de requisitos (extracción, clasificación y registro en Neo4j).",
    no_args_is_help=True,
)
app.add_typer(requisitos_app, name="requisitos")


def _base_del_archivo(ruta: Path) -> str:
    """Nombre seguro para los archivos de salida: solo letras, números, guiones y el formato."""
    import re

    raiz = re.sub(r"[^a-z0-9_-]+", "-", ruta.stem.lower()).strip("-") or "documento"
    return f"{raiz[:60]}-{ruta.suffix.lower().lstrip('.')}"


RutaDocumento = Annotated[
    Path | None, typer.Argument(help="Documento de requisitos local (PDF, DOCX, TXT o MD).")
]
IdDocumento = Annotated[
    str | None,
    typer.Option("--documento", help="Id de un documento cargado desde el dashboard o la API."),
]
CarpetaDestino = Annotated[
    Path | None,
    typer.Option("--destino", help="Carpeta de salida; por defecto salida/requisitos."),
]


def _extraer_documento(ruta: Path | None, documento: str | None):  # -> (DocumentoExtraido, str)
    """Extrae el documento indicado por ruta o por id; devuelve también el nombre de salida."""
    import re

    from orchestrator.documentos import DocumentoCargado, ErrorDocumento
    from orchestrator.ingest import extraer_markdown

    config = obtener_configuracion()
    if (ruta is None) == (documento is None):
        typer.echo("Indica una ruta o un --documento, solo uno de los dos.", err=True)
        raise typer.Exit(2)

    nombre = None
    if documento is not None:
        # El id lo genera el servidor (uuid4 en hexadecimal); cualquier otra cosa podría ser una
        # ruta, así que se rechaza antes de tocar el disco (CWE-22).
        if not re.fullmatch(r"[0-9a-f]{32}", documento):
            typer.echo("Id de documento no válido.", err=True)
            raise typer.Exit(2)
        carpeta = config.directorio_salida / "documentos"
        try:
            ficha = DocumentoCargado.model_validate_json(
                (carpeta / f"{documento}.json").read_bytes()
            )
        except (OSError, ValueError) as error:
            typer.echo(f"No existe el documento {documento}.", err=True)
            raise typer.Exit(1) from error
        ruta, nombre, base = carpeta / f"{documento}.{ficha.formato}", ficha.nombre, documento
    else:
        assert ruta is not None
        if not ruta.is_file():
            typer.echo(f"No existe el archivo {ruta}.", err=True)
            raise typer.Exit(1)
        base = _base_del_archivo(ruta)

    try:
        return extraer_markdown(ruta, nombre), base
    except ErrorDocumento as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error


def _carpeta_requisitos(destino: Path | None) -> Path:
    carpeta = destino or obtener_configuracion().directorio_salida / "requisitos"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


@requisitos_app.command("extraer")
def requisitos_extraer(
    ruta: RutaDocumento = None,
    documento: IdDocumento = None,
    destino: CarpetaDestino = None,
    vista_previa: Annotated[
        int, typer.Option("--vista-previa", min=0, help="Líneas del Markdown que se muestran.")
    ] = 12,
) -> None:
    """Extrae el documento de requisitos a Markdown con Docling y lo guarda con sus metadatos."""
    import json

    extraido, base = _extraer_documento(ruta, documento)
    carpeta_salida = _carpeta_requisitos(destino)
    markdown = carpeta_salida / f"{base}.md"
    markdown.write_text(extraido.markdown, encoding="utf-8")
    metadatos = extraido.model_dump(exclude={"markdown"}) | {"markdown": markdown.name}
    (carpeta_salida / f"{base}.json").write_text(
        json.dumps(metadatos, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    typer.echo(f"Documento: {extraido.nombre} ({extraido.formato})")
    typer.echo(f"  Herramienta: {extraido.herramienta}")
    typer.echo(f"  Texto extraído: {extraido.caracteres} caracteres, {extraido.lineas} líneas")
    typer.echo(f"  Duración: {extraido.duracion_s} s")
    typer.echo(f"  SHA-256 del original: {extraido.sha256}")
    typer.echo(f"  Markdown guardado en {markdown.as_posix()}")
    if vista_previa:
        typer.echo("--- Vista previa ---")
        for linea in extraido.markdown.splitlines()[:vista_previa]:
            typer.echo(linea)


@requisitos_app.command("normalizar")
def requisitos_normalizar(
    ruta: RutaDocumento = None,
    documento: IdDocumento = None,
    destino: CarpetaDestino = None,
    mostrar: Annotated[
        int, typer.Option("--mostrar", min=0, help="Unidades que se muestran en la terminal.")
    ] = 15,
) -> None:
    """Extrae, normaliza y divide el documento en unidades de requisito con su ubicación."""
    import json
    from collections import Counter

    from orchestrator.ingest import normalizar_texto, segmentar

    extraido, base = _extraer_documento(ruta, documento)
    invisibles = normalizar_texto(extraido.markdown).invisibles_eliminados
    unidades = segmentar(extraido.markdown)

    archivo = _carpeta_requisitos(destino) / f"{base}.unidades.json"
    contenido = {
        "documento": extraido.model_dump(include={"nombre", "formato", "sha256", "herramienta"}),
        "invisibles_eliminados": invisibles,
        "unidades": [u.model_dump() for u in unidades],
    }
    archivo.write_text(json.dumps(contenido, indent=2, ensure_ascii=False), encoding="utf-8")

    bloques = Counter(u.bloque for u in unidades)
    typer.echo(f"Documento: {extraido.nombre} ({extraido.formato}, {extraido.herramienta})")
    typer.echo(
        f"  Unidades: {len(unidades)} ("
        + ", ".join(f"{bloque}: {total}" for bloque, total in sorted(bloques.items()))
        + ")"
    )
    if invisibles:
        typer.echo(f"  Aviso: se eliminaron {invisibles} caracteres invisibles del documento")
    typer.echo(f"  Guardadas en {archivo.as_posix()}")
    for unidad in unidades[:mostrar]:
        texto = unidad.texto.replace("\n", " / ")
        typer.echo(f"  [{unidad.ubicacion:<14}] {unidad.bloque:<7} {texto[:90]}")
    if len(unidades) > mostrar:
        typer.echo(f"  ... y {len(unidades) - mostrar} más")


@requisitos_app.command("clasificar")
def requisitos_clasificar(
    ruta: RutaDocumento = None,
    documento: IdDocumento = None,
    destino: CarpetaDestino = None,
    proveedor: Annotated[
        str | None,
        typer.Option("--proveedor", help="Proveedor de LLM; por defecto LLM_PROVIDER."),
    ] = None,
) -> None:
    """Fase 1 completa: extrae, normaliza y clasifica con el LLM; guarda modelo_requisitos.json."""
    import time
    from collections import Counter

    from orchestrator.ingest import (
        DocumentoOrigen,
        ModeloRequisitos,
        construir_requisitos,
        segmentar,
    )
    from orchestrator.ingest.clasificacion import clasificar_unidades
    from orchestrator.llm import ErrorLLM, ProveedorEnCadena, crear_proveedor, describir_uso

    extraido, base = _extraer_documento(ruta, documento)
    unidades = segmentar(extraido.markdown)
    typer.echo(f"Documento: {extraido.nombre} ({extraido.formato}), {len(unidades)} unidades")

    def avance(titulo: str, total: int) -> None:
        typer.echo(f"  Clasificando «{titulo}» ({total} unidades)")

    def esperar(segundos: float) -> None:
        typer.echo(f"  Límite de uso del LLM: se reintenta en {segundos:.0f} s")
        time.sleep(segundos)

    try:
        llm = crear_proveedor(proveedor)
        if isinstance(llm, ProveedorEnCadena):
            llm.al_cambiar = lambda de, a, motivo: typer.echo(f"  {motivo}: la sección pasa a {a}")
        pares = clasificar_unidades(unidades, llm, al_avanzar=avance, dormir=esperar)
        modelo = ModeloRequisitos(
            documento=DocumentoOrigen(
                nombre=extraido.nombre, sha256=extraido.sha256, herramienta=extraido.herramienta
            ),
            requisitos=construir_requisitos(pares),
        )
    except (ErrorLLM, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    archivo = _carpeta_requisitos(destino) / f"{base}.modelo_requisitos.json"
    archivo.write_text(modelo.model_dump_json(indent=2), encoding="utf-8")

    tipos = Counter(r.tipo for r in modelo.requisitos)
    etiquetas = Counter(e for r in modelo.requisitos for e in r.etiquetas)
    descartadas = sum(1 for _, c in pares if not c.es_requisito)
    typer.echo(f"Proveedor: {getattr(llm, 'nombre', proveedor)}")
    typer.echo(f"Uso del LLM: {describir_uso(llm)}")
    typer.echo(
        f"Requisitos: {len(modelo.requisitos)} (funcionales: {tipos['funcional']}, "
        f"no funcionales: {tipos['no_funcional']}); unidades descartadas: {descartadas}"
    )
    typer.echo(
        "Etiquetas de seguridad: "
        + (", ".join(f"{e} {n}" for e, n in etiquetas.most_common()) or "ninguna")
    )
    typer.echo(f"Modelo guardado en {archivo.as_posix()}")


@requisitos_app.command("esquema")
def requisitos_esquema(
    salida: Annotated[
        Path | None, typer.Option("--salida", help="Archivo donde guardar el JSON Schema.")
    ] = None,
) -> None:
    """Muestra el JSON Schema de modelo_requisitos.json (esquema Pydantic Requisito)."""
    import json

    from orchestrator.ingest import ModeloRequisitos

    esquema = json.dumps(ModeloRequisitos.model_json_schema(), indent=2, ensure_ascii=False)
    if salida is None:
        typer.echo(esquema)
        return
    salida.write_text(esquema + "\n", encoding="utf-8")
    typer.echo(f"JSON Schema guardado en {salida.as_posix()}")


@requisitos_app.command("registrar")
def requisitos_registrar(
    modelo: Annotated[
        Path, typer.Argument(help="modelo_requisitos.json generado por «requisitos clasificar».")
    ],
    ejecucion: Annotated[
        str | None,
        typer.Option("--ejecucion", help="Ejecución existente; si se omite se crea una nueva."),
    ] = None,
) -> None:
    """Guarda los requisitos del modelo como nodos Requisito de una ejecución en Neo4j."""
    from collections import Counter

    from pydantic import ValidationError

    from orchestrator.ingest import ModeloRequisitos
    from orchestrator.knowledge import ErrorGrafo, conectar, crear_ejecucion, registrar_requisitos

    if not modelo.is_file():
        raise typer.BadParameter(f"no existe el archivo '{modelo}'", param_hint="MODELO")
    try:
        datos = ModeloRequisitos.model_validate_json(modelo.read_bytes())
    except ValidationError as error:
        typer.echo(f"Error: {modelo.name} no es un modelo de requisitos válido.\n{error}", err=True)
        raise typer.Exit(1) from error

    config = obtener_configuracion()
    try:
        driver = conectar(config)
        try:
            db = config.neo4j_database
            ejecucion_id = ejecucion or crear_ejecucion(
                driver, documento=datos.documento.nombre, base_datos=db
            )
            registrados = registrar_requisitos(driver, ejecucion_id, datos, base_datos=db)
        finally:
            driver.close()
    except ErrorGrafo as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    # Las fases siguientes del mismo pipeline (gates) se registran en esta ejecución.
    _guardar_ejecucion_del_pipeline(config.directorio_salida, ejecucion_id)

    tipos = Counter(r.tipo for r in datos.requisitos)
    typer.echo(f"Ejecución: {ejecucion_id}")
    typer.echo(f"Documento: {datos.documento.nombre}")
    typer.echo(
        f"Requisitos registrados: {registrados} (funcionales: {tipos['funcional']}, "
        f"no funcionales: {tipos['no_funcional']})"
    )


@requisitos_app.command("listar")
def requisitos_listar(
    ejecucion: Annotated[
        str | None,
        typer.Option(
            "--ejecucion", help="Ejecución a consultar; por defecto la última con requisitos."
        ),
    ] = None,
) -> None:
    """Muestra los requisitos registrados en Neo4j para una ejecución."""
    from orchestrator.knowledge import ErrorGrafo, conectar, listar_requisitos
    from orchestrator.knowledge.registro import ultima_ejecucion_con_requisitos

    config = obtener_configuracion()
    try:
        driver = conectar(config)
        try:
            db = config.neo4j_database
            ejecucion_id = ejecucion or ultima_ejecucion_con_requisitos(driver, db)
            filas = listar_requisitos(driver, ejecucion_id, db) if ejecucion_id else []
        finally:
            driver.close()
    except ErrorGrafo as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if ejecucion_id is None:
        typer.echo("No hay requisitos registrados en Neo4j.")
        return
    typer.echo(f"Ejecución: {ejecucion_id} ({len(filas)} requisitos)")
    for fila in filas:
        etiquetas = ", ".join(fila["etiquetas"] or []) or "sin etiquetas"
        typer.echo(
            f"  {fila['id']:<7} [{fila['ubicacion']}] {fila['servicio_sugerido']} | {etiquetas}"
        )
        typer.echo(f"          {fila['texto'][:100]}")


def _proveedor_principal(config) -> str:
    """LLM_PROVIDER validado. Si no es un proveedor conocido, se sale sin mostrar su valor: podría
    ser una clave pegada en la variable equivocada."""
    from orchestrator.llm import PROVEEDORES

    principal = config.llm_provider.strip().lower()
    if principal not in PROVEEDORES:
        typer.echo(
            f"Error: LLM_PROVIDER no es un proveedor conocido ({', '.join(PROVEEDORES)}).", err=True
        )
        raise typer.Exit(1)
    return principal


llm_app = typer.Typer(
    help="Proveedores de LLM: configuración, prueba de conexión y caché.", no_args_is_help=True
)
app.add_typer(llm_app, name="llm")


@llm_app.command("estado")
def llm_estado() -> None:
    """Muestra el proveedor principal, el respaldo, las claves definidas y la caché."""
    from orchestrator.llm import ErrorLLM
    from orchestrator.llm.cache import estadisticas
    from orchestrator.llm.fabrica import nombres_de_respaldo

    config = obtener_configuracion()
    principal = _proveedor_principal(config)
    try:
        respaldo = nombres_de_respaldo(config, principal)
    except ErrorLLM as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    claves = {
        "groq": config.groq_api_key,
        "gemini": config.gemini_api_key,
        "claude": config.anthropic_api_key,
    }
    typer.echo(f"Proveedor principal: {principal}")
    typer.echo(f"Respaldo: {', '.join(respaldo) or 'ninguno (LLM_RESPALDO vacío)'}")
    for nombre in [principal, *respaldo]:
        if nombre == "ollama":
            typer.echo(f"  {nombre}: servidor local en {config.ollama_host}")
        else:
            definida = claves.get(nombre) is not None
            typer.echo(f"  {nombre}: clave {'definida' if definida else 'NO definida'}")
    typer.echo(
        f"Esfuerzo de razonamiento (Groq): {config.llm_esfuerzo_razonamiento or 'el de Groq'}"
    )
    if config.llm_cache:
        respuestas, tamano = estadisticas(config.llm_cache_dir)
        typer.echo(
            f"Caché: activa en {config.llm_cache_dir.as_posix()} "
            f"({respuestas} respuestas, {tamano / 1024:.0f} KB)"
        )
    else:
        typer.echo("Caché: desactivada (LLM_CACHE=false)")


@llm_app.command("probar")
def llm_probar() -> None:
    """Envía una petición mínima a cada proveedor configurado, sin caché, y muestra si responde.

    Gasta unos cientos de tokens de cada uno.
    """
    from pydantic import BaseModel

    from orchestrator.llm import ErrorLimiteLLM, ErrorLLM, crear_adaptador, describir_uso
    from orchestrator.llm.fabrica import nombres_de_respaldo

    class Saludo(BaseModel):
        respuesta: str

    config = obtener_configuracion()
    principal = _proveedor_principal(config)
    fallos = 0
    try:
        respaldo = nombres_de_respaldo(config, principal)
    except ErrorLLM as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    for nombre in [principal, *respaldo]:
        try:
            proveedor = crear_adaptador(nombre, config, modelos_configurados=nombre == principal)
            proveedor.generar_estructurado(
                'Responde con el JSON {"respuesta": "ok"}.', Saludo, nivel="rapido"
            )
        except ErrorLimiteLLM as error:
            fallos += 1
            typer.echo(f"  {nombre}: sin cuota ahora mismo ({error})")
        except ErrorLLM as error:
            fallos += 1
            typer.echo(f"  {nombre}: no responde ({error})")
        else:
            typer.echo(f"  {nombre}: responde ({describir_uso(proveedor)})")
    if fallos:
        raise typer.Exit(1)


@llm_app.command("vaciar-cache")
def llm_vaciar_cache() -> None:
    """Borra las respuestas guardadas en la caché del LLM."""
    from orchestrator.llm.cache import vaciar

    carpeta = obtener_configuracion().llm_cache_dir
    typer.echo(f"Respuestas borradas de {carpeta.as_posix()}: {vaciar(carpeta)}")


arquitectura_app = typer.Typer(
    help="Fase 2: propuesta arquitectónica (servicios, contextos y decisiones).",
    no_args_is_help=True,
)
app.add_typer(arquitectura_app, name="arquitectura")


@arquitectura_app.command("proponer")
def arquitectura_proponer(
    modelo: Annotated[
        Path, typer.Argument(help="modelo_requisitos.json generado por «requisitos clasificar».")
    ],
    proveedor: Annotated[
        str | None,
        typer.Option("--proveedor", help="Proveedor de LLM; por defecto LLM_PROVIDER."),
    ] = None,
    nivel: Annotated[
        str,
        typer.Option("--nivel", help="Modelo del proveedor: razonamiento (por defecto) o rapido."),
    ] = "razonamiento",
    destino: Annotated[
        Path | None,
        typer.Option("--destino", help="Carpeta de salida; por defecto salida/arquitectura."),
    ] = None,
    intentos: Annotated[
        int,
        typer.Option("--intentos", min=1, max=5, help="Intentos del ciclo LLM ↔ OPA."),
    ] = 3,
    desde: Annotated[
        Path | None,
        typer.Option(
            "--desde",
            help="Empezar por esta arquitectura.json (p. ej. corregida a mano) en vez de pedirla.",
        ),
    ] = None,
    grafo: Annotated[
        bool | None,
        typer.Option(
            "--grafo/--sin-grafo",
            help="Registrar las decisiones en Neo4j. Por defecto, solo si NEO4J_PASSWORD existe.",
        ),
    ] = None,
    ejecucion: Annotated[
        str | None,
        typer.Option(
            "--ejecucion",
            help="Ejecución de Neo4j; por defecto la que tiene los requisitos de este documento.",
        ),
    ] = None,
) -> None:
    """Ciclo LLM ↔ OPA: el LLM propone y OPA valida; guarda arquitectura.json si OPA aprueba."""
    from functools import partial

    from pydantic import ValidationError

    from orchestrator.architecture import (
        Arquitectura,
        IntentoArquitectura,
        ciclo_llm_opa,
        proponer_arquitectura,
    )
    from orchestrator.ingest import ModeloRequisitos
    from orchestrator.llm import ErrorLLM, crear_proveedor
    from orchestrator.opa import ErrorOPA

    if nivel not in ("razonamiento", "rapido"):
        raise typer.BadParameter("usa «razonamiento» o «rapido»", param_hint="--nivel")
    if not modelo.is_file():
        raise typer.BadParameter(f"no existe el archivo '{modelo}'", param_hint="MODELO")
    try:
        datos = ModeloRequisitos.model_validate_json(modelo.read_bytes())
    except ValidationError as error:
        typer.echo(f"Error: {modelo.name} no es un modelo de requisitos válido.\n{error}", err=True)
        raise typer.Exit(1) from error
    inicial = None
    if desde is not None:
        try:
            inicial = Arquitectura.model_validate_json(desde.read_bytes())
        except (OSError, ValidationError) as error:
            typer.echo(f"Error: no se pudo leer la arquitectura de {desde}: {error}", err=True)
            raise typer.Exit(1) from error

    def reintento_del_motor(intento: int, problemas: list[str]) -> None:
        typer.echo(f"    La propuesta {intento} no pasó las comprobaciones del motor:")
        for problema in problemas:
            typer.echo(f"      - {problema}")

    def mostrar(intento: IntentoArquitectura) -> None:
        origen = "arquitectura inicial" if intento.origen == "inicial" else "propuesta del LLM"
        typer.echo(f"  Intento {intento.numero} ({origen}): {intento.decision.justificacion}")
        for bloqueante in intento.decision.bloqueantes:
            typer.echo(f"    OPA rechaza: {bloqueante.motivo}")
        for aviso in intento.decision.advertencias:
            typer.echo(f"    Aviso: {aviso.motivo}")
        if not intento.decision.aprobado and intento.numero < intentos:
            typer.echo("    Se vuelve a pedir al LLM con estos motivos.")

    typer.echo(f"Documento: {datos.documento.nombre}, {len(datos.requisitos)} requisitos")
    typer.echo(f"Ciclo LLM ↔ OPA (máximo {intentos} intentos):")
    try:
        llm = crear_proveedor(proveedor)
        resultado = ciclo_llm_opa(
            datos,
            llm,
            intentos=intentos,
            nivel=nivel,
            inicial=inicial,
            al_intento=mostrar,
            proponer=partial(proponer_arquitectura, al_reintentar=reintento_del_motor),
        )
    except (ErrorLLM, ErrorOPA, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    base = modelo.name.removesuffix(".json").removesuffix(".modelo_requisitos") or "documento"
    carpeta = destino or obtener_configuracion().directorio_salida / "arquitectura"
    carpeta.mkdir(parents=True, exist_ok=True)
    registro = carpeta / f"{base}.intentos.json"
    registro.write_text(resultado.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"Registro de intentos guardado en {registro.as_posix()}")

    final = resultado.final
    if resultado.aprobada:
        arquitectura = final.arquitectura
        archivo = carpeta / f"{base}.arquitectura.json"
        archivo.write_text(arquitectura.model_dump_json(indent=2), encoding="utf-8")
        typer.echo(f"Servicios: {len(arquitectura.servicios)}")
        for s in arquitectura.servicios:
            dependencias = ", ".join(f"{d.servicio} ({d.tipo})" for d in s.depende_de)
            typer.echo(
                f"  {s.nombre} [{s.contexto}]: {len(s.requisitos)} requisitos, "
                f"base {s.base_datos}, depende de {dependencias or 'ninguna'}"
            )
        typer.echo(f"Transversales: {len(arquitectura.transversales)} requisitos")
        typer.echo(f"Decisiones: {len(arquitectura.decisiones)}")
        for d in arquitectura.decisiones:
            typer.echo(f"  {d.id} {d.titulo}")
        typer.echo(f"Patrones inferidos por OPA: {len(final.decision.patrones)}")
        for p in final.decision.patrones:
            typer.echo(f"  {p.patron} ({p.id}): {p.motivo}")
        typer.echo(f"Arquitectura aprobada guardada en {archivo.as_posix()}")

    config = obtener_configuracion()
    usar_grafo = grafo if grafo is not None else config.neo4j_password is not None
    if usar_grafo:
        _registrar_decisiones_en_neo4j(config, resultado, datos, ejecucion)

    if not resultado.aprobada:
        typer.echo(
            f"OPA no aprobó ninguna propuesta en {len(resultado.intentos)} intentos: "
            "la arquitectura queda para revisión humana.",
            err=True,
        )
        raise typer.Exit(1)


def _registrar_decisiones_en_neo4j(config, resultado, modelo, ejecucion: str | None) -> None:
    """Guarda las decisiones del ciclo en la ejecución con los requisitos del documento.

    Si no hay ninguna, crea una y registra los requisitos, para que las decisiones queden
    enlazadas a ellos. Un fallo de Neo4j avisa pero no invalida la arquitectura.
    """
    from orchestrator.knowledge import ErrorGrafo, conectar, crear_ejecucion, registrar_requisitos
    from orchestrator.knowledge.registro import ejecucion_de_documento, registrar_decisiones

    db = config.neo4j_database
    try:
        driver = conectar(config)
        try:
            ejecucion_id = ejecucion or ejecucion_de_documento(driver, modelo.documento.sha256, db)
            if ejecucion_id is None:
                ejecucion_id = crear_ejecucion(
                    driver, documento=modelo.documento.nombre, base_datos=db
                )
                registrar_requisitos(driver, ejecucion_id, modelo, base_datos=db)
            registradas = registrar_decisiones(driver, ejecucion_id, resultado, base_datos=db)
        finally:
            driver.close()
    except ErrorGrafo as error:
        typer.echo(f"Sin registro en Neo4j: {error}", err=True)
        return
    typer.echo(f"Decisiones registradas en Neo4j: {registradas} (ejecución {ejecucion_id})")


@arquitectura_app.command("esquema")
def arquitectura_esquema(
    salida: Annotated[
        Path | None, typer.Option("--salida", help="Archivo donde guardar el JSON Schema.")
    ] = None,
) -> None:
    """Muestra el JSON Schema de arquitectura.json."""
    import json

    from orchestrator.architecture import Arquitectura

    esquema = json.dumps(Arquitectura.model_json_schema(), indent=2, ensure_ascii=False)
    if salida is None:
        typer.echo(esquema)
        return
    salida.write_text(esquema + "\n", encoding="utf-8")
    typer.echo(f"JSON Schema guardado en {salida.as_posix()}")


@arquitectura_app.command("adr")
def arquitectura_adr(
    arquitectura: Annotated[
        Path, typer.Argument(help="arquitectura.json generado por «arquitectura proponer».")
    ],
    requisitos: Annotated[
        Path,
        typer.Option("--requisitos", help="modelo_requisitos.json del que salió la arquitectura."),
    ],
    destino: Annotated[
        Path, typer.Option("--destino", help="Carpeta de los ADR; por defecto docs/adr.")
    ] = Path("docs/adr"),
    proveedor: Annotated[
        str | None,
        typer.Option("--proveedor", help="Proveedor de LLM que redacta; por defecto LLM_PROVIDER."),
    ] = None,
    sin_llm: Annotated[
        bool, typer.Option("--sin-llm", help="Redacta con la plantilla del motor, sin LLM.")
    ] = False,
) -> None:
    """Genera los ADR en Markdown: uno por decisión y otro por patrón que infiere OPA.

    Antes valida la arquitectura con OPA y solo genera los ADR si la aprueba.
    """
    from pydantic import ValidationError

    from orchestrator.architecture import Arquitectura, validar_arquitectura
    from orchestrator.architecture.adr import ErrorADR, construir_adrs, escribir_adrs, redactar
    from orchestrator.ingest import ModeloRequisitos
    from orchestrator.llm import ErrorLLM, crear_proveedor, describir_uso
    from orchestrator.opa import ErrorOPA

    try:
        datos = Arquitectura.model_validate_json(arquitectura.read_bytes())
        modelo = ModeloRequisitos.model_validate_json(requisitos.read_bytes())
    except OSError as error:
        typer.echo(f"Error: no se pudo leer {error.filename}", err=True)
        raise typer.Exit(1) from error
    except ValidationError as error:
        typer.echo(f"Error: un archivo no tiene el formato esperado.\n{error}", err=True)
        raise typer.Exit(1) from error
    if modelo.documento.sha256 != datos.documento.sha256:
        typer.echo(
            "Error: la arquitectura y el modelo de requisitos son de documentos distintos.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        decision = validar_arquitectura(datos)
    except ErrorOPA as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"OPA: {decision.justificacion}")
    if not decision.aprobado:
        for bloqueante in decision.bloqueantes:
            typer.echo(f"  - {bloqueante.regla}: {bloqueante.motivo}", err=True)
        typer.echo(
            "No se generan ADR de una arquitectura rechazada: corrígela con «arquitectura "
            "proponer» y vuelve a intentarlo.",
            err=True,
        )
        raise typer.Exit(1)

    llm = None
    if not sin_llm:
        try:
            llm = crear_proveedor(proveedor)
        except ErrorLLM as error:
            typer.echo(f"Sin LLM ({error}); se redacta con la plantilla del motor.")

    def al_redactar(adr, por: str) -> None:
        typer.echo(f"  ADR-{adr.numero:04d} {adr.titulo}: {por}")

    try:
        adrs = construir_adrs(datos, decision, modelo)
        redactar(adrs, llm, al_redactar=al_redactar)
        escritos = escribir_adrs(adrs, datos, decision, destino)
    except ErrorADR as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    if llm is not None:
        typer.echo(f"Uso del LLM: {describir_uso(llm)}")
    typer.echo(f"{len(adrs)} ADR y el índice README.md escritos en {destino.as_posix()}")
    for archivo in escritos:
        typer.echo(f"  {archivo.name}")


@arquitectura_app.command("diagrama")
def arquitectura_diagrama(
    arquitectura: Annotated[
        Path, typer.Argument(help="arquitectura.json generado por «arquitectura proponer».")
    ],
    requisitos: Annotated[
        Path,
        typer.Option("--requisitos", help="modelo_requisitos.json del que salió la arquitectura."),
    ],
    salida: Annotated[
        Path,
        typer.Option("--salida", help="Documento a escribir; por defecto docs/arquitectura.md."),
    ] = Path("docs/arquitectura.md"),
    adr: Annotated[
        Path,
        typer.Option("--adr", help="Carpeta de los ADR, para enlazar cada patrón con el suyo."),
    ] = Path("docs/adr"),
    nombre: Annotated[
        str | None,
        typer.Option("--nombre", help="Nombre del sistema; por defecto, el del documento."),
    ] = None,
) -> None:
    """Escribe la arquitectura con su diagrama C4 en Mermaid (contexto y contenedores).

    Antes valida la arquitectura con OPA y solo la dibuja si la aprueba. No usa LLM.
    """
    from datetime import date

    from pydantic import ValidationError

    from orchestrator.architecture import Arquitectura, validar_arquitectura
    from orchestrator.architecture.adr import construir_adrs
    from orchestrator.architecture.c4 import (
        ErrorDiagrama,
        actores,
        documento_arquitectura,
        enlaces_adr,
        escribir_documento,
    )
    from orchestrator.ingest import ModeloRequisitos
    from orchestrator.opa import ErrorOPA

    try:
        datos = Arquitectura.model_validate_json(arquitectura.read_bytes())
        modelo = ModeloRequisitos.model_validate_json(requisitos.read_bytes())
    except OSError as error:
        typer.echo(f"Error: no se pudo leer {error.filename}", err=True)
        raise typer.Exit(1) from error
    except ValidationError as error:
        typer.echo(f"Error: un archivo no tiene el formato esperado.\n{error}", err=True)
        raise typer.Exit(1) from error
    if modelo.documento.sha256 != datos.documento.sha256:
        typer.echo(
            "Error: la arquitectura y el modelo de requisitos son de documentos distintos.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        decision = validar_arquitectura(datos)
    except ErrorOPA as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"OPA: {decision.justificacion}")

    try:
        enlaces = (
            enlaces_adr(construir_adrs(datos, decision, modelo), adr, salida)
            if decision.aprobado
            else {}
        )
        contenido = documento_arquitectura(
            datos, modelo, decision, date.today(), enlaces, nombre=nombre
        )
        escribir_documento(contenido, salida)
    except ErrorDiagrama as error:
        for bloqueante in decision.bloqueantes:
            typer.echo(f"  - {bloqueante.regla}: {bloqueante.motivo}", err=True)
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    lista = ", ".join(f"{actor} ({n})" for actor, n in actores(modelo))
    typer.echo(f"Actores: {lista or 'ninguno'}")
    typer.echo(
        f"Contenedores: {len(datos.servicios)} servicios con su base de datos; "
        f"patrones: {', '.join(p.patron for p in decision.patrones) or 'ninguno'}"
    )
    typer.echo(f"ADR enlazados: {len(enlaces)} de {len(decision.patrones)} patrones")
    typer.echo(f"Documento escrito en {salida.as_posix()}")


servicio_app = typer.Typer(
    help="Fase 3: generación de cada microservicio NestJS con la plantilla Copier.",
    no_args_is_help=True,
)
app.add_typer(servicio_app, name="servicio")


@servicio_app.command("generar")
def servicio_generar(
    especificacion: Annotated[
        Path,
        typer.Argument(help="YAML o JSON con el servicio y sus entidades (ver la plantilla)."),
    ],
    destino: Annotated[
        Path | None,
        typer.Option(
            "--destino", help="Carpeta donde crear el servicio; por defecto salida/servicios."
        ),
    ] = None,
) -> None:
    """Genera un servicio con templates/microservicio_nestjs y valida su estructura."""
    from orchestrator.generation import (
        ErrorPlantilla,
        arbol,
        generar_servicio,
        leer_especificacion,
        validar_estructura,
    )

    if not especificacion.is_file():
        raise typer.BadParameter(
            f"no existe el archivo '{especificacion}'", param_hint="ESPECIFICACION"
        )
    carpeta = destino or obtener_configuracion().directorio_salida / "servicios"
    try:
        datos = leer_especificacion(especificacion)
        generado = generar_servicio(datos, carpeta)
    except ErrorPlantilla as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    resultado = validar_estructura(generado, datos)
    typer.echo(f"Servicio {datos['servicio']} generado en {generado.as_posix()}")
    typer.echo(arbol(resultado.archivos, generado.name))
    typer.echo(f"Estructura validada; rutas: {', '.join(resultado.rutas)}")
    typer.echo(
        "Para compilarlo y probarlo: npm ci, npm run prisma:generate, npm run typecheck y "
        "npm test (ver el README.md del servicio)."
    )


@servicio_app.command("sistema")
def servicio_sistema(
    arquitectura: Annotated[
        Path, typer.Argument(help="arquitectura.json aprobada por «arquitectura proponer».")
    ],
    requisitos: Annotated[
        Path, typer.Option("--requisitos", help="modelo_requisitos.json del que salió.")
    ],
    destino: Annotated[
        Path | None,
        typer.Option(
            "--destino",
            help="Carpeta nueva para los servicios; por defecto salida/servicios/<nombre>-<fecha>.",
        ),
    ] = None,
    compilar_servicios: Annotated[
        bool,
        typer.Option(
            "--compilar/--sin-compilar",
            help="Instalar las dependencias, compilar con tsc y ejecutar las pruebas con Jest.",
        ),
    ] = True,
    con_logica: Annotated[
        bool, typer.Option("--logica/--sin-logica", help="Pedir al LLM la lógica de negocio.")
    ] = True,
    con_pruebas: Annotated[
        bool, typer.Option("--pruebas/--sin-pruebas", help="Pedir al LLM las pruebas Jest.")
    ] = True,
    graphrag: Annotated[
        bool,
        typer.Option("--graphrag/--sin-graphrag", help="Contexto de seguridad desde Neo4j."),
    ] = True,
    proveedor: Annotated[
        str | None,
        typer.Option("--proveedor", help="Proveedor de LLM; por defecto LLM_PROVIDER."),
    ] = None,
) -> None:
    """Fase 3 completa: un microservicio por cada servicio de la arquitectura."""
    from datetime import UTC, datetime

    from pydantic import ValidationError

    from orchestrator.architecture import Arquitectura
    from orchestrator.ejecuciones import contexto_graphrag_en_neo4j
    from orchestrator.generation.sistema import (
        CARPETA_DEPENDENCIAS,
        ErrorSistema,
        generar_sistema,
    )
    from orchestrator.ingest import ModeloRequisitos
    from orchestrator.llm import ErrorLLM, crear_proveedor

    try:
        arq = Arquitectura.model_validate_json(arquitectura.read_bytes())
        modelo = ModeloRequisitos.model_validate_json(requisitos.read_bytes())
    except (OSError, ValidationError) as error:
        typer.echo(
            f"Error: no se pudieron leer la arquitectura o los requisitos: {error}", err=True
        )
        raise typer.Exit(1) from error
    servicios = obtener_configuracion().directorio_salida / "servicios"
    nombre = arquitectura.name.removesuffix(".arquitectura.json")
    fecha = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    carpeta = destino or servicios / f"{nombre}-{fecha}"

    contexto_de, cerrar = None, None
    if graphrag:
        try:
            contexto_de, cerrar = contexto_graphrag_en_neo4j()
        except Exception as error:  # Neo4j o los embeddings no están disponibles
            typer.echo(f"Sin contexto GraphRAG: {error}", err=True)
    try:
        llm = crear_proveedor(proveedor)
        resultado = generar_sistema(
            arq,
            modelo,
            carpeta,
            llm,
            documento=modelo.documento.nombre,
            contexto_de=contexto_de,
            compilar_servicios=compilar_servicios,
            con_logica=con_logica,
            con_pruebas=con_pruebas,
            dependencias=servicios / CARPETA_DEPENDENCIAS,
            avance=lambda mensaje, progreso=None: typer.echo(f"  {mensaje}"),
        )
    except (ErrorSistema, ErrorLLM) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    finally:
        if cerrar is not None:
            cerrar()

    typer.echo(f"\nServicios en {carpeta.as_posix()}")
    for s in resultado.servicios:
        estado = "completo" if s.completo else f"incompleto: {s.error or 'revisa el resumen'}"
        logica = ", ".join(f"{e.nombre}={e.logica}" for e in s.entidades)
        typer.echo(f"  {s.servicio:<16} puerto {s.puerto}  {estado}  [{logica}]")
    typer.echo(
        f"{resultado.completos} de {len(resultado.servicios)} servicios completos; "
        f"resumen en {carpeta.as_posix()}/sistema.json"
    )
    if resultado.completos < len(resultado.servicios):
        raise typer.Exit(1)


@servicio_app.command("parametros")
def servicio_parametros(
    arquitectura: Annotated[
        Path, typer.Argument(help="arquitectura.json aprobada por «arquitectura proponer».")
    ],
    salida: Annotated[
        Path | None,
        typer.Option("--salida", help="Guardar los parámetros de todos los servicios en JSON."),
    ] = None,
) -> None:
    """Parámetros de la plantilla de cada servicio de la arquitectura: nombre, entidades y rutas."""
    import json

    from pydantic import ValidationError

    from orchestrator.architecture import Arquitectura
    from orchestrator.generation import ErrorParametros, parametros_de_arquitectura

    try:
        arq = Arquitectura.model_validate_json(arquitectura.read_bytes())
    except (OSError, ValidationError) as error:
        typer.echo(f"Error: no se pudo leer la arquitectura: {error}", err=True)
        raise typer.Exit(1) from error
    try:
        parametros = parametros_de_arquitectura(arq)
    except ErrorParametros as error:
        typer.echo("Error: la arquitectura no se puede parametrizar:", err=True)
        for problema in error.problemas:
            typer.echo(f"  - {problema}", err=True)
        raise typer.Exit(1) from error

    typer.echo(f"{len(parametros.servicios)} servicios en {arquitectura.name}")
    for servicio in parametros.servicios:
        typer.echo(
            f"\n{servicio.servicio}  (puerto {servicio.puerto}, base {servicio.base_datos}, "
            f"audiencia {servicio.audiencia})"
        )
        typer.echo(f"  {servicio.descripcion}")
        typer.echo(f"  Requisitos: {', '.join(servicio.requisitos)}")
        if not servicio.entidades:
            typer.echo("  Sin entidades en la arquitectura: las propondrá el LLM")
        for entidad in servicio.entidades:
            typer.echo(f"  {entidad.original:<28} {entidad.nombre:<28} {entidad.ruta}")
    for advertencia in parametros.advertencias:
        typer.echo(f"\nAdvertencia: {advertencia}")
    if salida:
        salida.parent.mkdir(parents=True, exist_ok=True)
        salida.write_text(
            json.dumps(parametros.model_dump(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        typer.echo(f"\nParámetros guardados en {salida.as_posix()}")


@servicio_app.command("validar")
def servicio_validar(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta de un servicio generado.")],
    mostrar_arbol: Annotated[
        bool, typer.Option("--arbol/--sin-arbol", help="Mostrar el árbol de archivos.")
    ] = True,
) -> None:
    """Valida la estructura de un servicio generado contra su .copier-answers.yml."""
    from orchestrator.generation import arbol, validar_estructura

    if not carpeta.is_dir():
        raise typer.BadParameter(f"no existe la carpeta '{carpeta}'", param_hint="CARPETA")
    resultado = validar_estructura(carpeta)
    if mostrar_arbol and resultado.archivos:
        typer.echo(arbol(resultado.archivos, carpeta.resolve().name))
    if resultado.rutas:
        typer.echo(f"Rutas: {', '.join(resultado.rutas)}")
    if not resultado.valida:
        typer.echo(f"Estructura inválida ({len(resultado.problemas)} problemas):", err=True)
        for problema in resultado.problemas:
            typer.echo(f"  - {problema}", err=True)
        raise typer.Exit(1)
    typer.echo("Estructura válida: coincide con la especificación del servicio.")


@servicio_app.command("dependencias")
def servicio_dependencias(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta del servicio (con su package.json).")],
    lista: Annotated[
        Path | None,
        typer.Option("--lista", help="Lista permitida; por defecto la de knowledge_base/."),
    ] = None,
) -> None:
    """Comprueba las dependencias npm del servicio contra la lista permitida (slopsquatting)."""
    from orchestrator.generation.dependencias import (
        RUTA_LISTA,
        ErrorDependencias,
        cargar_lista,
        verificar_servicio,
    )

    try:
        problemas = verificar_servicio(carpeta, cargar_lista(lista or RUTA_LISTA))
    except ErrorDependencias as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(2) from error
    revisados = (
        "package.json y package-lock.json"
        if (carpeta / "package-lock.json").is_file()
        else ("package.json")
    )
    if problemas:
        typer.echo(f"{len(problemas)} problemas con la lista de dependencias permitidas:")
        for problema in problemas:
            typer.echo(f"  - {problema}")
        raise typer.Exit(1)
    typer.echo(f"{revisados}: todas las dependencias están en la lista permitida")


@servicio_app.command("demo")
def servicio_demo(
    arquitectura: Annotated[
        Path | None,
        typer.Option(
            "--arquitectura",
            help="arquitectura.json aprobada; por defecto la del documento 1 del repositorio.",
        ),
    ] = None,
    destino: Annotated[
        Path | None,
        typer.Option(
            "--destino", help="Carpeta de la demostración; por defecto salida/servicios-demo."
        ),
    ] = None,
    compilar: Annotated[
        bool,
        typer.Option(
            "--compilar", help="Además instala las dependencias y compila con tsc (minutos)."
        ),
    ] = False,
    mostrar_arbol: Annotated[
        bool, typer.Option("--arbol", help="Mostrar el árbol de archivos del servicio generado.")
    ] = False,
) -> None:
    """Muestra de una vez lo que la fase 3 ya hace, sin LLM: parámetros, plantilla y controles."""
    from orchestrator.generation.demostracion import (
        ARQUITECTURA_POR_DEFECTO,
        PENDIENTE,
        ErrorDemostracion,
        Paso,
        demostrar,
    )

    origen = arquitectura or ARQUITECTURA_POR_DEFECTO
    carpeta = destino or obtener_configuracion().directorio_salida / "servicios-demo"
    try:
        mostrada = origen.resolve().relative_to(Path.cwd().resolve())
    except ValueError:
        mostrada = origen

    def empezar(numero: int, total: int, titulo: str) -> None:
        typer.echo(f"\n[{numero}/{total}] {titulo}")

    def terminar(paso: Paso) -> None:
        for linea in paso.lineas:
            typer.echo(f"      {linea}")
        typer.echo(f"      -> {'OK' if paso.ok else 'FALLA'}")

    typer.echo("Fase 3: lo que el motor ya hace al generar un servicio (sin LLM)")
    try:
        pasos = demostrar(origen, carpeta, compilar, mostrar_arbol, empezar, terminar)
    except ErrorDemostracion as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    correctos = sum(1 for p in pasos if p.ok)
    typer.echo(f"\nResultado: {correctos} de {len(pasos)} pasos correctos")
    typer.echo("\nCon el LLM (gasta cuota; no se ejecuta aquí):")
    typer.echo(
        f"  framework servicio prompt {mostrada.as_posix()} --requisitos <modelo_requisitos.json> "
        "--servicio <servicio> --enviar --salida <servicio>.yml"
    )
    typer.echo("  framework servicio generar <servicio>.yml")
    typer.echo(
        "  framework servicio logica <carpeta del servicio> "
        f"--arquitectura {mostrada.as_posix()} --requisitos <modelo_requisitos.json>"
    )
    typer.echo("\nTodavía no está en el motor:")
    for linea in PENDIENTE:
        typer.echo(f"  - {linea}")
    if correctos != len(pasos) or len(pasos) < (7 if compilar else 6):
        raise typer.Exit(1)


@servicio_app.command("logica")
def servicio_logica(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta del servicio generado.")],
    arquitectura: Annotated[
        Path, typer.Option("--arquitectura", help="arquitectura.json aprobada.")
    ],
    requisitos: Annotated[
        Path, typer.Option("--requisitos", help="modelo_requisitos.json del que salió.")
    ],
    entidad: Annotated[
        list[str] | None,
        typer.Option("--entidad", help="Entidad a completar; por defecto todas."),
    ] = None,
    intentos: Annotated[
        int, typer.Option("--intentos", min=1, max=5, help="Intentos por entidad.")
    ] = 3,
    graphrag: Annotated[
        bool, typer.Option("--graphrag/--sin-graphrag", help="Recuperar el contexto de Neo4j.")
    ] = True,
    compilar: Annotated[
        bool, typer.Option("--compilar/--sin-compilar", help="Verificar con tsc --noEmit.")
    ] = True,
    proveedor: Annotated[
        str | None,
        typer.Option("--proveedor", help="Proveedor de LLM; por defecto LLM_PROVIDER."),
    ] = None,
) -> None:
    """Rellena con el LLM la lógica de negocio de las entidades y la verifica con tsc."""
    from pydantic import ValidationError

    from orchestrator.architecture import Arquitectura
    from orchestrator.generation import ErrorLogica, IntentoLogica, generar_logica, preparar
    from orchestrator.generation.logica import compilar as compilar_con_tsc
    from orchestrator.ingest import ModeloRequisitos
    from orchestrator.knowledge import ErrorGrafo
    from orchestrator.knowledge.embeddings import ErrorEmbeddings
    from orchestrator.llm import ErrorLLM, crear_proveedor
    from orchestrator.llm.prompts import (
        EspecificacionServicio,
        contexto_de_seguridad,
        contexto_vacio,
    )

    try:
        respuestas = yaml_seguro(carpeta / ".copier-answers.yml")
        spec = EspecificacionServicio.model_validate(
            {
                k: respuestas[k]
                for k in ("servicio", "descripcion", "base_datos", "puerto", "entidades")
            }
        )
        arq = Arquitectura.model_validate_json(arquitectura.read_bytes())
        modelo = ModeloRequisitos.model_validate_json(requisitos.read_bytes())
    except (OSError, KeyError, ValidationError, ValueError) as error:
        typer.echo(
            f"Error: no se pudo leer el servicio, la arquitectura o los requisitos: {error}",
            err=True,
        )
        raise typer.Exit(1) from error
    datos = next((s for s in arq.servicios if s.nombre == spec.servicio), None)
    if datos is None:
        typer.echo(f"Error: {spec.servicio} no está en {arquitectura.name}", err=True)
        raise typer.Exit(1)
    del_servicio = [r for r in modelo.requisitos if r.id in set(datos.requisitos)]
    entidades = entidad or [e.nombre for e in spec.entidades]

    contexto = contexto_vacio()
    if graphrag:
        try:
            consultor, cerrar = _consultor_graphrag(obtener_configuracion(), 3)
            try:
                contexto = contexto_de_seguridad(datos.etiquetas, consultor)
            finally:
                cerrar()
        except (ErrorGrafo, ErrorEmbeddings) as error:
            typer.echo(f"Sin contexto GraphRAG: {error}", err=True)

    typer.echo(
        f"Servicio {spec.servicio}: {len(entidades)} entidades, {len(del_servicio)} requisitos, "
        f"contexto con {len(contexto.controles)} controles ASVS"
    )
    try:
        if compilar:
            typer.echo(
                "Preparando la compilación (npm install --ignore-scripts y prisma generate)…"
            )
            preparar(carpeta)
        llm = crear_proveedor(proveedor)
    except (ErrorLogica, ErrorLLM) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    def mostrar(intento: IntentoLogica) -> None:
        if not intento.problemas and not intento.errores_tsc:
            typer.echo(f"    Intento {intento.numero}: aceptado")
            return
        typer.echo(f"    Intento {intento.numero}: rechazado")
        for motivo in intento.problemas + [f"tsc {e}" for e in intento.errores_tsc][:8]:
            typer.echo(f"      - {motivo}")

    registro = carpeta / "logica"
    registro.mkdir(exist_ok=True)
    rechazadas = []
    for nombre in entidades:
        typer.echo(f"  {nombre}:")
        try:
            resultado = generar_logica(
                carpeta,
                spec,
                nombre,
                del_servicio,
                contexto,
                llm,
                intentos=intentos,
                compilador=compilar_con_tsc if compilar else None,
                al_intento=mostrar,
            )
        except (ErrorLogica, ErrorLLM) as error:
            typer.echo(f"    Error: {error}", err=True)
            rechazadas.append(nombre)
            continue
        (registro / f"{nombre}.json").write_text(
            resultado.model_dump_json(indent=2), encoding="utf-8"
        )
        if resultado.aprobada and resultado.logica:
            implementados = ", ".join(resultado.logica.requisitos) or "-"
            typer.echo(
                f"    {resultado.archivo}: requisitos {implementados}; "
                f"pendientes {len(resultado.logica.pendientes)}"
            )
        else:
            rechazadas.append(nombre)
            typer.echo(f"    Sin lógica: {resultado.archivo} queda como lo generó la plantilla")

    typer.echo(f"Registro de cada entidad en {registro.as_posix()}/")
    if rechazadas:
        typer.echo(f"Entidades sin lógica aceptada: {', '.join(rechazadas)}", err=True)
        raise typer.Exit(1)


@servicio_app.command("pruebas")
def servicio_pruebas(
    carpeta: Annotated[Path, typer.Argument(help="Carpeta del servicio con la lógica generada.")],
    requisitos: Annotated[
        Path, typer.Option("--requisitos", help="modelo_requisitos.json del que salió.")
    ],
    entidad: Annotated[
        list[str] | None,
        typer.Option("--entidad", help="Entidad a probar; por defecto las que tienen lógica."),
    ] = None,
    intentos: Annotated[
        int, typer.Option("--intentos", min=1, max=5, help="Intentos por entidad.")
    ] = 3,
    cobertura: Annotated[
        bool,
        typer.Option("--cobertura", help="Al final, ejecutar todas las pruebas con cobertura."),
    ] = False,
    proveedor: Annotated[
        str | None,
        typer.Option("--proveedor", help="Proveedor de LLM; por defecto LLM_PROVIDER."),
    ] = None,
) -> None:
    """Genera con el LLM las pruebas Jest de la lógica de negocio y las ejecuta."""
    from pydantic import ValidationError

    from orchestrator.generation import (
        ErrorLogica,
        IntentoPruebas,
        ResultadoLogica,
        generar_pruebas,
        preparar,
    )
    from orchestrator.ingest import ModeloRequisitos
    from orchestrator.llm import ErrorLLM, crear_proveedor
    from orchestrator.llm.prompts import EspecificacionServicio

    try:
        respuestas = yaml_seguro(carpeta / ".copier-answers.yml")
        spec = EspecificacionServicio.model_validate(
            {
                k: respuestas[k]
                for k in ("servicio", "descripcion", "base_datos", "puerto", "entidades")
            }
        )
        modelo = ModeloRequisitos.model_validate_json(requisitos.read_bytes())
    except (OSError, KeyError, ValidationError, ValueError) as error:
        typer.echo(f"Error: no se pudo leer el servicio o los requisitos: {error}", err=True)
        raise typer.Exit(1) from error

    logicas: dict[str, ResultadoLogica] = {}
    for archivo in sorted((carpeta / "logica").glob("*.json")):
        resultado = ResultadoLogica.model_validate_json(archivo.read_bytes())
        reglas = resultado.logica
        if (
            resultado.aprobada
            and reglas
            and any(
                getattr(reglas, m).strip()
                for m in ("reglas_al_crear", "reglas_al_actualizar", "reglas_al_eliminar")
            )
        ):
            logicas[resultado.entidad] = resultado
    entidades = entidad or sorted(logicas)
    if sin_logica := [e for e in entidades if e not in logicas]:
        typer.echo(
            "Sin reglas de negocio aceptadas (ejecuta antes «servicio logica»): "
            + ", ".join(sin_logica),
            err=True,
        )
        raise typer.Exit(1)
    if not entidades:
        typer.echo("Ninguna entidad tiene reglas de negocio que probar.")
        return

    try:
        typer.echo("Preparando el servicio (dependencias permitidas, npm y Prisma)…")
        preparar(carpeta)
        llm = crear_proveedor(proveedor)
    except (ErrorLogica, ErrorLLM) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    def mostrar(intento: IntentoPruebas) -> None:
        pasan = sum(1 for c in intento.casos if c.estado == "passed")
        if intento.problemas:
            typer.echo(f"    Intento {intento.numero}: rechazado por el análisis del código")
            for problema in intento.problemas[:6]:
                typer.echo(f"      - {problema}")
        elif intento.error_de_compilacion:
            primera = intento.error_de_compilacion.splitlines()[0][:160]
            typer.echo(f"    Intento {intento.numero}: el archivo no compila ({primera})")
        else:
            typer.echo(f"    Intento {intento.numero}: {pasan}/{len(intento.casos)} casos pasan")

    registro = carpeta / "pruebas"
    registro.mkdir(exist_ok=True)
    sin_pruebas = []
    for nombre in entidades:
        logica = logicas[nombre].logica
        ids = set(logica.requisitos)
        del_codigo = [r for r in modelo.requisitos if r.id in ids]
        typer.echo(f"  {nombre} ({len(del_codigo)} requisitos):")
        try:
            resultado = generar_pruebas(
                carpeta,
                spec,
                nombre,
                logica,
                del_codigo,
                llm,
                intentos=intentos,
                al_intento=mostrar,
            )
        except (ErrorLogica, ErrorLLM) as error:
            typer.echo(f"    Error: {error}", err=True)
            sin_pruebas.append(nombre)
            continue
        (registro / f"{nombre}.json").write_text(
            resultado.model_dump_json(indent=2), encoding="utf-8"
        )
        if resultado.aceptadas:
            descartadas = (
                f", {len(resultado.descartadas)} descartadas" if resultado.descartadas else ""
            )
            typer.echo(f"    {resultado.archivo}: {resultado.aceptadas} pruebas{descartadas}")
        else:
            sin_pruebas.append(nombre)
            typer.echo("    Ninguna prueba pasó: no se deja archivo")

    typer.echo(f"Registro de cada entidad en {registro.as_posix()}/")
    if cobertura:
        typer.echo("Ejecutando todas las pruebas del servicio con cobertura (npx jest --coverage)…")
        from orchestrator.generation.logica import _ejecutar

        proceso = _ejecutar(["npx", "jest", "--ci", "--coverage"], carpeta, 900)
        salida = (proceso.stdout + proceso.stderr).strip().splitlines()
        for linea in salida[-45:]:
            typer.echo(f"  {linea}")
    if sin_pruebas:
        typer.echo(f"Entidades sin pruebas aceptadas: {', '.join(sin_pruebas)}", err=True)
        raise typer.Exit(1)


def yaml_seguro(ruta: Path) -> dict:
    """Lee un YAML con safe_load y exige que sea un objeto."""
    import yaml

    datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    if not isinstance(datos, dict):
        raise ValueError(f"{ruta.name} no es un objeto")
    return datos


def _consultor_graphrag(config, k: int):
    """Función pregunta -> ContextoGraphRAG sobre Neo4j y los embeddings locales, y su cierre."""
    from orchestrator.knowledge import conectar
    from orchestrator.knowledge.embeddings import EmbeddingsLocales
    from orchestrator.knowledge.graphrag import consultar

    proveedor = EmbeddingsLocales(config.embeddings_modelo, config.embeddings_cache)
    driver = conectar(config)

    def consultor(pregunta: str):
        return consultar(driver, proveedor, pregunta, k=k, base_datos=config.neo4j_database)

    return consultor, driver.close


@servicio_app.command("prompt")
def servicio_prompt(
    arquitectura: Annotated[
        Path, typer.Argument(help="arquitectura.json aprobada por «arquitectura proponer».")
    ],
    requisitos: Annotated[
        Path, typer.Option("--requisitos", help="modelo_requisitos.json del que salió.")
    ],
    servicio: Annotated[str, typer.Option("--servicio", help="Servicio de la arquitectura.")],
    tarea: Annotated[
        str,
        typer.Option("--tarea", help="especificacion (entidades) o logica (reglas de negocio)."),
    ] = "especificacion",
    especificacion: Annotated[
        Path | None,
        typer.Option("--especificacion", help="Tarea logica: especificación YAML del servicio."),
    ] = None,
    entidad: Annotated[
        str | None, typer.Option("--entidad", help="Tarea logica: entidad de la especificación.")
    ] = None,
    graphrag: Annotated[
        bool,
        typer.Option("--graphrag/--sin-graphrag", help="Recuperar el contexto de Neo4j."),
    ] = True,
    k: Annotated[int, typer.Option("--k", min=1, max=10, help="Fragmentos por pregunta.")] = 3,
    enviar: Annotated[
        bool, typer.Option("--enviar", help="Enviar el prompt al LLM y validar la respuesta.")
    ] = False,
    proveedor: Annotated[
        str | None,
        typer.Option("--proveedor", help="Proveedor de LLM; por defecto LLM_PROVIDER."),
    ] = None,
    salida: Annotated[
        Path | None,
        typer.Option("--salida", help="Guardar aquí la respuesta (con --enviar) o el prompt."),
    ] = None,
) -> None:
    """Muestra el prompt de generación de un servicio con su contexto GraphRAG (y lo prueba)."""
    import yaml
    from pydantic import ValidationError

    from orchestrator.architecture import Arquitectura
    from orchestrator.generation import ErrorParametros, parametros_de_arquitectura
    from orchestrator.generation import especificacion as especificacion_de_servicio
    from orchestrator.ingest import ModeloRequisitos
    from orchestrator.knowledge import ErrorGrafo
    from orchestrator.knowledge.embeddings import ErrorEmbeddings
    from orchestrator.llm import ErrorLLM, crear_proveedor
    from orchestrator.llm.prompts import (
        EspecificacionServicio,
        contexto_de_seguridad,
        contexto_vacio,
        prompt_especificacion,
        prompt_logica,
    )

    if tarea not in ("especificacion", "logica"):
        raise typer.BadParameter("usa «especificacion» o «logica»", param_hint="--tarea")
    try:
        arq = Arquitectura.model_validate_json(arquitectura.read_bytes())
        modelo = ModeloRequisitos.model_validate_json(requisitos.read_bytes())
    except (OSError, ValidationError) as error:
        typer.echo(
            f"Error: no se pudieron leer la arquitectura o los requisitos: {error}", err=True
        )
        raise typer.Exit(1) from error
    datos = next((s for s in arq.servicios if s.nombre == servicio), None)
    if datos is None:
        nombres = ", ".join(s.nombre for s in arq.servicios)
        raise typer.BadParameter(
            f"no está en la arquitectura; usa: {nombres}", param_hint="--servicio"
        )
    del_servicio = [r for r in modelo.requisitos if r.id in set(datos.requisitos)]

    contexto = contexto_vacio()
    if graphrag:
        try:
            consultor, cerrar = _consultor_graphrag(obtener_configuracion(), k)
            try:
                contexto = contexto_de_seguridad(datos.etiquetas, consultor)
            finally:
                cerrar()
        except (ErrorGrafo, ErrorEmbeddings) as error:
            typer.echo(f"Sin contexto GraphRAG: {error}", err=True)

    if tarea == "especificacion":
        prompt = prompt_especificacion(datos, del_servicio, contexto)
    else:
        if especificacion is None or entidad is None:
            raise typer.BadParameter("la tarea logica necesita --especificacion y --entidad")
        try:
            spec = EspecificacionServicio.model_validate(
                yaml.safe_load(especificacion.read_text(encoding="utf-8"))
            )
            prompt = prompt_logica(spec, entidad, del_servicio, contexto)
        except (OSError, yaml.YAMLError, ValidationError, ValueError) as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from error

    if not enviar:
        texto = prompt.a_texto()
        if salida:
            salida.write_text(texto, encoding="utf-8")
            typer.echo(f"Prompt guardado en {salida.as_posix()} (huella {prompt.huella[:12]})")
        else:
            typer.echo(texto)
        return

    typer.echo(f"Prompt «{prompt.nombre}» v{prompt.version}, huella {prompt.huella[:12]}")
    typer.echo(
        f"Contexto GraphRAG: {len(contexto.coincidencias)} fragmentos, "
        f"{len(contexto.controles)} controles ASVS, {len(contexto.cwe)} CWE"
    )
    try:
        respuesta = prompt.enviar(crear_proveedor(proveedor))
    except ErrorLLM as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error
    if tarea == "especificacion":
        # Lo que fijó la arquitectura (nombre, base, puerto y entidades) y los campos del LLM.
        try:
            parametros = parametros_de_arquitectura(arq).de(servicio)
            resultado = especificacion_de_servicio(parametros, respuesta).para_plantilla()
        except (ErrorParametros, ValidationError) as error:
            typer.echo(f"Error: {error}", err=True)
            raise typer.Exit(1) from error
        texto = yaml.safe_dump(resultado, allow_unicode=True, sort_keys=False)
    else:
        texto = respuesta.model_dump_json(indent=2)
    if salida:
        salida.write_text(texto, encoding="utf-8")
        typer.echo(f"Respuesta validada guardada en {salida.as_posix()}")
    else:
        typer.echo(texto)


@servicio_app.command("trazabilidad")
def servicio_trazabilidad(
    arquitectura: Annotated[
        Path, typer.Argument(help="arquitectura.json aprobada por «arquitectura proponer».")
    ],
    servicios: Annotated[
        Path, typer.Option("--servicios", help="Carpeta con los servicios generados.")
    ] = Path("services"),
    ejecucion: Annotated[
        str | None,
        typer.Option(
            "--ejecucion",
            help="Ejecución de Neo4j a la que enlazar; por defecto, la última con requisitos.",
        ),
    ] = None,
) -> None:
    """Enlaza requisito -> servicio -> archivo en Neo4j para los servicios generados."""
    from pydantic import ValidationError

    from orchestrator.architecture import Arquitectura
    from orchestrator.generation import ErrorParametros, parametros_de_arquitectura
    from orchestrator.generation.trazabilidad import (
        ErrorTrazabilidad,
        enlaces_de_servicios,
        registrar_trazabilidad,
    )
    from orchestrator.knowledge import ErrorGrafo, conectar
    from orchestrator.knowledge.registro import ultima_ejecucion_con_requisitos

    try:
        arq = Arquitectura.model_validate_json(arquitectura.read_bytes())
        parametros = parametros_de_arquitectura(arq)
    except (OSError, ValidationError) as error:
        typer.echo(f"Error: no se pudo leer la arquitectura: {error}", err=True)
        raise typer.Exit(1) from error
    except ErrorParametros as error:
        typer.echo("Error: la arquitectura no se puede parametrizar:", err=True)
        for problema in error.problemas:
            typer.echo(f"  - {problema}", err=True)
        raise typer.Exit(1) from error

    try:
        enlaces = enlaces_de_servicios(parametros.servicios, servicios)
    except ErrorTrazabilidad as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    config = obtener_configuracion()
    try:
        driver = conectar(config)
        try:
            db = config.neo4j_database
            ejecucion_id = ejecucion or ultima_ejecucion_con_requisitos(driver, db)
            if ejecucion_id is None:
                typer.echo("Error: no hay ninguna ejecución con requisitos en Neo4j.", err=True)
                raise typer.Exit(1)
            resumen = registrar_trazabilidad(driver, ejecucion_id, enlaces, base_datos=db)
        finally:
            driver.close()
    except ErrorGrafo as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    typer.echo(f"Ejecución: {ejecucion_id}")
    typer.echo(f"Servicios enlazados: {resumen.servicios}")
    typer.echo(f"Archivos enlazados: {resumen.archivos}")
    typer.echo(f"Requisitos enlazados: {resumen.requisitos_enlazados}")
    if resumen.requisitos_sin_nodo:
        typer.echo(
            "Requisitos sin nodo en esta ejecución (no enlazados): "
            + ", ".join(resumen.requisitos_sin_nodo)
        )


if __name__ == "__main__":
    app()
