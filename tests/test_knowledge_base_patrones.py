import re
from pathlib import Path

import pytest
import yaml

RUTA = Path(__file__).resolve().parent.parent / "knowledge_base" / "patrones"
OBLIGATORIOS = {
    "id",
    "patron",
    "descripcion",
    "aplica_cuando",
    "controles_asociados",
    "cwe_mitigadas",
    "implementacion",
}
ARCHIVOS = sorted(RUTA.glob("*.yaml"))


def test_hay_patrones():
    assert len(ARCHIVOS) >= 6


@pytest.mark.parametrize("archivo", ARCHIVOS, ids=lambda p: p.name)
def test_estructura_del_patron(archivo):
    datos = yaml.safe_load(archivo.read_text(encoding="utf-8"))
    assert OBLIGATORIOS <= set(datos), f"faltan campos en {archivo.name}"
    assert re.fullmatch(r"arq\.[a-z_]+\.\d{3}", datos["id"])
    assert datos["patron"] == archivo.stem
    assert all(re.fullmatch(r"CWE-\d+", c) for c in datos["cwe_mitigadas"])
    assert all(re.fullmatch(r"ASVS-V\d+\.\d+\.\d+", c) for c in datos["controles_asociados"])
    for cond in datos["aplica_cuando"]:
        assert set(cond) <= {"etiqueta", "numero_servicios_minimo"}


def test_ids_unicos():
    ids = [yaml.safe_load(a.read_text(encoding="utf-8"))["id"] for a in ARCHIVOS]
    assert len(ids) == len(set(ids))
