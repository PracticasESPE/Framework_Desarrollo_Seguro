"""Evalúa una arquitectura.json de la fase 2 contra la referencia del dataset.

Uso:
    uv run python -m evaluation.fase2.evaluar salida/arquitectura/<base>.arquitectura.json \
        salida/requisitos/<base>.modelo_requisitos.json evaluation/datasets/01_tienda_en_linea

Solo la evaluación lee referencia.yaml; el framework nunca lo recibe. Los ids de los requisitos
del modelo no son los de la referencia, así que cada requisito se empareja por su texto (cada
«texto» de la referencia es literal del documento), como en evaluation/fase1.

Métricas:
- servicios: cuántos propone el LLM, cuántos tiene la referencia y qué nombres coinciden;
- agrupación de requisitos: para cada par de requisitos, si están en el mismo servicio en la
  propuesta y en la referencia («transversal» cuenta como un grupo más). La precisión dice cuántos
  de los pares que el LLM juntó también van juntos en la referencia; la exhaustividad, cuántos de
  los pares de la referencia juntó el LLM. No depende de cómo se llame cada servicio.
- correspondencia: a qué servicio propuesto fue a parar la mayoría de los requisitos de cada
  servicio de la referencia.
"""

from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations
from pathlib import Path

import yaml
from pydantic import BaseModel

from orchestrator.architecture import Arquitectura
from orchestrator.ingest.requisito import ModeloRequisitos

TRANSVERSAL = "transversal"


class Resultado(BaseModel):
    documento: str
    servicios_propuestos: list[str]
    servicios_referencia: list[str]
    nombres_coincidentes: list[str]
    requisitos_emparejados: int
    requisitos_referencia: int
    pares_precision: float
    pares_exhaustividad: float
    pares_f1: float
    correspondencia: dict[str, str]


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def _proporcion(parte: int, total: int) -> float:
    return round(parte / total, 3) if total else 0.0


def evaluar(arquitectura: Arquitectura, modelo: ModeloRequisitos, carpeta: Path) -> Resultado:
    referencia = yaml.safe_load((carpeta / "referencia.yaml").read_text(encoding="utf-8"))

    grupo_propuesto = {i: TRANSVERSAL for i in arquitectura.transversales}
    for servicio in arquitectura.servicios:
        grupo_propuesto.update(dict.fromkeys(servicio.requisitos, servicio.nombre))

    # (grupo en la propuesta, grupo en la referencia) de cada requisito de la referencia hallado.
    pares_de_grupos: list[tuple[str, str]] = []
    usados: set[str] = set()
    for esperado in referencia["requisitos"]:
        frase = _normalizar(esperado["texto"])
        candidato = next(
            (
                r
                for r in modelo.requisitos
                if frase in _normalizar(r.texto) and r.id not in usados and r.id in grupo_propuesto
            ),
            None,
        )
        if candidato is not None:
            usados.add(candidato.id)
            pares_de_grupos.append((grupo_propuesto[candidato.id], esperado["servicio"]))

    juntos_ambos = juntos_propuesta = juntos_referencia = 0
    for (p1, r1), (p2, r2) in combinations(pares_de_grupos, 2):
        juntos_propuesta += p1 == p2
        juntos_referencia += r1 == r2
        juntos_ambos += p1 == p2 and r1 == r2
    precision = _proporcion(juntos_ambos, juntos_propuesta)
    exhaustividad = _proporcion(juntos_ambos, juntos_referencia)
    f1 = (
        round(2 * precision * exhaustividad / (precision + exhaustividad), 3)
        if precision + exhaustividad
        else 0.0
    )

    correspondencia = {}
    for servicio_ref in sorted({r for _, r in pares_de_grupos}):
        destinos = Counter(p for p, r in pares_de_grupos if r == servicio_ref)
        correspondencia[servicio_ref] = destinos.most_common(1)[0][0]

    propuestos = [s.nombre for s in arquitectura.servicios]
    de_referencia = [s["nombre"] for s in referencia.get("servicios", [])]
    return Resultado(
        documento=referencia["documento"],
        servicios_propuestos=propuestos,
        servicios_referencia=de_referencia,
        nombres_coincidentes=sorted(set(propuestos) & set(de_referencia)),
        requisitos_emparejados=len(pares_de_grupos),
        requisitos_referencia=len(referencia["requisitos"]),
        pares_precision=precision,
        pares_exhaustividad=exhaustividad,
        pares_f1=f1,
        correspondencia=correspondencia,
    )


def main(argumentos: list[str] | None = None) -> Resultado:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("arquitectura", type=Path, help="arquitectura.json de la fase 2")
    parser.add_argument("modelo", type=Path, help="modelo_requisitos.json usado para proponerla")
    parser.add_argument("dataset", type=Path, help="carpeta del documento en evaluation/datasets")
    parser.add_argument("--json", type=Path, help="guardar el resultado en este archivo")
    opciones = parser.parse_args(argumentos)

    resultado = evaluar(
        Arquitectura.model_validate_json(opciones.arquitectura.read_bytes()),
        ModeloRequisitos.model_validate_json(opciones.modelo.read_bytes()),
        opciones.dataset,
    )
    if opciones.json:
        opciones.json.write_text(resultado.model_dump_json(indent=2), encoding="utf-8")

    r = resultado
    print(f"Documento {r.documento}")
    print(
        f"  Servicios: {len(r.servicios_propuestos)} propuestos, "
        f"{len(r.servicios_referencia)} en la referencia"
    )
    print(f"    Propuestos:  {', '.join(r.servicios_propuestos)}")
    print(f"    Referencia:  {', '.join(r.servicios_referencia)}")
    print(f"    Coinciden:   {', '.join(r.nombres_coincidentes) or 'ninguno'}")
    print(f"  Requisitos emparejados: {r.requisitos_emparejados}/{r.requisitos_referencia}")
    print(
        f"  Agrupación por pares: precisión {r.pares_precision:.0%}, "
        f"exhaustividad {r.pares_exhaustividad:.0%}, F1 {r.pares_f1:.2f}"
    )
    print("  Correspondencia (referencia -> propuesta):")
    for servicio_ref, propuesto in r.correspondencia.items():
        print(f"    - {servicio_ref} -> {propuesto}")
    return resultado


if __name__ == "__main__":
    main()
