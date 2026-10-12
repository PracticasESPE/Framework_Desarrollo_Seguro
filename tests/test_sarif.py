"""Pruebas del lector SARIF con archivos de ejemplo de las herramientas del Gate 1."""

import json
from pathlib import Path

import pytest

from orchestrator.gates import (
    ErrorSarif,
    Hallazgo,
    Severidad,
    contar_por_severidad,
    convertir_sarif,
    leer_carpeta_sarif,
    leer_sarif,
)

EJEMPLOS = Path(__file__).parent / "datos" / "sarif"


def test_semgrep_extrae_regla_ubicacion_cwe_y_huella():
    hallazgos = leer_sarif(EJEMPLOS / "semgrep.sarif")

    # El tercer resultado está suprimido en el código y no se informa.
    assert len(hallazgos) == 2
    sql, md5 = hallazgos

    assert sql.herramienta == "semgrep oss"
    assert sql.regla_id == "semgrep_rules.nestjs.consulta-sql-concatenada"
    assert sql.severidad is Severidad.ALTA
    assert sql.archivo == "services/usuarios/src/usuarios.service.ts"
    assert (sql.linea_inicio, sql.linea_fin) == (42, 44)
    assert sql.cwe == ["CWE-89"]
    assert sql.huella == "semgrep oss:matchBasedId/v1:9f2c1a7be4d05c33a1b7_0"
    assert "parametrizadas" in sql.mensaje

    assert md5.severidad is Severidad.MEDIA
    assert md5.cwe == ["CWE-327", "CWE-916"]


def test_trivy_asigna_la_severidad_por_puntuacion():
    hallazgos = leer_sarif(EJEMPLOS / "trivy.sarif")

    assert [h.severidad for h in hallazgos] == [
        Severidad.CRITICA,
        Severidad.ALTA,
        Severidad.MEDIA,
        Severidad.BAJA,
    ]
    # El segundo resultado no trae ruleId: se resuelve por ruleIndex.
    assert [h.regla_id for h in hallazgos][1] == "CVE-2026-10002"
    assert all(h.archivo == "services/usuarios/package-lock.json" for h in hallazgos)
    assert len({h.huella for h in hallazgos}) == 4


def test_gitleaks_sin_nivel_y_con_ruta_de_windows():
    (secreto,) = leer_sarif(EJEMPLOS / "gitleaks.sarif")

    assert secreto.herramienta == "gitleaks"
    assert secreto.regla_id == "generic-api-key"
    # Sin nivel en el resultado ni en la regla, la especificación indica "warning".
    assert secreto.severidad is Severidad.MEDIA
    assert secreto.archivo == "services/usuarios/src/config.ts"
    assert secreto.linea_inicio == 5


def test_hadolint_sin_catalogo_de_reglas():
    aviso, nota = leer_sarif(EJEMPLOS / "hadolint.sarif")

    assert aviso.herramienta == "hadolint"
    assert (aviso.regla_id, aviso.severidad) == ("DL3002", Severidad.MEDIA)
    assert (nota.regla_id, nota.severidad) == ("DL3059", Severidad.BAJA)
    assert aviso.archivo == "services/usuarios/Dockerfile"
    assert aviso.cwe == []


def test_la_huella_calculada_es_estable_y_distingue_hallazgos():
    primera = leer_sarif(EJEMPLOS / "hadolint.sarif")
    segunda = leer_sarif(EJEMPLOS / "hadolint.sarif")

    assert [h.huella for h in primera] == [h.huella for h in segunda]
    assert primera[0].huella != primera[1].huella


def test_dos_secretos_del_mismo_commit_tienen_huellas_distintas():
    documento = json.loads((EJEMPLOS / "gitleaks.sarif").read_text(encoding="utf-8"))
    resultados = documento["runs"][0]["results"]
    otro = json.loads(json.dumps(resultados[0]))
    otro["locations"][0]["physicalLocation"]["region"]["startLine"] = 9
    resultados.append(otro)

    primero, segundo = convertir_sarif(documento)
    assert primero.huella != segundo.huella


def test_leer_carpeta_une_todas_las_herramientas():
    hallazgos = leer_carpeta_sarif(EJEMPLOS)

    assert len(hallazgos) == 9
    assert all(isinstance(h, Hallazgo) for h in hallazgos)
    assert {h.herramienta for h in hallazgos} == {"gitleaks", "hadolint", "semgrep oss", "trivy"}
    assert contar_por_severidad(hallazgos) == {
        "critica": 1,
        "alta": 2,
        "media": 4,
        "baja": 2,
        "info": 0,
    }


def test_el_modelo_se_serializa_para_opa():
    (secreto,) = leer_sarif(EJEMPLOS / "gitleaks.sarif")
    datos = json.loads(secreto.model_dump_json())

    assert datos["herramienta"] == "gitleaks"
    assert datos["severidad"] == "media"


def test_resultado_minimo_sin_ubicacion():
    documento = {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "ZAP"}}, "results": [{"message": {"text": "x"}}]}],
    }
    (hallazgo,) = convertir_sarif(documento)

    assert hallazgo.regla_id == "sin-regla"
    assert hallazgo.archivo is None and hallazgo.linea_inicio is None


def test_archivo_sin_resultados():
    documento = {"version": "2.1.0", "runs": [{"tool": {"driver": {"name": "Semgrep"}}}]}
    assert convertir_sarif(documento) == []


@pytest.mark.parametrize(
    ("contenido", "mensaje"),
    [
        ("esto no es json", "JSON válido"),
        ('{"version": "2.1.0"}', "runs"),
        ('{"version": "1.0.0", "runs": []}', "no soportada"),
    ],
)
def test_archivos_invalidos(tmp_path, contenido, mensaje):
    ruta = tmp_path / "malo.sarif"
    ruta.write_text(contenido, encoding="utf-8")
    with pytest.raises(ErrorSarif, match=mensaje):
        leer_sarif(ruta)


def test_archivo_inexistente(tmp_path):
    with pytest.raises(ErrorSarif, match="No se pudo leer"):
        leer_sarif(tmp_path / "no_existe.sarif")
