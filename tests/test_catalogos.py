"""Pruebas de los catálogos ASVS, CWE y OWASP API Top 10 y de las referencias entre ellos."""

from pathlib import Path

import pytest

from orchestrator.knowledge.base_conocimiento import (
    ErrorBaseConocimiento,
    cargar_base_conocimiento,
)

CONTROLES = """\
fuente: OWASP ASVS 4.0.3
controles:
  - id: ASVS-V4.1.3
    capitulo: V4 Control de acceso
    seccion: Diseño general
    descripcion: Mínimo privilegio
    niveles: [1, 2, 3]
    cwe: [CWE-285]
"""

CWE = """\
fuente: MITRE CWE
debilidades:
  - id: CWE-285
    nombre: Improper Authorization
    descripcion: Autorización incorrecta
  - id: CWE-20
    nombre: Improper Input Validation
    descripcion: Validación incorrecta
"""

RIESGOS = """\
fuente: OWASP API Security Top 10 2023
riesgos:
  - id: API5:2023
    nombre: Broken Function Level Authorization
    descripcion: Funciones accesibles sin permiso
    cwe: [CWE-285]
    controles: [ASVS-V4.1.3]
"""

DIRECTRIZ = """\
id: sbd.prueba.001
directriz: minimo_privilegio
descripcion: Prueba
aplica_a: [servicio]
practicas: [Una]
controles_asociados: [{control}]
cwe_mitigadas: [{cwe}]
verificacion: [semgrep]
"""


def _base(tmp_path: Path, control="ASVS-V4.1.3", cwe="CWE-20", **reemplazos) -> Path:
    archivos = {
        "controles/asvs.yaml": CONTROLES,
        "vulnerabilidades/cwe.yaml": CWE,
        "vulnerabilidades/owasp_api_top10.yaml": RIESGOS,
        "directrices/minimo_privilegio.yaml": DIRECTRIZ.format(control=control, cwe=cwe),
    }
    archivos.update(reemplazos)
    for nombre, contenido in archivos.items():
        ruta = tmp_path / nombre
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(contenido, encoding="utf-8")
    return tmp_path


def _errores(raiz: Path) -> list[str]:
    with pytest.raises(ErrorBaseConocimiento) as error:
        cargar_base_conocimiento(raiz)
    return error.value.errores


# --- La base real del repositorio --------------------------------------------------------


def test_catalogos_del_repositorio():
    base = cargar_base_conocimiento()

    assert len(base.riesgos_api) == 10
    assert [r.id for r in base.riesgos_api] == [f"API{n}:2023" for n in range(1, 11)]
    assert len(base.controles) >= 20
    assert len(base.debilidades) >= 40


def test_todo_lo_citado_existe_en_los_catalogos():
    base = cargar_base_conocimiento()

    assert base.controles_referenciados() <= {c.id for c in base.controles}
    assert base.cwe_referenciadas() <= {d.id for d in base.debilidades}


def test_no_se_usan_requisitos_eliminados_de_asvs():
    # ASVS 4.0.3 borró V1.4.3 por duplicar a V4.1.3.
    assert "ASVS-V1.4.3" not in cargar_base_conocimiento().controles_referenciados()


def test_cada_riesgo_tiene_cwe_o_control():
    for riesgo in cargar_base_conocimiento().riesgos_api:
        assert riesgo.cwe or riesgo.controles, riesgo.id


# --- Validación de los catálogos ----------------------------------------------------------


def test_base_completa_valida(tmp_path):
    base = cargar_base_conocimiento(_base(tmp_path))

    assert base.resumen()["controles_asvs"] == 1
    assert base.resumen()["debilidades_cwe"] == 2
    assert base.resumen()["riesgos_api_top10"] == 1
    assert base.controles[0].niveles == [1, 2, 3]


def test_control_citado_que_no_esta_en_el_catalogo(tmp_path):
    errores = _errores(_base(tmp_path, control="ASVS-V9.9.9"))
    assert errores == ["el control ASVS-V9.9.9 no está en controles/asvs.yaml"]


def test_cwe_citada_que_no_esta_en_el_catalogo(tmp_path):
    errores = _errores(_base(tmp_path, cwe="CWE-79"))
    assert errores == ["la CWE-79 no está en vulnerabilidades/cwe.yaml"]


def test_cwe_de_un_control_tambien_se_comprueba(tmp_path):
    controles = CONTROLES.replace("cwe: [CWE-285]", "cwe: [CWE-639]")
    errores = _errores(_base(tmp_path, **{"controles/asvs.yaml": controles}))
    assert any("CWE-639" in e for e in errores)


def test_sin_catalogos_no_se_comprueban_referencias(tmp_path):
    raiz = tmp_path
    ruta = raiz / "directrices" / "minimo_privilegio.yaml"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(DIRECTRIZ.format(control="ASVS-V9.9.9", cwe="CWE-79"), encoding="utf-8")

    assert len(cargar_base_conocimiento(raiz).directrices) == 1


@pytest.mark.parametrize(
    ("archivo", "contenido", "esperado"),
    [
        ("controles/asvs.yaml", CONTROLES.replace("niveles: [1, 2, 3]", "niveles: [4]"), "niveles"),
        ("controles/asvs.yaml", CONTROLES.replace("ASVS-V4.1.3", "V4.1.3"), "control"),
        ("controles/asvs.yaml", CONTROLES.replace("fuente: OWASP ASVS 4.0.3\n", ""), "fuente"),
        ("vulnerabilidades/cwe.yaml", CWE.replace("id: CWE-20", "id: CWE20"), "CWE"),
        ("vulnerabilidades/owasp_api_top10.yaml", RIESGOS.replace("API5:2023", "API5"), "riesgo"),
        (
            "vulnerabilidades/owasp_api_top10.yaml",
            RIESGOS.replace("API5:2023", "API11:2023"),
            "riesgo",
        ),
        ("vulnerabilidades/cwe.yaml", "debilidades: [roto", "YAML mal formado"),
    ],
)
def test_catalogos_invalidos(tmp_path, archivo, contenido, esperado):
    errores = _errores(_base(tmp_path, **{archivo: contenido}))
    assert esperado in errores[0]


def test_id_repetido_dentro_del_catalogo(tmp_path):
    repetido = CWE + "  - id: CWE-20\n    nombre: Otra\n    descripcion: Repetida\n"
    errores = _errores(_base(tmp_path, **{"vulnerabilidades/cwe.yaml": repetido}))
    assert "id repetido 'CWE-20'" in errores[0]
