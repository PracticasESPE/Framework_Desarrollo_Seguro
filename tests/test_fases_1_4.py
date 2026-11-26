"""Resumen de las fases 1 a 4 con el dataset (evaluation/fases_1_4.py)."""

from __future__ import annotations

import json
from pathlib import Path

import evaluation.fases_1_4 as fases
from evaluation.fases_1_4 import _resumen_fase3, _resumen_fase4, hallazgos_del_gate1, informe
from tests.test_fases_1_2 import _resumen


def _sistema() -> dict:
    def entidad(nombre, logica, intentos, aceptadas=0, descartadas=0, pendientes=()):
        return {
            "nombre": nombre,
            "logica": logica,
            "intentos_logica": intentos,
            "pruebas_aceptadas": aceptadas,
            "pruebas_descartadas": descartadas,
            "pendientes": list(pendientes),
        }

    return {
        "completos": 2,
        "advertencias": ["La entidad «paciente» está en citas, historias"],
        "servicios": [
            {"servicio": "citas", "entidades": [entidad("cita", "aceptada", 1, 9)]},
            {
                "servicio": "historias",
                "entidades": [
                    entidad("historia", "aceptada", 3, 5, 2, ["Validar el médico tratante"]),
                    entidad("paciente", "sin_logica", 3),
                ],
            },
        ],
    }


def test_resumen_de_la_fase_3():
    f3 = _resumen_fase3(_sistema())
    assert f3 == {
        "servicios": 2,
        "completos": 2,
        "entidades": 3,
        "logica_aceptada": 2,
        "logica_al_primer_intento": 1,
        "sin_logica": 1,
        "logica_con_error": 0,
        "pruebas_aceptadas": 14,
        "pruebas_descartadas": 2,
        "pendientes": 1,
        "advertencias": ["La entidad «paciente» está en citas, historias"],
    }


def _sarif(*resultados):
    return {
        "version": "2.1.0",
        "runs": [{"tool": {"driver": {"name": "x"}}, "results": list(resultados)}],
    }


def _resultado(regla, nivel, uri, linea=3):
    return {
        "ruleId": regla,
        "level": nivel,
        "message": {"text": f"Hallazgo de {regla}"},
        "locations": [
            {"physicalLocation": {"artifactLocation": {"uri": uri}, "region": {"startLine": linea}}}
        ],
    }


def test_revision_de_los_hallazgos_por_servicio_y_herramienta(tmp_path: Path, monkeypatch):
    sarif, decisiones = tmp_path / "sarif", tmp_path / "decisiones"
    monkeypatch.setattr(fases, "SARIF_SERVICIOS", sarif)
    monkeypatch.setattr(fases, "DECISIONES", decisiones)
    for servicio in ("citas", "historias"):
        (sarif / servicio).mkdir(parents=True)
        for herramienta in fases.HERRAMIENTAS:
            (sarif / servicio / f"{herramienta}.sarif").write_text(json.dumps(_sarif()), "utf-8")
        (sarif / servicio / "compilacion.txt").write_text("ok", encoding="utf-8")
    (sarif / "historias" / "eslint.sarif").write_text(
        json.dumps(
            _sarif(_resultado("security/detect-object-injection", "warning", "src/h.ts", 8))
        ),
        encoding="utf-8",
    )
    (sarif / "historias" / "hadolint.sarif").unlink()  # la herramienta no terminó
    for servicio, aprobado in (("citas", True), ("historias", False)):
        (decisiones / servicio).mkdir(parents=True)
        decision = {
            "aprobado": aprobado,
            "justificacion": "Gate 1 aprobado" if aprobado else "Gate 1 rechazado",
            "bloqueantes": [] if aprobado else [{"motivo": "La herramienta hadolint no terminó"}],
        }
        (decisiones / servicio / "gate1.json").write_text(
            json.dumps({"decision": decision}), encoding="utf-8"
        )

    revision = hallazgos_del_gate1(["citas", "historias"])

    assert revision["citas"]["aprobado"] is True and revision["citas"]["compila"] is True
    assert revision["citas"]["herramientas"]["semgrep"] == []
    historias = revision["historias"]
    assert historias["bloqueantes"] == ["La herramienta hadolint no terminó"]
    (hallazgo,) = historias["herramientas"]["eslint"]
    assert hallazgo | {"mensaje": ""} == {
        "regla": "security/detect-object-injection",
        "severidad": "media",
        "archivo": "src/h.ts",
        "linea": 8,
        "mensaje": "",
    }
    assert historias["herramientas"]["hadolint"] == "sin resultado (la herramienta no terminó)"

    f4 = _resumen_fase4(revision)
    assert f4 == {"aprobados": 1, "servicios": 2, "hallazgos": 1, "por_severidad": {"media": 1}}


def test_el_informe_resume_las_cuatro_fases():
    resumen = _resumen(
        documento="03_citas_medicas",
        titulo="Citas médicas",
        fase3=_resumen_fase3(_sistema()),
        fase4={"aprobados": 1, "servicios": 2, "hallazgos": 1, "por_severidad": {"media": 1}},
    )
    resumen["pasos"]["sistema"] = {"correcto": True, "segundos": 280.0}
    texto = informe([resumen])

    assert (
        "| 03_citas_medicas | 29/30 | aprobada (intento 2) | 2/2 | 2/3 (1) | "
        "14 (descartadas 2) | 1/2 | 1 |"
    ) in texto
    assert "- Pasos: clasificar 12.5 s, sistema 280.0 s." in texto
    assert "1 entidades sin lógica (para revisión)" in texto
    assert "- Gate 1: 1 hallazgos (1 media)." in texto
    assert "Advertencia de la arquitectura: La entidad «paciente» está en citas, historias" in texto


def test_sin_arquitectura_aprobada_no_genera_servicios(tmp_path: Path, monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        fases,
        "procesar",
        lambda *a, **k: {
            "documento": "x",
            "titulo": "X",
            "pasos": {},
            "ciclo": {"aprobada": False},
        },
    )
    monkeypatch.setattr(fases, "framework", lambda *a, **k: llamadas.append(a) or (0, "", 0.0))
    carpeta = tmp_path / "datos" / "03_citas_medicas"
    (tmp_path / "res" / "03_citas_medicas").mkdir(parents=True)

    resumen = fases.procesar_fases_1_4(carpeta, "docx", False, False, True, tmp_path / "res")

    assert "fase3" not in resumen and llamadas == []
    assert (tmp_path / "res" / "03_citas_medicas" / "resumen.json").is_file()


def test_con_reutilizar_la_fase_3_continua_en_la_carpeta_anterior(tmp_path: Path, monkeypatch):
    """El límite de uso del LLM dejó 4 de 6 servicios sin generar (#75, documento 3)."""
    monkeypatch.setattr(fases, "RAIZ", tmp_path)
    resultados = tmp_path / "res"
    destino = resultados / "03_citas_medicas"
    destino.mkdir(parents=True)
    (destino / "requisitos-docx.arquitectura.json").write_text("{}", encoding="utf-8")
    servicios = tmp_path / "salida" / "servicios" / "eval-03_citas_medicas-20261125-183854"
    (servicios / "especificaciones").mkdir(parents=True)
    sistema = _sistema() | {"completos": 1}
    (servicios / "sistema.json").write_text(json.dumps(sistema), encoding="utf-8")
    (destino / "resumen.json").write_text(
        json.dumps(
            {
                "carpeta_servicios": servicios.relative_to(tmp_path).as_posix(),
                "pasos": {"sistema": {"correcto": False, "segundos": 1905.7}},
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        fases,
        "procesar",
        lambda *a, **k: {"documento": "x", "titulo": "X", "pasos": {}, "ciclo": {"aprobada": True}},
    )
    llamadas = []
    monkeypatch.setattr(
        fases, "framework", lambda *a, **k: llamadas.append(a) or (0, "listo", 600.3)
    )

    carpeta = tmp_path / "datos" / "03_citas_medicas"
    resumen = fases.procesar_fases_1_4(carpeta, "docx", False, True, False, resultados)

    (argumentos,) = llamadas
    assert argumentos[-1] == "--reanudar"
    assert str(servicios.relative_to(tmp_path)) in argumentos
    assert resumen["pasos"]["sistema"] == {"correcto": True, "segundos": 2506.0, "ejecuciones": 2}
    completo = _resumen(
        documento="03_citas_medicas", titulo="Citas médicas", fase3=resumen["fase3"]
    )
    completo["pasos"]["sistema"] = resumen["pasos"]["sistema"]
    assert "sistema 2506.0 s en 2 ejecuciones" in informe([completo])
    assert "--reanudar" in (destino / "fase3.log").read_text(encoding="utf-8")

    # Si ya están todos completos, no se vuelve a generar nada.
    (servicios / "sistema.json").write_text(json.dumps(_sistema()), encoding="utf-8")
    llamadas.clear()
    fases.procesar_fases_1_4(carpeta, "docx", False, True, False, resultados)
    assert llamadas == []


def test_usa_git_bash_en_windows_y_no_el_de_wsl(tmp_path: Path, monkeypatch):
    r"""En Windows, «bash» es el de WSL (C:\Windows\system32): el script necesita Git Bash."""
    git_bash = tmp_path / "Git" / "bin" / "bash.exe"
    git_bash.parent.mkdir(parents=True)
    git_bash.write_text("", encoding="utf-8")
    monkeypatch.setattr(fases.os, "name", "nt")
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    assert fases._bash() == str(git_bash)

    monkeypatch.setattr(fases.os, "name", "posix")
    monkeypatch.setattr(fases.shutil, "which", lambda nombre: "/usr/bin/bash")
    assert fases._bash() == "/usr/bin/bash"


def test_hasta_completar_espera_solo_si_no_hay_avance(tmp_path: Path, monkeypatch):
    estados = iter([(0, 2), (0, 2), (1, 2), (2, 2)])  # inicial, tras intento 1, 2 y 3
    actual = {"v": next(estados)}
    llamadas: list[bool] = []
    esperas: list[float] = []
    monkeypatch.setattr(fases, "_servicios_completos", lambda destino: actual["v"])

    def procesar(carpeta, formato, grafo, reutilizar, con_gate1, resultados):
        llamadas.append(con_gate1)
        if not con_gate1:
            actual["v"] = next(estados)
        return {}

    monkeypatch.setattr(fases, "procesar_fases_1_4", procesar)
    fases.procesar_hasta_completar(
        tmp_path / "doc", "docx", False, True, tmp_path, 8, 30.0, esperas.append
    )
    assert esperas == [1800.0]  # solo el intento 1 no avanzó
    assert llamadas == [False, False, False, True]  # el Gate 1 una vez, al final


def test_hasta_completar_con_todo_completo_no_espera_ni_reintenta(tmp_path: Path, monkeypatch):
    llamadas: list[bool] = []
    monkeypatch.setattr(fases, "_servicios_completos", lambda destino: (6, 6))
    monkeypatch.setattr(fases, "procesar_fases_1_4", lambda *a: llamadas.append(a[4]) or {})
    fases.procesar_hasta_completar(
        tmp_path / "doc", "docx", False, True, tmp_path, 8, 30.0, lambda s: 1 / 0
    )
    assert llamadas == [True]


def test_hasta_completar_se_detiene_tras_los_intentos(tmp_path: Path, monkeypatch):
    esperas: list[float] = []
    monkeypatch.setattr(fases, "_servicios_completos", lambda destino: (1, 2))
    monkeypatch.setattr(fases, "procesar_fases_1_4", lambda *a: {})
    fases.procesar_hasta_completar(
        tmp_path / "doc", "docx", False, False, tmp_path, 3, 1.0, esperas.append
    )
    assert esperas == [60.0, 60.0]  # no espera tras el último intento
