"""Ciclo LLM ↔ OPA de la fase 2, versión de demostración. TEMPORAL: lo reemplaza la #58.

Qué hace (plan técnico 7.2, pasos 2 y 3):

    arquitectura.json ──► OPA valida ──► ¿aprobada? ── sí ──► se guarda y termina
                              ▲               │
                              │               no
                              │               ▼
                    el LLM propone otra ◄── motivos del rechazo
                    con esos motivos          (p. ej. «Dependencias circulares entre…»)

Como mucho 3 intentos. Si OPA no aprueba ninguna propuesta, queda para revisión humana.

Uso, desde la carpeta del proyecto, con el id del documento cargado en el dashboard:

    python -m uv run python scripts/demo/ciclo_llm_opa.py <id del documento>

Lee `salida/arquitectura/<id>.arquitectura.json` y `salida/requisitos/<id>.modelo_requisitos.json`
(los que dejan «arquitectura proponer» y la fase 1) y, si OPA aprueba, guarda la arquitectura
aprobada en el mismo archivo. Después se generan los ADR con «arquitectura adr».

Por qué no basta con repetir «arquitectura proponer»: con la caché del LLM, la misma pregunta da la
misma respuesta. Lo que hace cambiar la propuesta es pasarle al LLM los motivos del rechazo
(`retroalimentacion`), y eso hace este ciclo.

Para la #58 (Marcelo), lo que esta versión NO hace y la definitiva debería hacer:
- Estar dentro del flujo: que «arquitectura proponer» (y la ejecución de la API) valide con OPA y
  reintente sola, sin un script aparte.
- Registrar cada intento con su motivo de rechazo (evidencia de la #58: «Registro de intentos»).
- Guardar las decisiones aprobadas como nodos Decision en Neo4j, enlazadas a sus requisitos y a
  las reglas de OPA, y registrar el rechazo final como Decision cuando no converge (riesgo de la
  planificación del sprint 3).
- Pruebas propias. La de este script (tests/test_ciclo_llm_opa.py) solo comprueba el ciclo con
  dobles de prueba.

Todo lo que usa ya existe: `validar_arquitectura` (#196) y `proponer_arquitectura` con
`retroalimentacion` (#194).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ) not in sys.path:
    # Para ejecutarlo como script sin PYTHONPATH: el paquete orchestrator está en la raíz.
    sys.path.insert(0, str(RAIZ))

from orchestrator.architecture import (  # noqa: E402
    Arquitectura,
    DecisionArquitectura,
    proponer_arquitectura,
    validar_arquitectura,
)
from orchestrator.ingest import ModeloRequisitos  # noqa: E402
from orchestrator.llm import ProveedorLLM  # noqa: E402

INTENTOS = 3


@dataclass
class Intento:
    numero: int
    arquitectura: Arquitectura
    decision: DecisionArquitectura


def ciclo_llm_opa(
    arquitectura: Arquitectura,
    modelo: ModeloRequisitos,
    llm: ProveedorLLM,
    intentos: int = INTENTOS,
    al_intento: Callable[[Intento], None] | None = None,
    validar: Callable[[Arquitectura], DecisionArquitectura] = validar_arquitectura,
    proponer: Callable[..., Arquitectura] = proponer_arquitectura,
) -> list[Intento]:
    """Valida con OPA y, si rechaza, pide al LLM otra propuesta con los motivos.

    Devuelve todos los intentos; el último es el aprobado o el último rechazado.
    """
    historial: list[Intento] = []
    for numero in range(1, intentos + 1):
        intento = Intento(numero, arquitectura, validar(arquitectura))
        historial.append(intento)
        if al_intento is not None:
            al_intento(intento)
        if intento.decision.aprobado or numero == intentos:
            break
        arquitectura = proponer(modelo, llm, retroalimentacion=intento.decision.retroalimentacion())
    return historial


def _mostrar(intento: Intento) -> None:
    print(f"Intento {intento.numero}: {intento.decision.justificacion}")
    for servicio in intento.arquitectura.servicios:
        dependencias = ", ".join(f"{d.servicio} ({d.tipo})" for d in servicio.depende_de)
        print(f"    {servicio.nombre}: depende de {dependencias or 'ninguna'}")
    for bloqueante in intento.decision.bloqueantes:
        print(f"  OPA rechaza: {bloqueante.motivo}")


def main(argumentos: list[str]) -> int:
    from orchestrator.config import obtener_configuracion
    from orchestrator.llm import ErrorLLM, crear_proveedor, describir_uso
    from orchestrator.opa import ErrorOPA

    if len(argumentos) != 1:
        print("Uso: python scripts/demo/ciclo_llm_opa.py <id del documento>", file=sys.stderr)
        return 2
    documento = argumentos[0]
    salida = obtener_configuracion().directorio_salida
    archivo = salida / "arquitectura" / f"{documento}.arquitectura.json"
    requisitos = salida / "requisitos" / f"{documento}.modelo_requisitos.json"
    try:
        arquitectura = Arquitectura.model_validate_json(archivo.read_bytes())
        modelo = ModeloRequisitos.model_validate_json(requisitos.read_bytes())
    except OSError as error:
        print(
            f"No se pudo leer {error.filename}: ¿ejecutaste «arquitectura proponer»?",
            file=sys.stderr,
        )
        return 1

    try:
        llm = crear_proveedor()
        historial = ciclo_llm_opa(arquitectura, modelo, llm, al_intento=_mostrar)
    except (ErrorLLM, ErrorOPA, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    final = historial[-1]
    print(f"Uso del LLM: {describir_uso(llm)}")
    if not final.decision.aprobado:
        print(f"OPA no aprobó ninguna propuesta en {len(historial)} intentos: revisión humana.")
        return 1
    archivo.write_text(final.arquitectura.model_dump_json(indent=2), encoding="utf-8")
    print(f"Arquitectura aprobada en el intento {final.numero}; guardada en {archivo.as_posix()}")
    print("Siguiente paso: «arquitectura adr» con este archivo.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
