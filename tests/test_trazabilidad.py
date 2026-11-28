"""Trazabilidad requisito -> componente -> archivo: la parte que no necesita Neo4j.

El registro en Neo4j se prueba con el driver sustituido: lo que importa aquí es qué parámetros
recibe la consulta y qué resumen devuelve, no el comportamiento del motor de base de datos.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from orchestrator.generation import trazabilidad as tz
from orchestrator.generation.trazabilidad import (
    ErrorTrazabilidad,
    archivos_del_servicio,
    enlaces_de_servicios,
    registrar_trazabilidad,
)
from orchestrator.knowledge.registro import ErrorGrafo


def _servicio(nombre: str, requisitos: tuple[str, ...]) -> SimpleNamespace:
    return SimpleNamespace(servicio=nombre, requisitos=requisitos)


def _crear_servicio(raiz, nombre: str, archivos: list[str]) -> None:
    for relativa in archivos:
        ruta = raiz / nombre / relativa
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text("x", encoding="utf-8")


def test_archivos_excluyen_dependencias_y_compilacion(tmp_path) -> None:
    _crear_servicio(
        tmp_path,
        "pagos",
        [
            "src/main.ts",
            "package.json",
            "node_modules/x/index.js",
            "dist/main.js",
            "coverage/lcov.info",
        ],
    )

    archivos = archivos_del_servicio(tmp_path / "pagos")

    assert archivos == ("package.json", "src/main.ts")


def test_archivos_usan_barras_normales(tmp_path) -> None:
    _crear_servicio(tmp_path, "pagos", ["src/dto/crear-pago.dto.ts"])

    assert archivos_del_servicio(tmp_path / "pagos") == ("src/dto/crear-pago.dto.ts",)


def test_enlaces_toman_requisitos_y_archivos_de_cada_servicio(tmp_path) -> None:
    _crear_servicio(tmp_path, "pagos", ["src/main.ts"])
    _crear_servicio(tmp_path, "pedidos", ["src/main.ts", "src/pedido.service.ts"])

    enlaces = enlaces_de_servicios(
        [_servicio("pagos", ("RF-15",)), _servicio("pedidos", ("RF-10", "RF-11"))],
        tmp_path,
    )

    assert [e.servicio for e in enlaces] == ["pagos", "pedidos"]
    assert enlaces[1].requisitos == ("RF-10", "RF-11")
    assert enlaces[1].archivos == ("src/main.ts", "src/pedido.service.ts")


def test_falla_si_falta_la_carpeta_de_un_servicio(tmp_path) -> None:
    _crear_servicio(tmp_path, "pagos", ["src/main.ts"])

    with pytest.raises(ErrorTrazabilidad, match="pedidos"):
        enlaces_de_servicios([_servicio("pedidos", ("RF-10",))], tmp_path)


class _Resultado:
    def __init__(self, records: list[dict] | None = None) -> None:
        self.records = records or []


@pytest.fixture
def registro(monkeypatch):
    """Sustituye la ejecución de consultas: guarda los parámetros de cada una."""
    llamadas: list[dict] = []
    existentes = {"RF-10", "RF-11"}

    def ejecutar(driver, consulta, base_datos, **parametros):
        llamadas.append({"consulta": consulta, "parametros": parametros, "base": base_datos})
        if "RETURN r.id AS id" in consulta:
            return _Resultado([{"id": rid} for rid in existentes])
        return _Resultado()

    monkeypatch.setattr(tz, "existe_ejecucion", lambda driver, eid, base: eid == "ej-1")
    monkeypatch.setattr(tz, "_ejecutar", ejecutar)
    return llamadas


def _enlaces() -> list[tz.EnlaceServicio]:
    return [
        tz.EnlaceServicio(
            servicio="pedidos",
            carpeta="services/pedidos",
            requisitos=("RF-10", "RF-99"),
            archivos=("src/main.ts", "package.json"),
        ),
        tz.EnlaceServicio(
            servicio="pagos",
            carpeta="services/pagos",
            requisitos=("RF-11",),
            archivos=("src/main.ts",),
        ),
    ]


def test_registro_envia_servicios_archivos_y_requisitos(registro) -> None:
    resumen = registrar_trazabilidad(object(), "ej-1", _enlaces(), base_datos="neo4j")

    escritura = registro[-1]
    servicios = escritura["parametros"]["servicios"]
    assert escritura["parametros"]["ejecucion_id"] == "ej-1"
    assert escritura["base"] == "neo4j"
    assert servicios[0]["servicio"] == "pedidos"
    assert servicios[0]["requisitos"] == ["RF-10", "RF-99"]
    assert servicios[0]["archivos"] == ["src/main.ts", "package.json"]
    assert "IMPLEMENTA_EN" in escritura["consulta"]
    assert "CONTIENE" in escritura["consulta"]
    assert "Archivo" in escritura["consulta"]

    assert resumen.servicios == 2
    assert resumen.archivos == 3
    assert resumen.requisitos_enlazados == 2
    assert resumen.requisitos_sin_nodo == ["RF-99"]


def test_registro_falla_si_no_existe_la_ejecucion(registro) -> None:
    with pytest.raises(ErrorGrafo, match="ej-2"):
        registrar_trazabilidad(object(), "ej-2", _enlaces())

    assert registro == []
