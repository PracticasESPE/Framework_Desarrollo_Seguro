"""Ejecuta las fases 1 a 4 con documentos del dataset y resume los resultados (sprint 4, #75/#76).

Uso, desde la carpeta del proyecto:

    uv run python -m evaluation.fases_1_4 03_citas_medicas            # un documento
    uv run python -m evaluation.fases_1_4 --sin-grafo                  # los 3, sin Neo4j
    uv run python -m evaluation.fases_1_4 03_citas_medicas --reutilizar

Para cada documento de evaluation/datasets, con los comandos del framework:

1. Fases 1 y 2: las de evaluation/fases_1_2.py (requisitos, arquitectura con el ciclo LLM ↔ OPA,
   ADR, diagrama y sus evaluaciones contra la referencia).
2. Fase 3: `servicio sistema`, un microservicio por servicio de la arquitectura aprobada.
3. Fase 4: el Gate 1 sobre los servicios generados (scripts/gate1-servicios.sh) y la decisión de
   OPA de cada uno (`gates servicios`). Necesita Docker.

Deja el resumen y lo necesario para revisar los resultados en
evaluation/resultados/sprint4/fases_1_4/<documento>/: el resumen de cada fase, la especificación de
cada servicio, el resumen de la fase 3 (sistema.json), la decisión del Gate 1 de cada servicio y
sus hallazgos uno por uno (hallazgos_gate1.json). El código generado (unos 50 archivos por
servicio) queda en salida/servicios/; en GitHub Actions se guarda como artefacto. La salida de la
fase 3 va en fase3.log, que se acumula entre ejecuciones, y la del Gate 1 en fase4.log.

Con --reutilizar, además, la fase 3 continúa en la carpeta de la ejecución anterior
(`servicio sistema --reanudar`): conserva los servicios completos y genera los que el límite de uso
del LLM dejó sin terminar. El tiempo de la fase 3 es la suma de sus ejecuciones.

Con --hasta-completar N repite esa reanudación (hasta N veces) y pasa el Gate 1 una sola vez al
final. Solo espera (--espera, 30 min por defecto) si un intento no avanzó, que suele ser la cuota
del LLM; si ya están todos los servicios, va directo al Gate 1:
    uv run python -m evaluation.fases_1_4 03_citas_medicas --sin-grafo --hasta-completar 8
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from evaluation.fases_1_2 import ARCHIVO_USO, DATASETS, RAIZ, framework, procesar, uso_por_fase

RESULTADOS = RAIZ / "evaluation" / "resultados" / "sprint4" / "fases_1_4"
SERVICIOS = RAIZ / "salida" / "servicios"
SARIF_SERVICIOS = RAIZ / "salida" / "security" / "sarif" / "servicios"
DECISIONES = RAIZ / "salida" / "gates" / "servicios"
HERRAMIENTAS = ("eslint", "semgrep", "gitleaks", "trivy-fs", "trivy-config", "hadolint")


def _es_windows() -> bool:
    return os.name == "nt"


def _bash() -> str:
    """Git Bash en Windows (el «bash» de PowerShell es el de WSL); bash en los demás."""
    if _es_windows():
        git_bash = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/bin/bash.exe"
        if git_bash.is_file():
            return str(git_bash)
    return shutil.which("bash") or "bash"


def gate1(carpeta_servicios: Path) -> tuple[int, str, float]:
    """scripts/gate1-servicios.sh sobre la carpeta de los servicios."""
    # Rutas de Docker sin convertir en Git Bash y salida de Python en UTF-8.
    entorno = {**os.environ, "MSYS_NO_PATHCONV": "1", "PYTHONIOENCODING": "utf-8"}
    inicio = time.perf_counter()
    proceso = subprocess.run(
        [_bash(), "scripts/gate1-servicios.sh", carpeta_servicios.relative_to(RAIZ).as_posix()],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=entorno,
        check=False,
    )
    return (
        proceso.returncode,
        proceso.stdout + proceso.stderr,
        round(time.perf_counter() - inicio, 1),
    )


def hallazgos_del_gate1(servicios: list[str]) -> dict[str, dict]:
    """Por servicio: la decisión de OPA y cada hallazgo de cada herramienta."""
    from orchestrator.gates.sarif import ErrorSarif, leer_sarif

    revision: dict[str, dict] = {}
    for servicio in servicios:
        decision_archivo = DECISIONES / servicio / "gate1.json"
        decision = (
            json.loads(decision_archivo.read_text(encoding="utf-8"))["decision"]
            if decision_archivo.is_file()
            else None
        )
        herramientas: dict[str, object] = {}
        for herramienta in HERRAMIENTAS:
            sarif = SARIF_SERVICIOS / servicio / f"{herramienta}.sarif"
            if not sarif.is_file():
                herramientas[herramienta] = "sin resultado (la herramienta no terminó)"
                continue
            try:
                herramientas[herramienta] = [
                    {
                        "regla": h.regla_id,
                        "severidad": h.severidad.value,
                        "archivo": h.archivo,
                        "linea": h.linea_inicio,
                        "mensaje": h.mensaje[:300],
                    }
                    for h in leer_sarif(sarif)
                ]
            except ErrorSarif as error:
                herramientas[herramienta] = f"SARIF no válido: {error}"
        compila = (SARIF_SERVICIOS / servicio / "compilacion.txt").is_file() and (
            (SARIF_SERVICIOS / servicio / "compilacion.txt").read_text(encoding="utf-8").strip()
            == "ok"
        )
        revision[servicio] = {
            "aprobado": decision["aprobado"] if decision else None,
            "justificacion": decision["justificacion"] if decision else "sin decisión de OPA",
            "bloqueantes": [b["motivo"] for b in decision["bloqueantes"]] if decision else [],
            "compila": compila,
            "herramientas": herramientas,
        }
    return revision


def procesar_fases_1_4(
    carpeta: Path,
    formato: str,
    grafo: bool,
    reutilizar: bool,
    con_gate1: bool,
    resultados: Path = RESULTADOS,
) -> dict:
    """Las fases 1 a 4 con un documento; devuelve el resumen y lo guarda en resultados/."""
    destino = resultados / carpeta.name
    # Antes de las fases 1 y 2, que reescriben resumen.json.
    anterior = _fase3_anterior(destino) if reutilizar else None
    resumen = procesar(carpeta, formato, grafo, reutilizar=reutilizar, resultados=resultados)
    base = f"requisitos-{formato}"
    arquitectura = destino / f"{base}.arquitectura.json"
    modelo = destino / f"{base}.modelo_requisitos.json"
    if not (resumen.get("ciclo") or {}).get("aprobada") or not arquitectura.is_file():
        print("  fase 3: no se ejecuta (la fase 2 no dejó una arquitectura aprobada)")
        return _guardar(resumen, destino)

    # Fase 3: cada ejecución en una carpeta nueva (o la anterior, al reanudar); las dependencias
    # se comparten entre todas.
    paso_previo = (anterior or {}).get("paso", {})
    if anterior is not None:
        carpeta_servicios = anterior["carpeta"]
    else:
        fecha = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        carpeta_servicios = SERVICIOS / f"eval-{carpeta.name}-{fecha}"
    if anterior is not None and anterior["completa"]:
        print("  fase 3: reutilizada (todos los servicios completos)")
        resumen["pasos"]["sistema"] = paso_previo or {
            "correcto": True,
            "segundos": 0.0,
            "reutilizado": True,
        }
    else:
        opciones = ["--graphrag"] if grafo else ["--sin-graphrag"]
        if anterior is not None:
            opciones.append("--reanudar")
        codigo, salida, segundos = framework(
            "servicio",
            "sistema",
            str(arquitectura.relative_to(RAIZ)),
            "--requisitos",
            str(modelo.relative_to(RAIZ)),
            "--destino",
            str(carpeta_servicios.relative_to(RAIZ)),
            *opciones,
            registro_uso=destino / ARCHIVO_USO,
        )
        estado = "correcto" if codigo == 0 else "con servicios incompletos"
        print(f"  fase 3{' (reanudada)' if anterior else ''}: {estado} ({segundos} s)")
        resumen["pasos"]["sistema"] = {
            "correcto": codigo == 0,
            "segundos": round(paso_previo.get("segundos", 0.0) + segundos, 1),
            "ejecuciones": paso_previo.get("ejecuciones", 1 if anterior else 0) + 1,
        }
        _anadir_registro(
            destino, f"$ framework servicio sistema {' '.join(opciones)} …\n{salida}\n", "fase3.log"
        )
    sistema = carpeta_servicios / "sistema.json"
    if not sistema.is_file():
        return _guardar(resumen, destino)
    datos = json.loads(sistema.read_text(encoding="utf-8"))
    shutil.copyfile(sistema, destino / "sistema.json")
    shutil.copytree(
        carpeta_servicios / "especificaciones", destino / "especificaciones", dirs_exist_ok=True
    )
    resumen["carpeta_servicios"] = carpeta_servicios.relative_to(RAIZ).as_posix()
    resumen["fase3"] = _resumen_fase3(datos)

    # Fase 4: Gate 1 sobre los servicios generados.
    if not con_gate1:
        print("  fase 4: omitida (--sin-gate1)")
        return _guardar(resumen, destino)
    codigo, salida, segundos = gate1(carpeta_servicios)
    print(
        f"  fase 4 (Gate 1): {'sin hallazgos' if codigo == 0 else 'con hallazgos'} ({segundos} s)"
    )
    resumen["pasos"]["gate1"] = {"correcto": codigo == 0, "segundos": segundos}
    (destino / "fase4.log").write_text(
        f"$ bash scripts/gate1-servicios.sh …\n{salida[-20000:]}\n", encoding="utf-8"
    )
    codigo, salida, _ = framework(
        "gates", "servicios", "--sarif", str(SARIF_SERVICIOS.relative_to(RAIZ)), "--no-bloquear"
    )
    _anadir_registro(destino, f"$ framework gates servicios\n{salida}\n", "fase4.log")
    generados = [
        s["servicio"] for s in datos["servicios"] if (carpeta_servicios / s["servicio"]).is_dir()
    ]
    revision = hallazgos_del_gate1(generados)
    (destino / "hallazgos_gate1.json").write_text(
        json.dumps(revision, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    resumen["fase4"] = _resumen_fase4(revision)
    return _guardar(resumen, destino)


def _servicios_completos(destino: Path) -> tuple[int, int] | None:
    """(completos, total) de la fase 3 guardada en resumen.json, o None si no hay."""
    try:
        previo = json.loads((destino / "resumen.json").read_text(encoding="utf-8"))
        sistema = json.loads(
            (RAIZ / previo["carpeta_servicios"] / "sistema.json").read_text(encoding="utf-8")
        )
    except (OSError, KeyError, ValueError):
        return None
    return int(sistema["completos"]), len(sistema["servicios"])


def procesar_hasta_completar(
    carpeta: Path,
    formato: str,
    grafo: bool,
    con_gate1: bool,
    resultados: Path = RESULTADOS,
    intentos: int = 8,
    espera_minutos: float = 30.0,
    dormir=time.sleep,
) -> dict:
    """Repite la fase 3 (reanudándola) hasta que estén todos los servicios y entonces pasa el
    Gate 1 una sola vez. Solo espera si un intento no avanzó (lo normal es una cuota agotada); si
    ya están completos, no espera ni vuelve a llamar al LLM."""
    destino = resultados / carpeta.name
    estado = _servicios_completos(destino)
    resumen: dict = {}
    for numero in range(1, intentos + 1):
        if estado is not None and estado[0] == estado[1]:
            break
        antes = estado[0] if estado else -1
        resumen = procesar_fases_1_4(carpeta, formato, grafo, True, False, resultados)
        estado = _servicios_completos(destino)
        if estado is None or estado[0] == estado[1]:
            break
        print(f"  intento {numero}: {estado[0]} de {estado[1]} servicios completos")
        if estado[0] <= antes and numero < intentos:
            print(f"  sin avance: se espera {espera_minutos:g} min (cuota del LLM)")
            dormir(espera_minutos * 60)
    return procesar_fases_1_4(carpeta, formato, grafo, True, con_gate1, resultados) or resumen


def _resumen_fase3(datos: dict) -> dict:
    entidades = [e for s in datos["servicios"] for e in s["entidades"]]
    con_logica = [e for e in entidades if e["logica"] == "aceptada"]
    return {
        "servicios": len(datos["servicios"]),
        "completos": datos["completos"],
        "entidades": len(entidades),
        "logica_aceptada": len(con_logica),
        "logica_al_primer_intento": sum(e["intentos_logica"] == 1 for e in con_logica),
        "sin_logica": sum(e["logica"] == "sin_logica" for e in entidades),
        "logica_con_error": sum(e["logica"] == "error" for e in entidades),
        "pruebas_aceptadas": sum(e["pruebas_aceptadas"] for e in entidades),
        "pruebas_descartadas": sum(e["pruebas_descartadas"] for e in entidades),
        "pendientes": sum(len(e["pendientes"]) for e in entidades),
        "advertencias": datos.get("advertencias", []),
    }


def _resumen_fase4(revision: dict[str, dict]) -> dict:
    hallazgos = [
        h
        for r in revision.values()
        for lista in r["herramientas"].values()
        if isinstance(lista, list)
        for h in lista
    ]
    por_severidad: dict[str, int] = {}
    for h in hallazgos:
        por_severidad[h["severidad"]] = por_severidad.get(h["severidad"], 0) + 1
    return {
        "aprobados": sum(bool(r["aprobado"]) for r in revision.values()),
        "servicios": len(revision),
        "hallazgos": len(hallazgos),
        "por_severidad": por_severidad,
    }


def _anadir_registro(destino: Path, texto: str, archivo: str) -> None:
    with (destino / archivo).open("a", encoding="utf-8") as registro:
        registro.write(texto)


def _fase3_anterior(destino: Path) -> dict | None:
    """La carpeta de la fase 3 de la ejecución anterior, si dejó su sistema.json."""
    try:
        previo = json.loads((destino / "resumen.json").read_text(encoding="utf-8"))
        carpeta = RAIZ / previo["carpeta_servicios"]
        sistema = json.loads((carpeta / "sistema.json").read_text(encoding="utf-8"))
    except (OSError, KeyError, ValueError):
        return None
    return {
        "carpeta": carpeta,
        "completa": sistema["completos"] == len(sistema["servicios"]),
        "paso": previo.get("pasos", {}).get("sistema", {}),
    }


def _guardar(resumen: dict, destino: Path) -> dict:
    resumen["uso_llm"] = uso_por_fase(destino / ARCHIVO_USO)
    (destino / "resumen.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return resumen


def informe(resumenes: list[dict]) -> str:
    """Resumen en Markdown de las fases 1 a 4 de los documentos procesados."""
    lineas = [
        "# Fases 1 a 4 con los documentos del dataset (sprint 4)",
        "",
        f"Generado el {datetime.now(UTC):%d/%m/%Y %H:%M} UTC con "
        "`uv run python -m evaluation.fases_1_4`. Cada carpeta tiene lo de las fases 1 y 2 (ver "
        "sprint 3), la especificación de cada servicio (`especificaciones/`), el resumen de la "
        "fase 3 (`sistema.json`) y los hallazgos del Gate 1 uno por uno (`hallazgos_gate1.json`).",
        "",
        "| Documento | Requisitos | Arquitectura | Servicios completos | Entidades con lógica "
        "(al 1.er intento) | Pruebas Jest | Gate 1 aprobados | Hallazgos |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in resumenes:
        f1, ciclo, f3, f4 = r.get("fase1"), r.get("ciclo"), r.get("fase3"), r.get("fase4")
        requisitos = f"{f1['encontrados']}/{f1['referencia']}" if f1 else "-"
        arquitectura = (
            f"aprobada (intento {ciclo['intentos']})"
            if ciclo and ciclo["aprobada"]
            else ("rechazada" if ciclo else "-")
        )
        if f3:
            servicios = f"{f3['completos']}/{f3['servicios']}"
            logica = f"{f3['logica_aceptada']}/{f3['entidades']} ({f3['logica_al_primer_intento']})"
            pruebas = f"{f3['pruebas_aceptadas']} (descartadas {f3['pruebas_descartadas']})"
        else:
            servicios = logica = pruebas = "-"
        gate = f"{f4['aprobados']}/{f4['servicios']}" if f4 else "-"
        hallazgos = str(f4["hallazgos"]) if f4 else "-"
        lineas.append(
            f"| {r['documento']} | {requisitos} | {arquitectura} | {servicios} | {logica} | "
            f"{pruebas} | {gate} | {hallazgos} |"
        )
    lineas += ["", "## Detalle", ""]
    for r in resumenes:
        lineas += [f"### {r['documento']}: {r['titulo']}", ""]
        pasos = ", ".join(
            f"{n} {p['segundos']} s"
            + (f" en {p['ejecuciones']} ejecuciones" if p.get("ejecuciones", 1) > 1 else "")
            + ("" if p["correcto"] else " (con problemas)")
            for n, p in r["pasos"].items()
            if not p.get("reutilizado")
        )
        lineas.append(f"- Pasos: {pasos}.")
        if uso := r.get("uso_llm"):
            por_fase = ", ".join(
                f"fase {f.removeprefix('fase')} {_miles(u['tokens'])} ({u['llamadas']} llamadas)"
                for f, u in uso.items()
            )
            total = sum(u["tokens"] for u in uso.values())
            lineas.append(f"- Tokens del LLM: {por_fase}; total {_miles(total)}.")
        if f3 := r.get("fase3"):
            lineas.append(
                f"- Fase 3: {f3['sin_logica']} entidades sin lógica (para revisión), "
                f"{f3['logica_con_error']} con error al pedirla, {f3['pendientes']} reglas "
                "pendientes declaradas por el LLM."
            )
            for advertencia in f3["advertencias"]:
                lineas.append(f"- Advertencia de la arquitectura: {advertencia}.")
        if f4 := r.get("fase4"):
            severidades = ", ".join(f"{n} {s}" for s, n in sorted(f4["por_severidad"].items()))
            lineas.append(f"- Gate 1: {f4['hallazgos']} hallazgos ({severidades or 'ninguno'}).")
        lineas.append("")
    return "\n".join(lineas)


def _miles(numero: int) -> str:
    """12345 -> «12 345»."""
    return f"{numero:,}".replace(",", " ")


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("documentos", nargs="*", help="carpetas de evaluation/datasets")
    parser.add_argument("--formato", default="docx", choices=["docx", "pdf", "txt", "md"])
    parser.add_argument("--sin-grafo", action="store_true", help="sin Neo4j ni GraphRAG")
    parser.add_argument(
        "--reutilizar",
        action="store_true",
        help="no volver a pedir al LLM el modelo ni la arquitectura que ya estén guardados, y "
        "continuar la fase 3 de la ejecución anterior",
    )
    parser.add_argument("--sin-gate1", action="store_true", help="no ejecutar la fase 4")
    parser.add_argument(
        "--hasta-completar",
        type=int,
        metavar="INTENTOS",
        help="reanudar la fase 3 hasta tener todos los servicios (como mucho INTENTOS veces) y "
        "luego pasar el Gate 1; implica --reutilizar",
    )
    parser.add_argument(
        "--espera",
        type=float,
        default=30.0,
        metavar="MINUTOS",
        help="con --hasta-completar, lo que se espera si un intento no avanza (por defecto 30)",
    )
    parser.add_argument("--resultados", type=Path, default=RESULTADOS, help=argparse.SUPPRESS)
    opciones = parser.parse_args(argumentos)

    carpetas = [DATASETS / d for d in opciones.documentos] or sorted(
        p.parent for p in DATASETS.glob("*/referencia.yaml")
    )
    resultados: Path = opciones.resultados
    resultados.mkdir(parents=True, exist_ok=True)
    for carpeta in carpetas:
        if opciones.hasta_completar:
            procesar_hasta_completar(
                carpeta,
                opciones.formato,
                not opciones.sin_grafo,
                not opciones.sin_gate1,
                resultados,
                opciones.hasta_completar,
                opciones.espera,
            )
            continue
        procesar_fases_1_4(
            carpeta,
            opciones.formato,
            not opciones.sin_grafo,
            opciones.reutilizar,
            not opciones.sin_gate1,
            resultados,
        )
    resumenes = [
        json.loads(archivo.read_text(encoding="utf-8"))
        for archivo in sorted(resultados.glob("*/resumen.json"))
    ]
    (resultados / "README.md").write_text(informe(resumenes), encoding="utf-8")
    print(f"Resumen en {(resultados / 'README.md').relative_to(RAIZ).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
