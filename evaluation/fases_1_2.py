"""Ejecuta las fases 1 y 2 con los documentos del dataset y resume los resultados (sprint 3, #60).

Uso, desde la carpeta del proyecto:

    uv run python -m evaluation.fases_1_2                     # los 3 documentos, en DOCX
    uv run python -m evaluation.fases_1_2 01_tienda_en_linea  # solo uno
    uv run python -m evaluation.fases_1_2 --formato pdf --sin-grafo

Para cada documento de evaluation/datasets y con los comandos del framework:

1. Fase 1: `requisitos clasificar`, `requisitos registrar` (Neo4j) y la evaluación contra la
   referencia (evaluation/fase1).
2. Fase 2: `arquitectura proponer` (ciclo LLM ↔ OPA), la evaluación contra la referencia
   (evaluation/fase2), `arquitectura adr` y `arquitectura diagrama`.

Deja todo en evaluation/resultados/sprint3/<documento>/ y el resumen en
evaluation/resultados/sprint3/README.md. Solo la evaluación lee referencia.yaml; el framework
recibe únicamente el documento.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import yaml

from evaluation.fase1.evaluar import main as evaluar_fase1
from evaluation.fase2.evaluar import main as evaluar_fase2

RAIZ = Path(__file__).resolve().parent.parent
DATASETS = RAIZ / "evaluation" / "datasets"
RESULTADOS = RAIZ / "evaluation" / "resultados" / "sprint3"


def framework(*argumentos: str) -> tuple[int, str, float]:
    """Ejecuta un comando del framework; devuelve el código, la salida y los segundos."""
    inicio = time.perf_counter()
    proceso = subprocess.run(
        [sys.executable, "-m", "orchestrator.cli", *argumentos],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    salida = (proceso.stdout + proceso.stderr).strip()
    return proceso.returncode, salida, round(time.perf_counter() - inicio, 1)


def _relativa(ruta: Path) -> str:
    return ruta.relative_to(RAIZ).as_posix()


def procesar(carpeta: Path, formato: str, grafo: bool, reutilizar: bool = False) -> dict:
    """Ejecuta las fases 1 y 2 con un documento.

    Con `reutilizar`, el modelo de requisitos y la arquitectura que ya estén en la carpeta de
    resultados no se vuelven a pedir al LLM: solo se completan los pasos que faltan.
    """
    referencia = yaml.safe_load((carpeta / "referencia.yaml").read_text(encoding="utf-8"))
    destino = RESULTADOS / carpeta.name
    destino.mkdir(parents=True, exist_ok=True)
    base = f"requisitos-{formato}"
    modelo = destino / f"{base}.modelo_requisitos.json"
    arquitectura = destino / f"{base}.arquitectura.json"
    registro_intentos = destino / f"{base}.intentos.json"
    resumen: dict = {"documento": carpeta.name, "titulo": referencia["titulo"], "pasos": {}}
    registro: list[str] = []

    def paso(nombre: str, *argumentos: str) -> bool:
        codigo, salida, segundos = framework(*argumentos)
        resumen["pasos"][nombre] = {"correcto": codigo == 0, "segundos": segundos}
        registro.append(f"$ framework {' '.join(argumentos)}\n{salida}\n")
        print(f"  {nombre}: {'correcto' if codigo == 0 else 'ERROR'} ({segundos} s)")
        return codigo == 0

    # Al reutilizar se conservan los tiempos medidos en la ejecución anterior.
    archivo_previo = destino / "resumen.json"
    previo = (
        json.loads(archivo_previo.read_text(encoding="utf-8")).get("pasos", {})
        if reutilizar and archivo_previo.is_file()
        else {}
    )

    def reutilizado(nombre: str) -> None:
        resumen["pasos"][nombre] = previo.get(
            nombre, {"correcto": True, "segundos": 0.0, "reutilizado": True}
        )
        print(f"  {nombre}: reutilizado")
        if nombre == "clasificar" and "registrar" in previo:
            resumen["pasos"]["registrar"] = previo["registrar"]

    print(f"{carpeta.name} ({referencia['titulo']})")
    # Fase 1
    entrada = _relativa(carpeta / f"requisitos.{formato}")
    if reutilizar and modelo.is_file():
        reutilizado("clasificar")
    else:
        if not paso("clasificar", "requisitos", "clasificar", entrada, "--destino", str(destino)):
            return _cerrar(resumen, registro, destino)
        if grafo:
            paso("registrar", "requisitos", "registrar", _relativa(modelo))
    resumen["fase1"] = evaluar_fase1(
        [str(modelo), str(carpeta), "--json", str(destino / "evaluacion_fase1.json")]
    ).model_dump()

    # Fase 2
    opciones_grafo = ["--grafo"] if grafo else ["--sin-grafo"]
    if reutilizar and registro_intentos.is_file() and arquitectura.is_file():
        reutilizado("proponer")
        aprobada = True
    else:
        aprobada = paso(
            "proponer",
            "arquitectura",
            "proponer",
            _relativa(modelo),
            "--destino",
            str(destino),
            *opciones_grafo,
        )
    if not registro_intentos.is_file():
        # El LLM o OPA fallaron antes de terminar un intento (el error está en ejecucion.log).
        return _cerrar(resumen, registro, destino)
    intentos = json.loads(registro_intentos.read_text(encoding="utf-8"))
    inferidos = sorted(p["patron"] for p in intentos["intentos"][-1]["decision"]["patrones"])
    esperados = sorted(p["patron"] for p in referencia.get("patrones", []))
    resumen["ciclo"] = {
        "aprobada": intentos["aprobada"],
        "intentos": len(intentos["intentos"]),
        "rechazos": [
            b["motivo"] for i in intentos["intentos"] for b in i["decision"]["bloqueantes"]
        ],
        "patrones": inferidos,
        "patrones_referencia": esperados,
        "avisos": [a["regla"] for a in intentos["intentos"][-1]["decision"]["advertencias"]],
    }
    if not aprobada:
        return _cerrar(resumen, registro, destino)
    resumen["fase2"] = evaluar_fase2(
        [
            str(arquitectura),
            str(modelo),
            str(carpeta),
            "--json",
            str(destino / "evaluacion_fase2.json"),
        ]
    ).model_dump()
    if reutilizar and any((destino / "adr").glob("0*.md")):
        reutilizado("adr")
    else:
        paso(
            "adr",
            "arquitectura",
            "adr",
            _relativa(arquitectura),
            "--requisitos",
            _relativa(modelo),
            "--destino",
            str(destino / "adr"),
        )
    if reutilizar and (destino / "arquitectura.md").is_file():
        reutilizado("diagrama")
    else:
        paso(
            "diagrama",
            "arquitectura",
            "diagrama",
            _relativa(arquitectura),
            "--requisitos",
            _relativa(modelo),
            "--salida",
            str(destino / "arquitectura.md"),
            "--adr",
            str(destino / "adr"),
            "--nombre",
            referencia["titulo"],
        )
    resumen["adr"] = len(list((destino / "adr").glob("0*.md")))
    return _cerrar(resumen, registro, destino)


def _cerrar(resumen: dict, registro: list[str], destino: Path) -> dict:
    (destino / "ejecucion.log").write_text("\n".join(registro), encoding="utf-8")
    (destino / "resumen.json").write_text(
        json.dumps(resumen, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return resumen


def _porcentaje(valor: float) -> str:
    return f"{valor:.0%}"


def _patrones(ciclo: dict) -> str:
    """«4/5 (falta saga; además bff)»: cuántos patrones de la referencia infirió OPA."""
    inferidos, esperados = set(ciclo["patrones"]), set(ciclo.get("patrones_referencia", []))
    texto = f"{len(inferidos & esperados)}/{len(esperados)}"
    notas = []
    if faltan := sorted(esperados - inferidos):
        notas.append(f"falta {', '.join(faltan)}")
    if sobran := sorted(inferidos - esperados):
        notas.append(f"además {', '.join(sobran)}")
    return f"{texto} ({'; '.join(notas)})" if notas else texto


def informe(resumenes: list[dict], formato: str) -> str:
    """El resumen en Markdown de los documentos procesados."""
    lineas = [
        "# Fases 1 y 2 con los documentos del dataset (sprint 3)",
        "",
        f"Generado el {datetime.now(UTC):%d/%m/%Y %H:%M} UTC con "
        f"`uv run python -m evaluation.fases_1_2 --formato {formato}`. Cada carpeta tiene el "
        "modelo de requisitos, la arquitectura aprobada, el registro de intentos del ciclo "
        "LLM ↔ OPA, los ADR, el diagrama C4, las evaluaciones y la salida de cada comando "
        "(`ejecucion.log`).",
        "",
        "## Fase 1: requisitos",
        "",
        "| Documento | Encontrados | Falsos positivos | Tipo correcto | Etiquetas (P / R / F1) |",
        "|---|---|---|---|---|",
    ]
    for r in resumenes:
        f1 = r.get("fase1")
        if f1 is None:
            lineas.append(f"| {r['documento']} | no se pudo clasificar | | | |")
            continue
        lineas.append(
            f"| {r['documento']} | {f1['encontrados']}/{f1['referencia']} "
            f"({_porcentaje(f1['exhaustividad'])}) | {f1['falsos_positivos']} | "
            f"{f1['tipo_correcto']}/{f1['encontrados']} ({_porcentaje(f1['acierto_tipo'])}) | "
            f"{_porcentaje(f1['etiquetas_precision'])} / "
            f"{_porcentaje(f1['etiquetas_exhaustividad'])} / {f1['etiquetas_f1']:.2f} |"
        )
    lineas += [
        "",
        "## Fase 2: arquitectura",
        "",
        "| Documento | Ciclo LLM ↔ OPA | Servicios (propuestos / referencia) | Coinciden | "
        "Agrupación (P / R / F1) | Patrones de la referencia inferidos | ADR |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in resumenes:
        ciclo, f2 = r.get("ciclo"), r.get("fase2")
        if ciclo is None:
            continue
        estado = (
            f"aprobada en el intento {ciclo['intentos']}"
            if ciclo["aprobada"]
            else f"rechazada en {ciclo['intentos']} intentos"
        )
        if f2 is None:
            lineas.append(f"| {r['documento']} | {estado} | | | | | |")
            continue
        lineas.append(
            f"| {r['documento']} | {estado} | {len(f2['servicios_propuestos'])} / "
            f"{len(f2['servicios_referencia'])} | {len(f2['nombres_coincidentes'])} | "
            f"{_porcentaje(f2['pares_precision'])} / {_porcentaje(f2['pares_exhaustividad'])} / "
            f"{f2['pares_f1']:.2f} | {_patrones(ciclo)} | {r.get('adr', 0)} |"
        )
    lineas += ["", "## Detalle por documento", ""]
    for r in resumenes:
        lineas.append(f"### {r['documento']}: {r['titulo']}")
        lineas.append("")
        pasos = ", ".join(
            f"{n} reutilizado"
            if p.get("reutilizado")
            else f"{n} {p['segundos']} s{'' if p['correcto'] else ' (ERROR)'}"
            for n, p in r["pasos"].items()
        )
        lineas.append(f"- Pasos: {pasos}.")
        f1, ciclo, f2 = r.get("fase1"), r.get("ciclo"), r.get("fase2")
        if f1:
            if f1["no_encontrados"]:
                lineas.append(f"- Requisitos no encontrados: {', '.join(f1['no_encontrados'])}.")
            if f1["tipo_incorrecto"]:
                lineas.append(f"- Tipo incorrecto: {'; '.join(f1['tipo_incorrecto'])}.")
            if f1["falsos_positivos_texto"]:
                lineas.append(f"- Falsos positivos: {'; '.join(f1['falsos_positivos_texto'])}.")
        if ciclo:
            if ciclo["rechazos"]:
                lineas.append(f"- Rechazos de OPA: {' / '.join(ciclo['rechazos'])}.")
            if ciclo["avisos"]:
                avisos = Counter(ciclo["avisos"])
                lineas.append(
                    "- Avisos de OPA: "
                    + ", ".join(f"{a} ×{n}" if n > 1 else a for a, n in sorted(avisos.items()))
                    + "."
                )
            lineas.append(f"- Patrones inferidos: {', '.join(ciclo['patrones']) or 'ninguno'}.")
        if f2:
            lineas.append(f"- Servicios propuestos: {', '.join(f2['servicios_propuestos'])}.")
            correspondencia = ", ".join(f"{k} -> {v}" for k, v in f2["correspondencia"].items())
            lineas.append(f"- Correspondencia con la referencia: {correspondencia}.")
        lineas.append("")
    return "\n".join(lineas)


def main(argumentos: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("documentos", nargs="*", help="carpetas de evaluation/datasets")
    parser.add_argument("--formato", default="docx", choices=["docx", "pdf", "txt", "md"])
    parser.add_argument("--sin-grafo", action="store_true", help="no registrar en Neo4j")
    parser.add_argument(
        "--reutilizar",
        action="store_true",
        help="no volver a pedir al LLM el modelo ni la arquitectura que ya estén guardados",
    )
    opciones = parser.parse_args(argumentos)

    carpetas = [DATASETS / d for d in opciones.documentos] or sorted(
        p.parent for p in DATASETS.glob("*/referencia.yaml")
    )
    procesados = [
        procesar(c, opciones.formato, not opciones.sin_grafo, opciones.reutilizar) for c in carpetas
    ]
    # El resumen junta todos los documentos ya procesados, no solo los de esta ejecución: así se
    # puede repetir uno sin volver a gastar la cuota del LLM en los demás.
    resumenes = [
        json.loads(archivo.read_text(encoding="utf-8"))
        for archivo in sorted(RESULTADOS.glob("*/resumen.json"))
    ]
    (RESULTADOS / "README.md").write_text(
        informe(resumenes, opciones.formato) + "\n", encoding="utf-8"
    )
    print(f"Resumen en {_relativa(RESULTADOS / 'README.md')}")
    return 0 if all(r.get("fase2") for r in procesados) else 1


if __name__ == "__main__":
    sys.exit(main())
