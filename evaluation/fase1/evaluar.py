"""Evalúa un modelo_requisitos.json de la fase 1 contra la referencia del dataset.

Uso:
    uv run python -m evaluation.fase1.evaluar salida/requisitos/<base>.modelo_requisitos.json \
        evaluation/datasets/01_tienda_en_linea

Solo la evaluación lee referencia.yaml; el framework nunca lo recibe. Un requisito del modelo
corresponde a uno de la referencia si su texto contiene la frase literal de la referencia (cada
«texto» de la referencia es literal del documento). Métricas (plan técnico, 11.2):

- requisitos encontrados: cuántos de la referencia aparecen en el modelo (exhaustividad);
- falsos positivos: requisitos del modelo que no están en la referencia, como el contexto o lo
  que queda fuera del alcance;
- acierto del tipo funcional / no funcional entre los encontrados;
- etiquetas de seguridad: precisión, exhaustividad y F1 sobre todos los pares
  (requisito, etiqueta), como en evaluation/comparacion_llm.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from pydantic import BaseModel

from orchestrator.ingest.requisito import ModeloRequisitos


class Resultado(BaseModel):
    documento: str
    referencia: int
    modelo: int
    encontrados: int
    exhaustividad: float
    falsos_positivos: int
    fuera_de_alcance_como_requisito: int
    tipo_correcto: int
    acierto_tipo: float
    etiquetas_precision: float
    etiquetas_exhaustividad: float
    etiquetas_f1: float
    no_encontrados: list[str]
    tipo_incorrecto: list[str]
    falsos_positivos_texto: list[str]


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def _proporcion(parte: int, total: int) -> float:
    return round(parte / total, 3) if total else 0.0


def evaluar(modelo: ModeloRequisitos, carpeta: Path) -> Resultado:
    referencia = yaml.safe_load((carpeta / "referencia.yaml").read_text(encoding="utf-8"))
    esperados = referencia["requisitos"]
    fuera = [_normalizar(f) for f in referencia.get("fuera_de_alcance", [])]

    usados: set[str] = set()
    tipo_ok, tipo_mal, no_encontrados = 0, [], []
    tp = fp = fn = 0
    for esperado in esperados:
        frase = _normalizar(esperado["texto"])
        candidato = next(
            (r for r in modelo.requisitos if frase in _normalizar(r.texto) and r.id not in usados),
            None,
        )
        etiquetas_esperadas = set(esperado.get("etiquetas", []))
        if candidato is None:
            no_encontrados.append(esperado["id"])
            fn += len(etiquetas_esperadas)
            continue
        usados.add(candidato.id)
        if candidato.tipo == esperado["tipo"]:
            tipo_ok += 1
        else:
            tipo_mal.append(f"{esperado['id']}: {candidato.tipo} (esperado {esperado['tipo']})")
        obtenidas = set(candidato.etiquetas)
        tp += len(obtenidas & etiquetas_esperadas)
        fp += len(obtenidas - etiquetas_esperadas)
        fn += len(etiquetas_esperadas - obtenidas)

    sobrantes = [r for r in modelo.requisitos if r.id not in usados]
    fp += sum(len(r.etiquetas) for r in sobrantes)
    precision, exhaustividad = _proporcion(tp, tp + fp), _proporcion(tp, tp + fn)
    f1 = round(2 * precision * exhaustividad / (precision + exhaustividad), 3) if tp else 0.0
    encontrados = len(esperados) - len(no_encontrados)
    return Resultado(
        documento=referencia["documento"],
        referencia=len(esperados),
        modelo=len(modelo.requisitos),
        encontrados=encontrados,
        exhaustividad=_proporcion(encontrados, len(esperados)),
        falsos_positivos=len(sobrantes),
        fuera_de_alcance_como_requisito=sum(
            1 for r in sobrantes if any(f in _normalizar(r.texto) for f in fuera)
        ),
        tipo_correcto=tipo_ok,
        acierto_tipo=_proporcion(tipo_ok, encontrados),
        etiquetas_precision=precision,
        etiquetas_exhaustividad=exhaustividad,
        etiquetas_f1=f1,
        no_encontrados=no_encontrados,
        tipo_incorrecto=tipo_mal,
        falsos_positivos_texto=[f"{r.id} [{r.ubicacion}] {r.texto[:80]}" for r in sobrantes],
    )


def main(argumentos: list[str] | None = None) -> Resultado:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("modelo", type=Path, help="modelo_requisitos.json generado por la fase 1")
    parser.add_argument("dataset", type=Path, help="carpeta del documento en evaluation/datasets")
    parser.add_argument("--json", type=Path, help="guardar el resultado en este archivo")
    opciones = parser.parse_args(argumentos)

    modelo = ModeloRequisitos.model_validate_json(opciones.modelo.read_bytes())
    resultado = evaluar(modelo, opciones.dataset)
    if opciones.json:
        opciones.json.write_text(resultado.model_dump_json(indent=2), encoding="utf-8")

    r = resultado
    print(
        f"Documento {r.documento}: {r.modelo} requisitos en el modelo, "
        f"{r.referencia} en la referencia"
    )
    print(f"  Encontrados: {r.encontrados}/{r.referencia} ({r.exhaustividad:.0%})")
    print(
        f"  Falsos positivos: {r.falsos_positivos} "
        f"(de ellos, fuera del alcance: {r.fuera_de_alcance_como_requisito})"
    )
    print(f"  Tipo correcto: {r.tipo_correcto}/{r.encontrados} ({r.acierto_tipo:.0%})")
    print(
        f"  Etiquetas: precisión {r.etiquetas_precision:.0%}, "
        f"exhaustividad {r.etiquetas_exhaustividad:.0%}, F1 {r.etiquetas_f1:.2f}"
    )
    for titulo, lista in (
        ("No encontrados", r.no_encontrados),
        ("Tipo incorrecto", r.tipo_incorrecto),
        ("Falsos positivos", r.falsos_positivos_texto),
    ):
        if lista:
            print(f"  {titulo}:")
            for linea in lista:
                print(f"    - {linea}")
    return resultado


if __name__ == "__main__":
    main()
