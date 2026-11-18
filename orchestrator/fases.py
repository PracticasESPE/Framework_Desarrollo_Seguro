"""Catálogo de las fases del pipeline de construcción y validación."""

from pydantic import BaseModel


class Fase(BaseModel):
    numero: int
    nombre: str
    es_gate: bool = False


FASES: tuple[Fase, ...] = (
    Fase(numero=1, nombre="Adquisición de requisitos"),
    Fase(numero=2, nombre="Análisis y propuesta arquitectónica"),
    Fase(numero=3, nombre="Generación de la estructura interna"),
    Fase(numero=4, nombre="Security Gate 1: análisis estático", es_gate=True),
    Fase(numero=5, nombre="Refinamiento iterativo: identificar y priorizar"),
    Fase(numero=6, nombre="Refinamiento iterativo: seleccionar control y refinar"),
    Fase(numero=7, nombre="Integración de microservicios"),
    Fase(numero=8, nombre="Security Gate 2: seguridad de integración", es_gate=True),
    Fase(numero=9, nombre="Pruebas automatizadas"),
    Fase(numero=10, nombre="Contenerización"),
    Fase(numero=11, nombre="DAST y Security Gate 3", es_gate=True),
)


def obtener_fase(numero: int) -> Fase:
    for fase in FASES:
        if fase.numero == numero:
            return fase
    raise ValueError(f"No existe la fase {numero}; las fases válidas van de 1 a {len(FASES)}")
