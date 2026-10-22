"""Pruebas del validador de la base de conocimiento y de las directrices Secure by Design."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.knowledge.base_conocimiento import (
    RAIZ_POR_DEFECTO,
    ErrorBaseConocimiento,
    cargar_base_conocimiento,
)

DIRECTRICES_DEL_PLAN = {
    "minimo_privilegio",
    "defensa_en_profundidad",
    "validacion_entrada",
    "fallo_seguro",
}

DIRECTRIZ_VALIDA = """\
id: sbd.prueba.001
directriz: {nombre}
descripcion: Directriz de prueba
aplica_a: [servicio]
practicas: [Una práctica]
controles_asociados: [ASVS-V1.1.1]
cwe_mitigadas: [CWE-20]
verificacion: [semgrep]
"""

PATRON_VALIDO = """\
id: arq.prueba.001
patron: {nombre}
descripcion: Patrón de prueba
aplica_cuando:
  - etiqueta: punto_unico_acceso
  - numero_servicios_minimo: 2
controles_asociados: [ASVS-V4.1.1]
cwe_mitigadas: [CWE-284]
implementacion: traefik
"""


def _escribir(raiz: Path, carpeta: str, nombre: str, contenido: str) -> None:
    destino = raiz / carpeta
    destino.mkdir(parents=True, exist_ok=True)
    (destino / f"{nombre}.yaml").write_text(contenido, encoding="utf-8")


def test_la_base_del_repositorio_es_valida():
    base = cargar_base_conocimiento()

    nombres = {d.directriz for d in base.directrices}
    assert DIRECTRICES_DEL_PLAN <= nombres
    assert len(base.directrices) >= 6
    assert all(d.id.startswith("sbd.") for d in base.directrices)


def test_cada_directriz_se_puede_verificar():
    for directriz in cargar_base_conocimiento().directrices:
        assert directriz.practicas and directriz.verificacion, directriz.directriz


def test_base_valida_con_patrones_y_directrices(tmp_path):
    _escribir(
        tmp_path,
        "directrices",
        "minimo_privilegio",
        DIRECTRIZ_VALIDA.format(nombre="minimo_privilegio"),
    )
    _escribir(tmp_path, "patrones", "api_gateway", PATRON_VALIDO.format(nombre="api_gateway"))

    base = cargar_base_conocimiento(tmp_path)

    assert base.resumen() == {
        "patrones": 1,
        "directrices": 1,
        "controles_asvs": 0,
        "debilidades_cwe": 0,
        "riesgos_api_top10": 0,
        "controles_referenciados": 2,
        "cwe_referenciadas": 2,
    }
    assert base.patrones[0].aplica_cuando[1].numero_servicios_minimo == 2


def test_carpetas_vacias_no_son_error(tmp_path):
    assert cargar_base_conocimiento(tmp_path).resumen()["directrices"] == 0


@pytest.mark.parametrize(
    ("contenido", "esperado"),
    [
        (DIRECTRIZ_VALIDA.replace("CWE-20", "cwe20"), "CWE con formato inválido"),
        (DIRECTRIZ_VALIDA.replace("ASVS-V1.1.1", "V1.1"), "control con formato inválido"),
        (DIRECTRIZ_VALIDA.replace("sbd.prueba.001", "prueba-1"), "id de directriz inválido"),
        (DIRECTRIZ_VALIDA.replace("[servicio]", "[nube]"), "aplica_a"),
        (DIRECTRIZ_VALIDA.replace("practicas: [Una práctica]", "practicas: []"), "practicas"),
        (DIRECTRIZ_VALIDA + "campo_extra: 1\n", "campo_extra"),
        ("id: [sin cerrar\n", "YAML mal formado"),
    ],
)
def test_errores_de_directriz(tmp_path, contenido, esperado):
    _escribir(tmp_path, "directrices", "fallo_seguro", contenido.format(nombre="fallo_seguro"))

    with pytest.raises(ErrorBaseConocimiento) as error:
        cargar_base_conocimiento(tmp_path)
    assert esperado in error.value.errores[0]


def test_el_nombre_del_archivo_debe_coincidir(tmp_path):
    _escribir(tmp_path, "directrices", "fallo_seguro", DIRECTRIZ_VALIDA.format(nombre="otro"))

    with pytest.raises(ErrorBaseConocimiento) as error:
        cargar_base_conocimiento(tmp_path)
    assert "debe ser 'fallo_seguro'" in error.value.errores[0]


def test_condicion_de_patron_con_dos_criterios(tmp_path):
    contenido = PATRON_VALIDO.replace(
        "  - numero_servicios_minimo: 2",
        "  - etiqueta: x\n    numero_servicios_minimo: 2",
    )
    _escribir(tmp_path, "patrones", "saga", contenido.format(nombre="saga"))

    with pytest.raises(ErrorBaseConocimiento) as error:
        cargar_base_conocimiento(tmp_path)
    assert "no ambas" in error.value.errores[0]


def test_ids_repetidos_entre_archivos(tmp_path):
    _escribir(
        tmp_path, "directrices", "fallo_seguro", DIRECTRIZ_VALIDA.format(nombre="fallo_seguro")
    )
    _escribir(
        tmp_path,
        "directrices",
        "seguro_por_defecto",
        DIRECTRIZ_VALIDA.format(nombre="seguro_por_defecto"),
    )

    with pytest.raises(ErrorBaseConocimiento) as error:
        cargar_base_conocimiento(tmp_path)
    assert "id repetido" in error.value.errores[0]


def test_reune_todos_los_errores(tmp_path):
    _escribir(tmp_path, "directrices", "a", "id: [roto\n")
    _escribir(tmp_path, "directrices", "b", DIRECTRIZ_VALIDA.format(nombre="otro"))

    with pytest.raises(ErrorBaseConocimiento) as error:
        cargar_base_conocimiento(tmp_path)
    assert len(error.value.errores) == 2


def test_comando_validar():
    resultado = CliRunner().invoke(app, ["conocimiento", "validar"])

    assert resultado.exit_code == 0
    assert "Base de conocimiento válida" in resultado.output
    assert "directrices:" in resultado.output


def test_comando_validar_con_errores(tmp_path):
    _escribir(tmp_path, "directrices", "fallo_seguro", "id: [roto\n")
    resultado = CliRunner().invoke(app, ["conocimiento", "validar", "--raiz", str(tmp_path)])

    assert resultado.exit_code == 1
    assert "inválida" in resultado.output


def test_la_raiz_por_defecto_es_la_del_repositorio():
    assert RAIZ_POR_DEFECTO.name == "knowledge_base"
    assert (RAIZ_POR_DEFECTO / "directrices").is_dir()
