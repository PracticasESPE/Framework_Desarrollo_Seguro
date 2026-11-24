"""Gate 1 sobre los servicios generados (#71).

scripts/gate1-servicios.sh ejecuta las herramientas (en CI, job `gate1-servicios`); aquí se prueba
lo que hace el motor con sus resultados: la preparación de los SARIF para GitHub
(orchestrator/gates/sarif_servicio.py) y la decisión de OPA de cada servicio
(orchestrator/gates/servicios.py y `framework gates servicios`). Las que llaman a OPA se saltan
sin el ejecutable `opa`.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.gates.decision import HERRAMIENTAS, construir_entrada
from orchestrator.gates.sarif_servicio import preparar, preparar_carpeta, ruta_en_el_repositorio
from orchestrator.gates.servicios import (
    HERRAMIENTAS_DE_SERVICIO,
    compilo,
    decidir_servicios,
    resumen_markdown,
)

RAIZ = Path(__file__).resolve().parents[1]
runner = CliRunner()
con_opa = pytest.mark.skipif(shutil.which("opa") is None, reason="Requiere el ejecutable opa")
SERVICIO = "salida/servicios/pedidos"


def _sarif(herramienta: str, *resultados: dict) -> dict:
    return {
        "version": "2.1.0",
        "runs": [
            {"tool": {"driver": {"name": herramienta, "rules": []}}, "results": list(resultados)}
        ],
    }


def _resultado(regla: str, nivel: str, uri: str, base: str | None = None) -> dict:
    artefacto = {"uri": uri} | ({"uriBaseId": base} if base else {})
    return {
        "ruleId": regla,
        "level": nivel,
        "message": {"text": f"Hallazgo de {regla}"},
        "locations": [
            {"physicalLocation": {"artifactLocation": artefacto, "region": {"startLine": 3}}}
        ],
    }


def _servicio(carpeta: Path, nombre: str, compila: bool = True, **extra: dict) -> Path:
    """Una carpeta de SARIF de un servicio: todas las herramientas limpias salvo `extra`."""
    destino = carpeta / nombre
    destino.mkdir(parents=True)
    archivos = HERRAMIENTAS[1] | HERRAMIENTAS_DE_SERVICIO
    for archivo in archivos:
        documento = extra.get(archivo.removesuffix(".sarif").replace("-", "_"), _sarif(archivo))
        (destino / archivo).write_text(json.dumps(documento), encoding="utf-8")
    (destino / "compilacion.txt").write_text("ok" if compila else "error", encoding="utf-8")
    return destino


# --- SARIF para GitHub -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("uri", "esperada"),
    [
        ("package-lock.json", f"{SERVICIO}/package-lock.json"),  # Trivy: relativa a lo analizado
        (f"/src/{SERVICIO}/src/a.ts", f"{SERVICIO}/src/a.ts"),  # montaje de Semgrep
        (f"file:///work/{SERVICIO}/Dockerfile", f"{SERVICIO}/Dockerfile"),
        (f"{SERVICIO}/src/b.ts", f"{SERVICIO}/src/b.ts"),  # ya relativa a la raíz
        ("./src/c.ts", f"{SERVICIO}/src/c.ts"),
        (f"/tmp/x/{SERVICIO}/src/d.ts", f"{SERVICIO}/src/d.ts"),  # ruta absoluta del sistema
        ("src\\e.ts", f"{SERVICIO}/src/e.ts"),  # Windows
    ],
)
def test_las_rutas_quedan_relativas_a_la_raiz_del_repositorio(uri: str, esperada: str):
    assert ruta_en_el_repositorio(uri, SERVICIO) == esperada


def test_cada_ejecucion_recibe_su_categoria_y_pierde_las_bases_de_rutas():
    documento = _sarif("Trivy", _resultado("CVE-1", "error", "package-lock.json", "ROOTPATH"))
    documento["runs"][0]["originalUriBaseIds"] = {"ROOTPATH": {"uri": "file:///servicio/"}}

    assert preparar(documento, SERVICIO, "pedidos", "trivy-fs") == 1

    ejecucion = documento["runs"][0]
    assert ejecucion["automationDetails"] == {"id": "gate1/pedidos/trivy-fs/"}
    assert "originalUriBaseIds" not in ejecucion
    artefacto = ejecucion["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]
    assert artefacto == {"uri": f"{SERVICIO}/package-lock.json"}


def test_varias_ejecuciones_tienen_categorias_distintas():
    documento = _sarif("Gitleaks")
    documento["runs"].append(_sarif("Gitleaks")["runs"][0])
    preparar(documento, SERVICIO, "pedidos", "gitleaks")
    ids = [r["automationDetails"]["id"] for r in documento["runs"]]
    assert ids == ["gate1/pedidos/gitleaks-1/", "gate1/pedidos/gitleaks-2/"]


def test_la_carpeta_de_un_servicio_se_copia_plana_para_una_sola_subida(tmp_path: Path):
    carpeta = _servicio(tmp_path / "sarif", "pedidos")
    publicar = tmp_path / "github"
    preparar_carpeta(carpeta, SERVICIO, "pedidos", publicar)
    _servicio(tmp_path / "sarif", "historia_clinica")
    preparar_carpeta(
        tmp_path / "sarif" / "historia_clinica",
        "salida/servicios/historia_clinica",
        "historia_clinica",
        publicar,
    )

    publicados = sorted(p.name for p in publicar.iterdir())
    assert len(publicados) == 12 and "pedidos-semgrep.sarif" in publicados
    # GitHub rechaza dos SARIF con la misma herramienta y categoría: todas son distintas.
    categorias = [
        json.loads(p.read_text(encoding="utf-8"))["runs"][0]["automationDetails"]["id"]
        for p in publicar.iterdir()
    ]
    assert len(set(categorias)) == len(categorias) == 12


# --- Decisión de OPA por servicio --------------------------------------------------------------


def test_eslint_cuenta_como_herramienta_del_servicio(tmp_path: Path):
    carpeta = _servicio(
        tmp_path,
        "pedidos",
        eslint=_sarif(
            "ESLint",
            _resultado("security/detect-eval-with-expression", "error", f"{SERVICIO}/src/a.ts"),
        ),
    )
    datos = construir_entrada(1, tmp_path, carpeta, True, HERRAMIENTAS_DE_SERVICIO).datos
    assert {h["nombre"] for h in datos["herramientas"]} == {
        "semgrep",
        "gitleaks",
        "trivy fs",
        "trivy config",
        "hadolint",
        "eslint",
    }
    (hallazgo,) = datos["hallazgos"]
    assert (hallazgo["herramienta"], hallazgo["severidad"]) == ("eslint", "alta")
    # En el servicio de referencia, ESLint no forma parte de la entrada.
    assert "eslint" not in {
        h["nombre"] for h in construir_entrada(1, tmp_path, carpeta).datos["herramientas"]
    }


def test_sin_resultado_de_tsc_se_asume_que_no_compila(tmp_path: Path):
    carpeta = _servicio(tmp_path, "pedidos")
    assert compilo(carpeta)
    (carpeta / "compilacion.txt").unlink()
    assert not compilo(carpeta)


@con_opa
def test_decide_cada_servicio_por_separado(tmp_path: Path):
    sarif = tmp_path / "sarif"
    _servicio(sarif, "pedidos")
    _servicio(
        sarif,
        "historia_clinica",
        semgrep=_sarif(
            "Semgrep", _resultado("javascript.express.security.audit.xss", "error", "src/x.ts")
        ),
        trivy_fs=_sarif("Trivy", _resultado("CVE-2026-1", "warning", "package-lock.json")),
    )
    _servicio(sarif, "notas", compila=False)
    (sarif / "notas" / "hadolint.sarif").unlink()  # la herramienta no terminó

    decisiones = {d.servicio: d for d in decidir_servicios(sarif, tmp_path)}

    assert decisiones["pedidos"].decision.aprobado
    historia = decisiones["historia_clinica"].decision
    assert not historia.aprobado
    assert [b.regla for b in historia.bloqueantes] == ["gate1.severidad"]
    assert historia.conteo.get("media") == 1  # la media no bloquea: es advertencia
    notas = decisiones["notas"].decision
    assert {b.regla for b in notas.bloqueantes} == {"gate1.compilacion", "gate1.herramienta_caida"}
    # Cada decisión va a su carpeta; la del servicio de referencia no se toca.
    guardada = json.loads(
        (tmp_path / "gates" / "servicios" / "pedidos" / "gate1.json").read_text("utf-8")
    )
    assert guardada["servicio"] == "pedidos" and guardada["decision"]["aprobado"] is True
    assert not (tmp_path / "gates" / "gate1.json").exists()

    resumen = resumen_markdown(list(decisiones.values()))
    assert "| pedidos | aprobado | 0/0/0/0 | - |" in resumen
    assert "| historia_clinica | **rechazado** | 0/1/1/0 |" in resumen
    assert "1 de 3 servicios aprobados." in resumen


@con_opa
def test_cli_gates_servicios(tmp_path: Path):
    sarif = tmp_path / "sarif"
    _servicio(sarif, "pedidos")
    _servicio(sarif, "historia_clinica", compila=False)
    argumentos = ["gates", "servicios", "--sarif", str(sarif), "--salida", str(tmp_path)]

    resultado = runner.invoke(app, argumentos)
    assert resultado.exit_code == 1, resultado.output
    assert "Gate 1 de pedidos: APROBADO" in resultado.output
    assert "Gate 1 de historia_clinica: RECHAZADO" in resultado.output
    assert "1 de 2 servicios aprobados; rechazados: historia_clinica" in resultado.output

    assert runner.invoke(app, [*argumentos, "--no-bloquear"]).exit_code == 0


def test_cli_gates_servicios_sin_sarif(tmp_path: Path):
    resultado = runner.invoke(app, ["gates", "servicios", "--sarif", str(tmp_path / "nada")])
    assert resultado.exit_code == 1
    assert "ejecuta antes scripts/gate1-servicios.sh" in resultado.output


# --- El script y la configuración --------------------------------------------------------------


def _imagenes(script: str) -> dict[str, str]:
    texto = (RAIZ / "scripts" / script).read_text(encoding="utf-8")
    return dict(re.findall(r"^(SEMGREP|GITLEAKS|TRIVY_IMG|HADOLINT)=(\S+)", texto, flags=re.M))


def test_las_herramientas_son_las_mismas_versiones_que_el_gate1():
    assert _imagenes("gate1-servicios.sh") == _imagenes("gate1.sh")
    assert len(_imagenes("gate1.sh")) == 4


def test_el_script_analiza_el_codigo_generado_aunque_no_este_en_git():
    script = (RAIZ / "scripts" / "gate1-servicios.sh").read_text(encoding="utf-8")
    assert "--no-git-ignore" in script  # sin la opción, Semgrep no ve salida/ (ignorada por Git)
    assert "dir --no-banner" in script  # Gitleaks sobre la carpeta, no sobre el historial
    assert '"$RAIZ/scripts/gitleaks-servicios.toml:/gitleaks.toml:ro"' in script
    # Cada contenedor monta solo lo que analiza, nunca el repositorio entero.
    assert '"$RAIZ:/' not in script and "'$RAIZ:/" not in script
    assert '-v "$RAIZ/$dir:/servicio:ro"' in script
    assert "--config '$RAIZ_NODE/eslint/eslint.config.mjs'" in script


def test_eslint_del_framework_con_versiones_exactas_y_las_reglas_de_seguridad():
    paquete = json.loads((RAIZ / "eslint" / "package.json").read_text(encoding="utf-8"))
    for nombre, version in paquete["devDependencies"].items():
        assert re.fullmatch(r"\d+\.\d+\.\d+", version), f"{nombre} sin versión exacta"
    configuracion = (RAIZ / "eslint" / "eslint.config.mjs").read_text(encoding="utf-8")
    assert "pluginSecurity.configs.recommended" in configuracion
    assert "tseslint.configs.recommendedTypeChecked" in configuracion
    assert (RAIZ / "eslint" / "package-lock.json").is_file()


# --- Ajustes de la plantilla según el Gate 1 (#73) ---------------------------------------------


def test_la_plantilla_no_repite_los_hallazgos_del_gate1(tmp_path: Path):
    """objeto[variable] pasó a un switch y a un Map (detect-object-injection)."""
    from orchestrator.generation import RUTA_PLANTILLA, generar_servicio, leer_especificacion

    carpeta = generar_servicio(
        leer_especificacion(RUTA_PLANTILLA / "ejemplos" / "pedidos.yml"), tmp_path
    )
    entorno = (carpeta / "src" / "configuracion" / "entorno.ts").read_text(encoding="utf-8")
    assert "REGISTRO[" not in entorno and "switch (nombre)" in entorno
    filtro = (carpeta / "src" / "seguridad" / "filtro-errores.ts").read_text(encoding="utf-8")
    assert "STATUS_CODES[" not in filtro
    assert "new Map(Object.entries(STATUS_CODES))" in filtro


def test_el_falso_positivo_del_generador_del_contrato_esta_acotado(tmp_path: Path):
    """La regla se desactiva solo en las dos escrituras, con motivo, y la ruta se valida."""
    from orchestrator.generation import RUTA_PLANTILLA, generar_servicio, leer_especificacion

    carpeta = generar_servicio(
        leer_especificacion(RUTA_PLANTILLA / "ejemplos" / "pedidos.yml"), tmp_path
    )
    texto = (carpeta / "src" / "openapi" / "generar-openapi.ts").read_text(encoding="utf-8")
    desactivacion = (
        "eslint-disable-next-line security/detect-non-literal-fs-filename"
        " -- ruta del pipeline, validada"
    )
    assert re.findall(r"eslint-disable[^\n]*", texto) == [desactivacion, desactivacion]
    assert "const destino = validarDestino(ruta);" in texto
    assert "ruta.endsWith('.json')" in texto
    # Ningún otro archivo generado desactiva reglas.
    otros = [
        p.relative_to(carpeta).as_posix()
        for p in carpeta.rglob("*.ts")
        if "eslint-disable" in p.read_text(encoding="utf-8") and p.name != "generar-openapi.ts"
    ]
    assert otros == []


def test_la_ejecucion_de_codigo_dinamico_bloquea_el_gate1():
    """Lo que el generador de lógica prohíbe al LLM es un error en Semgrep y en ESLint."""
    import yaml

    reglas = yaml.safe_load((RAIZ / "semgrep_rules" / "nestjs-seguridad.yaml").read_text("utf-8"))
    regla = next(r for r in reglas["rules"] if r["id"] == "ejecucion-de-codigo-dinamico")
    assert regla["severity"] == "ERROR"
    patrones = {p["pattern"] for p in regla["pattern-either"]}
    assert {"eval(...)", "new Function(...)", 'require("child_process")'} <= patrones
    casos = (RAIZ / "semgrep_rules" / "nestjs-seguridad.ts").read_text(encoding="utf-8")
    assert casos.count("// ruleid: ejecucion-de-codigo-dinamico") == 6

    configuracion = (RAIZ / "eslint" / "eslint.config.mjs").read_text(encoding="utf-8")
    for regla_eslint in (
        "no-eval",
        "no-new-func",
        "security/detect-eval-with-expression",
        "security/detect-child-process",
        "security/detect-non-literal-require",
    ):
        assert f"'{regla_eslint}': 'error'" in configuracion
