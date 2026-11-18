"""El motor lee el SARIF que genera el conversor de ZAP (dast/zap-a-sarif.mjs)."""

import shutil
import subprocess
from pathlib import Path

import pytest

from orchestrator.gates import Hallazgo, Severidad, leer_sarif

DAST = Path(__file__).parent.parent / "dast"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="requiere Node.js")


@pytest.fixture
def por_regla(tmp_path: Path) -> dict[str, list[Hallazgo]]:
    salida = tmp_path / "zap.sarif"
    subprocess.run(
        [
            "node",
            str(DAST / "zap-a-sarif.mjs"),
            str(DAST / "pruebas" / "zap-ejemplo.json"),
            str(salida),
            str(DAST / "zap-reglas.conf"),
        ],
        check=True,
    )
    agrupados: dict[str, list[Hallazgo]] = {}
    for hallazgo in leer_sarif(salida):
        agrupados.setdefault(hallazgo.regla_id, []).append(hallazgo)
    return agrupados


def test_extrae_herramienta_severidad_cwe_ubicacion_y_huella(por_regla):
    get, post = por_regla["ZAP-40018"]

    assert get.herramienta == "zap"
    assert get.severidad is Severidad.ALTA
    assert get.cwe == ["CWE-89"]
    assert get.archivo == "api/usuarios"
    assert get.mensaje == "SQL Injection: GET /api/usuarios (parámetro orden)"
    assert get.huella.startswith("zap:zapHallazgo/v1:")
    assert get.huella != post.huella


def test_la_regla_fail_llega_como_alta_para_que_opa_bloquee(por_regla):
    (error_500,) = por_regla["ZAP-100000-2"]

    assert error_500.severidad is Severidad.ALTA


def test_respeta_las_severidades_media_y_baja_y_la_cwe_desconocida(por_regla):
    (cookie,) = por_regla["ZAP-10054-1"]
    (tipo,) = por_regla["ZAP-100001"]

    assert cookie.severidad is Severidad.MEDIA
    assert tipo.severidad is Severidad.BAJA
    assert tipo.cwe == []


def test_omite_falsos_positivos_e_informativas(por_regla):
    assert "ZAP-10037" not in por_regla
    assert "ZAP-100000-1" not in por_regla
