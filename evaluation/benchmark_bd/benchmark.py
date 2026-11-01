"""Prueba comparativa Neo4j vs PostgreSQL + pgvector (plan técnico, sección 5.1.4).

Carga la misma base de conocimiento, con los mismos embeddings, en las dos bases y mide la
latencia media, la mediana y el percentil 95 de tres consultas:

1. Trazabilidad a tres saltos: controles que implementan los patrones o directrices que
   mitigan las CWE de un riesgo del API Top 10 (riesgo -> CWE -> práctica -> control).
2. Controles que protegen frente a una CWE: los que la cubren directamente y los que se
   implementan con una práctica que la mitiga.
3. Los 5 fragmentos más parecidos a una pregunta (búsqueda vectorial).

Antes de medir comprueba que las dos bases devuelven los mismos resultados.

Uso:
    docker compose -f evaluation/benchmark_bd/docker-compose.yml up -d
    uv run python -m evaluation.benchmark_bd.benchmark --iteraciones 300
"""

import argparse
import json
import platform
import statistics
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from orchestrator.config import obtener_configuracion
from orchestrator.knowledge import aplicar_esquema, conectar
from orchestrator.knowledge.base_conocimiento import BaseConocimiento, cargar_base_conocimiento
from orchestrator.knowledge.cargador import calcular_version, cargar_en_grafo
from orchestrator.knowledge.embeddings import EmbeddingsLocales
from orchestrator.knowledge.fragmentos import (
    NOMBRE_INDICE,
    cargar_fragmentos,
    generar_fragmentos,
)

CARPETA = Path(__file__).parent

PREGUNTAS = [
    "un usuario puede ver los datos de otro cliente cambiando el identificador",
    "contraseñas escritas en el código fuente",
    "demasiadas peticiones tumban el servicio",
    "punto único de entrada con autenticación centralizada",
    "cada microservicio con su propia base de datos",
    "inyección SQL en las consultas a la base de datos",
    "los errores muestran información interna al usuario",
    "el contenedor se ejecuta como administrador",
    "tokens de sesión sin firma",
    "si un servicio falla no debe tumbar a los demás",
]


class ConfigBenchmark(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BENCHMARK_DB_", env_file=".env", env_ignore_empty=True, extra="ignore"
    )

    host: str = "localhost"
    port: int = 5434
    password: SecretStr | None = None


# --- Consultas equivalentes en los dos motores ----------------------------------------------

NEO4J = {
    "trazabilidad": """
        MATCH (:RiesgoApi {id: $id})-[:INCLUYE]->(:CWE)<-[:MITIGA]-(p)
              <-[:SE_IMPLEMENTA_CON]-(ctl:Control)
        RETURN DISTINCT ctl.id AS id
    """,
    "controles_cwe": """
        MATCH (c:CWE {id: $id})
        CALL (c) {
            MATCH (ctl:Control)-[:CUBRE]->(c) RETURN ctl
            UNION
            MATCH (ctl:Control)-[:SE_IMPLEMENTA_CON]->()-[:MITIGA]->(c) RETURN ctl
        }
        RETURN DISTINCT ctl.id AS id
    """,
    "vectorial": f"""
        CALL db.index.vector.queryNodes('{NOMBRE_INDICE}', 5, $vector) YIELD node
        RETURN node.id AS id
    """,
}

POSTGRES = {
    "trazabilidad": """
        SELECT DISTINCT i.control_id
        FROM incluye inc
        JOIN mitiga m ON m.cwe_id = inc.cwe_id
        JOIN implementa i ON i.practica_id = m.practica_id
        WHERE inc.riesgo_id = %(id)s
    """,
    "controles_cwe": """
        SELECT control_id FROM cubre WHERE cwe_id = %(id)s
        UNION
        SELECT i.control_id FROM mitiga m
        JOIN implementa i ON i.practica_id = m.practica_id
        WHERE m.cwe_id = %(id)s
    """,
    "vectorial": """
        SELECT id FROM fragmento ORDER BY embedding <=> %(vector)s::vector LIMIT 5
    """,
}

DESCRIPCIONES = {
    "trazabilidad": "Trazabilidad a 3 saltos (riesgo → CWE → práctica → control)",
    "controles_cwe": "Controles que protegen frente a una CWE",
    "vectorial": "5 fragmentos más parecidos (búsqueda vectorial)",
}


# --- Estadística y presentación ---------------------------------------------------------------


def percentil(valores: list[float], p: float) -> float:
    """Percentil con interpolación lineal (el mismo método que numpy por defecto)."""
    if not valores:
        raise ValueError("Sin valores")
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * p / 100
    inferior = int(posicion)
    superior = min(inferior + 1, len(ordenados) - 1)
    fraccion = posicion - inferior
    return ordenados[inferior] + (ordenados[superior] - ordenados[inferior]) * fraccion


def resumir(milisegundos: list[float]) -> dict[str, float]:
    return {
        "media": round(statistics.fmean(milisegundos), 3),
        "p50": round(percentil(milisegundos, 50), 3),
        "p95": round(percentil(milisegundos, 95), 3),
        "muestras": len(milisegundos),
    }


def _tabla(latencias: dict[str, Any], clave_neo: str, clave_pg: str) -> list[str]:
    filas = [
        "| Consulta | Motor | Media | Mediana (p50) | p95 | Más rápido |",
        "|---|---|---|---|---|---|",
    ]
    for clave, descripcion in DESCRIPCIONES.items():
        neo, pg = latencias[clave][clave_neo], latencias[clave][clave_pg]
        rapido, lento = sorted([("Neo4j", neo), ("PostgreSQL", pg)], key=lambda x: x[1]["media"])
        veces = lento[1]["media"] / rapido[1]["media"] if rapido[1]["media"] else 0
        filas.append(
            f"| {descripcion} | Neo4j | {neo['media']} | {neo['p50']} | {neo['p95']} "
            f"| {rapido[0]} ({veces:.1f}×) |"
        )
        filas.append(f"| | PostgreSQL | {pg['media']} | {pg['p50']} | {pg['p95']} | |")
    return filas


def tabla_markdown(resultados: dict[str, Any]) -> str:
    lineas = [
        "# Prueba comparativa: Neo4j vs PostgreSQL + pgvector",
        "",
        f"Ejecutada el {resultados['fecha']} en {resultados['equipo']}. "
        f"{resultados['iteraciones']} mediciones por consulta y motor, tras "
        f"{resultados['calentamiento']} de calentamiento. Latencias en milisegundos, medidas "
        "desde el cliente en Python (incluyen la ida y vuelta por la red local de Docker).",
        "",
        f"Datos: {resultados['datos']['nodos']} elementos de conocimiento, "
        f"{resultados['datos']['relaciones']} relaciones y {resultados['datos']['fragmentos']} "
        f"fragmentos con embeddings de {resultados['datos']['dimensiones']} dimensiones, "
        "idénticos en las dos bases.",
        "",
        "## Latencia vista desde el motor del framework (cliente)",
        "",
        "Conexión reutilizada en los dos casos: una sesión de Neo4j y una conexión de PostgreSQL.",
        "",
        *_tabla(resultados["latencias"], "neo4j", "postgres"),
        "",
        "## Tiempo dentro de cada base (servidor)",
        "",
        "Neo4j: tiempo hasta tener y entregar el resultado, según el resumen de la consulta. "
        "PostgreSQL: planificación más ejecución, según EXPLAIN ANALYZE. "
        "Excluye la red y el driver.",
        "",
        *_tabla(resultados["latencias"], "neo4j_servidor", "postgres_servidor"),
        "",
        "## Neo4j con una transacción gestionada por consulta",
        "",
        "Es lo que hace hoy el motor (driver.execute_query): cada consulta abre su propia "
        "transacción con reintentos automáticos.",
        "",
        "| Consulta | Media | Mediana (p50) | p95 |",
        "|---|---|---|---|",
        *[
            f"| {d} | {resultados['latencias'][k]['neo4j_transaccion']['media']} "
            f"| {resultados['latencias'][k]['neo4j_transaccion']['p50']} "
            f"| {resultados['latencias'][k]['neo4j_transaccion']['p95']} |"
            for k, d in DESCRIPCIONES.items()
        ],
    ]

    coincidencia = resultados["verificacion"]
    lineas += [
        "",
        "## Verificación de resultados",
        "",
        f"- Trazabilidad: las dos bases devuelven los mismos controles en "
        f"{coincidencia['trazabilidad']} de {coincidencia['total_trazabilidad']} riesgos.",
        f"- Controles por CWE: mismos controles en {coincidencia['controles_cwe']} de "
        f"{coincidencia['total_controles_cwe']} CWE.",
        f"- Búsqueda vectorial: coincidencia media del top 5 entre las dos bases del "
        f"{coincidencia['vectorial']:.0%} (los índices HNSW son aproximados).",
        "",
    ]
    return "\n".join(lineas)


# --- Carga -----------------------------------------------------------------------------------


class EmbeddingsEnCache:
    """Calcula cada embedding una sola vez para que las dos bases reciban los mismos vectores."""

    def __init__(self, proveedor):
        self._proveedor = proveedor
        self.modelo = proveedor.modelo
        self.dimensiones = proveedor.dimensiones
        self._cache: dict[str, list[float]] = {}

    def embeber(self, textos: list[str]) -> list[list[float]]:
        pendientes = [t for t in dict.fromkeys(textos) if t not in self._cache]
        if pendientes:
            self._cache.update(zip(pendientes, self._proveedor.embeber(pendientes), strict=True))
        return [self._cache[t] for t in textos]


def _vector(valores: list[float]) -> str:
    return "[" + ",".join(f"{v:.7f}" for v in valores) + "]"


def _parametros_pg(parametros: dict[str, Any]) -> dict[str, Any]:
    return {k: _vector(v) if k == "vector" else v for k, v in parametros.items()}


def cargar_postgres(conexion, base: BaseConocimiento, proveedor) -> None:
    with conexion.cursor() as cur:
        cur.execute((CARPETA / "esquema.sql").read_text(encoding="utf-8"))
        cur.executemany(
            "INSERT INTO cwe VALUES (%s, %s)", [(d.id, d.nombre) for d in base.debilidades]
        )
        cur.executemany(
            "INSERT INTO practica VALUES (%s, %s, %s)",
            [(p.id, "Patron", p.patron) for p in base.patrones]
            + [(d.id, "Directriz", d.directriz) for d in base.directrices],
        )
        cur.executemany(
            "INSERT INTO control VALUES (%s, %s)", [(c.id, c.descripcion) for c in base.controles]
        )
        cur.executemany(
            "INSERT INTO riesgo VALUES (%s, %s)", [(r.id, r.nombre) for r in base.riesgos_api]
        )
        practicas = [*base.patrones, *base.directrices]
        cur.executemany(
            "INSERT INTO mitiga VALUES (%s, %s)",
            [(p.id, c) for p in practicas for c in p.cwe_mitigadas],
        )
        cur.executemany(
            "INSERT INTO implementa VALUES (%s, %s)",
            [(c, p.id) for p in practicas for c in p.controles_asociados],
        )
        cur.executemany(
            "INSERT INTO cubre VALUES (%s, %s)", [(c.id, w) for c in base.controles for w in c.cwe]
        )
        cur.executemany(
            "INSERT INTO previene VALUES (%s, %s)",
            [(c, r.id) for r in base.riesgos_api for c in r.controles],
        )
        cur.executemany(
            "INSERT INTO incluye VALUES (%s, %s)",
            [(r.id, w) for r in base.riesgos_api for w in r.cwe],
        )
        fragmentos = generar_fragmentos(base)
        vectores = proveedor.embeber([f.texto for f in fragmentos])
        cur.executemany(
            "INSERT INTO fragmento VALUES (%s, %s, %s, %s::vector)",
            [
                (f.id, f.origen_id, f.texto, _vector(v))
                for f, v in zip(fragmentos, vectores, strict=True)
            ],
        )
        cur.execute("ANALYZE")
    conexion.commit()


def contar_datos(base: BaseConocimiento, dimensiones: int) -> dict[str, int]:
    practicas = [*base.patrones, *base.directrices]
    relaciones = (
        sum(len(p.cwe_mitigadas) + len(p.controles_asociados) for p in practicas)
        + sum(len(c.cwe) for c in base.controles)
        + sum(len(r.cwe) + len(r.controles) for r in base.riesgos_api)
    )
    return {
        "nodos": len(practicas)
        + len(base.controles)
        + len(base.debilidades)
        + len(base.riesgos_api),
        "relaciones": relaciones,
        "fragmentos": len(generar_fragmentos(base)),
        "dimensiones": dimensiones,
    }


# --- Medición --------------------------------------------------------------------------------


def medir(
    funcion: Callable[[Any], float | None],
    parametros: list[Any],
    calentamiento: int,
    iteraciones: int,
) -> dict[str, dict[str, float]]:
    """Latencia vista desde el cliente y, si la función lo informa, tiempo en el servidor."""
    for i in range(calentamiento):
        funcion(parametros[i % len(parametros)])
    cliente, servidor = [], []
    for i in range(iteraciones):
        inicio = time.perf_counter()
        en_servidor = funcion(parametros[i % len(parametros)])
        cliente.append((time.perf_counter() - inicio) * 1000)
        if en_servidor is not None:
            servidor.append(en_servidor)
    resultado = {"cliente": resumir(cliente)}
    if servidor:
        resultado["servidor"] = resumir(servidor)
    return resultado


def principal(argv: list[str] | None = None) -> int:
    argumentos = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argumentos.add_argument("--iteraciones", type=int, default=300)
    argumentos.add_argument("--calentamiento", type=int, default=30)
    opciones = argumentos.parse_args(argv)

    config = obtener_configuracion()
    config_pg = ConfigBenchmark()
    if config_pg.password is None:
        print("Falta BENCHMARK_DB_PASSWORD en .env", file=sys.stderr)
        return 1

    base = cargar_base_conocimiento()
    print(f"Cargando el modelo de embeddings {config.embeddings_modelo}...")
    proveedor = EmbeddingsEnCache(
        EmbeddingsLocales(config.embeddings_modelo, config.embeddings_cache)
    )

    driver = conectar(config)
    db = config.neo4j_database
    conexion = psycopg.connect(
        host=config_pg.host,
        port=config_pg.port,
        dbname="benchmark",
        user="benchmark",
        password=config_pg.password.get_secret_value(),
    )
    try:
        print("Cargando la base de conocimiento en Neo4j...")
        version = calcular_version()
        aplicar_esquema(driver, db)
        cargar_en_grafo(driver, base, version, base_datos=db)
        cargar_fragmentos(driver, base, proveedor, version, base_datos=db)
        driver.execute_query("CALL db.awaitIndexes(120)", database_=db)

        print("Cargando la misma base en PostgreSQL + pgvector...")
        cargar_postgres(conexion, base, proveedor)

        vectores = proveedor.embeber(PREGUNTAS)
        parametros = {
            "trazabilidad": [{"id": r.id} for r in base.riesgos_api],
            "controles_cwe": [{"id": d.id} for d in base.debilidades],
            "vectorial": [{"vector": v} for v in vectores],
        }

        sesion = driver.session(database=db)

        def neo4j_ids(clave, p):
            return {r["id"] for r in sesion.run(NEO4J[clave], p)}

        def postgres_ids(clave, p):
            with conexion.cursor() as cur:
                cur.execute(POSTGRES[clave], _parametros_pg(p))
                return {fila[0] for fila in cur.fetchall()}

        def neo4j_medido(clave):
            # Sesión reutilizada, como la conexión de PostgreSQL. El resumen trae el tiempo
            # que Neo4j dedicó a la consulta por dentro (hasta tener y entregar el resultado).
            def consulta(p):
                resultado = sesion.run(NEO4J[clave], p)
                list(resultado)
                resumen = resultado.consume()
                return float(resumen.result_available_after + resumen.result_consumed_after)

            return consulta

        def neo4j_transaccion(clave):
            # execute_query: una transacción gestionada por consulta, con reintentos.
            def consulta(p):
                driver.execute_query(NEO4J[clave], p, database_=db)

            return consulta

        def postgres_medido(clave):
            def consulta(p):
                with conexion.cursor() as cur:
                    cur.execute(POSTGRES[clave], _parametros_pg(p))
                    cur.fetchall()

            return consulta

        def postgres_servidor(clave):
            # EXPLAIN ANALYZE ejecuta la consulta y devuelve su tiempo de planificación y ejecución.
            def consulta(p):
                with conexion.cursor() as cur:
                    cur.execute(
                        "EXPLAIN (ANALYZE, FORMAT JSON) " + POSTGRES[clave], _parametros_pg(p)
                    )
                    plan = cur.fetchone()[0][0]
                    return float(plan["Planning Time"] + plan["Execution Time"])

            return consulta

        print("Verificando que las dos bases devuelven lo mismo...")
        verificacion = {}
        for clave in ("trazabilidad", "controles_cwe"):
            iguales = sum(neo4j_ids(clave, p) == postgres_ids(clave, p) for p in parametros[clave])
            verificacion[clave] = iguales
            verificacion[f"total_{clave}"] = len(parametros[clave])
        solapes = [
            len(neo4j_ids("vectorial", p) & postgres_ids("vectorial", p)) / 5
            for p in parametros["vectorial"]
        ]
        verificacion["vectorial"] = statistics.fmean(solapes)

        latencias = {}
        n, c = opciones.iteraciones, opciones.calentamiento
        for clave in DESCRIPCIONES:
            print(f"Midiendo: {DESCRIPCIONES[clave]}...")
            neo = medir(neo4j_medido(clave), parametros[clave], c, n)
            pg_servidor = medir(postgres_servidor(clave), parametros[clave], c, n)
            latencias[clave] = {
                "neo4j": neo["cliente"],
                "postgres": medir(postgres_medido(clave), parametros[clave], c, n)["cliente"],
                "neo4j_transaccion": medir(neo4j_transaccion(clave), parametros[clave], c, n)[
                    "cliente"
                ],
                "neo4j_servidor": neo["servidor"],
                "postgres_servidor": pg_servidor["servidor"],
            }
        sesion.close()
    finally:
        conexion.close()
        driver.close()

    resultados = {
        "fecha": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "equipo": f"{platform.system()} {platform.release()}, Python {platform.python_version()}",
        "iteraciones": opciones.iteraciones,
        "calentamiento": opciones.calentamiento,
        "datos": contar_datos(base, proveedor.dimensiones),
        "motores": {"neo4j": "neo4j:5.26-community", "postgres": "pgvector/pgvector:0.8.1-pg17"},
        "verificacion": verificacion,
        "latencias": latencias,
    }
    (CARPETA / "resultados.json").write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    tabla = tabla_markdown(resultados)
    (CARPETA / "resultados.md").write_text(tabla, encoding="utf-8")
    print(tabla)
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
