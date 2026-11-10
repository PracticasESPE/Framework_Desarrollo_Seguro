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
) -> None:
    """Propone con el LLM los servicios, contextos y decisiones; guarda arquitectura.json."""
    from pydantic import ValidationError

    from orchestrator.architecture import proponer_arquitectura
    from orchestrator.ingest import ModeloRequisitos
    from orchestrator.llm import ErrorLLM, crear_proveedor

    if nivel not in ("razonamiento", "rapido"):
        raise typer.BadParameter("usa «razonamiento» o «rapido»", param_hint="--nivel")
    if not modelo.is_file():
        raise typer.BadParameter(f"no existe el archivo '{modelo}'", param_hint="MODELO")
    try:
        datos = ModeloRequisitos.model_validate_json(modelo.read_bytes())
    except ValidationError as error:
        typer.echo(f"Error: {modelo.name} no es un modelo de requisitos válido.\n{error}", err=True)
        raise typer.Exit(1) from error

    def reintento(intento: int, problemas: list[str]) -> None:
        typer.echo(f"  Intento {intento} rechazado por el motor; se vuelve a pedir:")
        for problema in problemas:
            typer.echo(f"    - {problema}")

    typer.echo(f"Documento: {datos.documento.nombre}, {len(datos.requisitos)} requisitos")
    try:
        llm = crear_proveedor(proveedor)
        arquitectura = proponer_arquitectura(datos, llm, nivel=nivel, al_reintentar=reintento)
    except (ErrorLLM, ValueError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1) from error

    base = modelo.name.removesuffix(".json").removesuffix(".modelo_requisitos") or "documento"
    carpeta = destino or obtener_configuracion().directorio_salida / "arquitectura"
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / f"{base}.arquitectura.json"
    archivo.write_text(arquitectura.model_dump_json(indent=2), encoding="utf-8")

    typer.echo(f"Proveedor: {getattr(llm, 'nombre', proveedor)} ({nivel})")
    typer.echo(f"Servicios: {len(arquitectura.servicios)}")
    for s in arquitectura.servicios:
        dependencias = ", ".join(f"{d.servicio} ({d.tipo})" for d in s.depende_de) or "ninguna"
        typer.echo(
            f"  {s.nombre} [{s.contexto}]: {len(s.requisitos)} requisitos, "
            f"base {s.base_datos}, depende de {dependencias}"
        )
    typer.echo(f"Transversales: {len(arquitectura.transversales)} requisitos")
    typer.echo(f"Decisiones: {len(arquitectura.decisiones)}")
    for d in arquitectura.decisiones:
        typer.echo(f"  {d.id} {d.titulo}")
    typer.echo(f"Arquitectura guardada en {archivo.as_posix()}")


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


if __name__ == "__main__":
    app()
