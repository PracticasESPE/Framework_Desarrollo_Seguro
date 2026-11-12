"""Diagrama C4 en Mermaid (docs/arquitectura.md) a partir de arquitectura.json y la decisión de OPA.

La sintaxis de los diagramas se comprobó dibujándolos con Mermaid 11 y 12; aquí se prueba lo que
genera el motor: qué piezas aparecen, cómo se escapa el texto del LLM y que no se pise un archivo
ajeno. La prueba de la CLI, que valida con OPA de verdad, se salta si no está instalado.
"""

import re
import shutil
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from orchestrator.architecture.adr import MARCA, construir_adrs
from orchestrator.architecture.c4 import (
    ErrorDiagrama,
    actores,
    diagrama_contenedores,
    diagrama_contexto,
    documento_arquitectura,
    enlaces_adr,
    escribir_documento,
    texto_mermaid,
)
from orchestrator.architecture.validacion import PatronInferido
from orchestrator.cli import app
from tests.test_adr import _arquitectura, _decision
from tests.test_arquitectura import _modelo, _servicio

runner = CliRunner()
FECHA = date(2026, 11, 12)
con_opa = pytest.mark.skipif(shutil.which("opa") is None, reason="Requiere el ejecutable opa")


def _sin_gateway():
    return _decision(
        patrones=[
            PatronInferido(
                id="arq.basedatos.001",
                patron="database_per_service",
                implementacion="postgresql",
                controles=["ASVS-V1.4.1"],
                cwe=["CWE-284"],
                por=["autonomia_de_datos"],
                motivo="Cada servicio tiene su propia base de datos",
            )
        ]
    )


# --- Texto no confiable --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ataque",
    [
        'cierra la cadena") \nclick s_usuarios "javascript:alert(1)"',
        "<script>alert(1)</script> e <img src=x onerror=alert(1)>",
        "rompe la flecha | y la etiqueta",
        "entidad #quot; y otra sentencia; graph",
    ],
)
def test_texto_mermaid_no_puede_salir_de_la_etiqueta(ataque):
    limpio = texto_mermaid(ataque)
    assert "\n" not in limpio and '"' not in limpio
    assert not re.search(r"[<>|#;`\\]", limpio)


def test_texto_mermaid_recorta():
    assert texto_mermaid("a" * 200, 20) == "a" * 19 + "…"


def test_una_responsabilidad_maliciosa_no_rompe_el_diagrama():
    servicio = _servicio("usuarios", ["RF-01"])
    servicio["responsabilidad"] = 'Gestiona cuentas") \nclick s_usuarios "javascript:alert(1)"'
    arquitectura = _arquitectura(
        servicios=[
            servicio,
            _servicio("pedidos", ["RF-02"], [("usuarios", "sincrona")]),
            _servicio("notificaciones", ["RF-03"], [("pedidos", "asincrona")]),
        ]
    )
    diagrama = diagrama_contenedores(arquitectura, _decision())
    for linea in diagrama.splitlines():
        assert linea.count('"') % 2 == 0, linea  # ninguna cadena queda abierta
    assert not any(linea.strip().startswith("click") for linea in diagrama.splitlines())
    # El texto del ataque queda como texto dentro de la etiqueta de su propia caja.
    (linea,) = [linea for linea in diagrama.splitlines() if "javascript" in linea]
    assert linea.strip().startswith('s_usuarios["<b>usuarios</b><br/>[NestJS]<br/>')


# --- Contexto ------------------------------------------------------------------------------------


def test_los_actores_salen_de_los_requisitos_sin_el_sistema():
    modelo = _modelo()
    modelo.requisitos[2].actor = "sistema"
    modelo.requisitos[1].actor = "Administrador "
    # «Administrador » se normaliza; «cliente» va primero porque aparece en más requisitos.
    assert actores(modelo) == ["cliente", "administrador"]


def test_diagrama_de_contexto():
    modelo = _modelo()
    diagrama = diagrama_contexto(_arquitectura(), modelo, nombre="Tienda en línea")
    assert diagrama.splitlines()[0] == "C4Context"
    assert 'Person(p_cliente, "Cliente"' in diagrama
    assert 'System(sistema, "Tienda en línea", "3 microservicios: usuarios, pedidos' in diagrama
    assert 'Rel(p_cliente, sistema, "Usa", "HTTPS")' in diagrama


def test_sin_nombre_usa_el_del_documento():
    diagrama = diagrama_contexto(_arquitectura(), _modelo())
    assert "Sistema del documento «requisitos.md»" in diagrama


# --- Contenedores --------------------------------------------------------------------------------


def test_contenedores_con_gateway_identidad_y_eventos():
    diagrama = diagrama_contenedores(_arquitectura(), _decision(), nombre="Tienda")
    assert diagrama.splitlines()[0] == "flowchart TB"
    assert 'subgraph sistema["Tienda"]' in diagrama
    assert "gateway[" in diagrama and "[Traefik]" in diagrama
    assert "identidad[" in diagrama  # RF-01 lleva la etiqueta autenticacion
    assert 'eventos[["<b>Bus de eventos</b><br/>[RabbitMQ]"]]' in diagrama
    # Cada servicio con su base de datos.
    for nombre in ("usuarios", "pedidos", "notificaciones"):
        assert f"s_{nombre}[" in diagrama
        assert f'db_{nombre}_db[("<b>{nombre}_db</b><br/>[PostgreSQL]")]' in diagrama
        assert f's_{nombre} -->|"SQL"| db_{nombre}_db' in diagrama
        assert f'gateway -->|"HTTP"| s_{nombre}' in diagrama
    # Síncrona: flecha directa. Asíncrona: pasa por el bus y es punteada.
    assert 's_pedidos -->|"HTTP: Necesita sus datos o eventos."| s_usuarios' in diagrama
    assert 'eventos -.->|"Necesita sus datos o eventos."| s_notificaciones' in diagrama
    assert 's_pedidos -.->|"publica eventos"| eventos' in diagrama
    assert "class usuarios persona" in diagrama


def test_sin_gateway_ni_eventos_ni_identidad_no_se_dibujan():
    modelo_sin_auth = _arquitectura(
        servicios=[
            _servicio("pedidos", ["RF-02"]),
            _servicio("notificaciones", ["RF-03"], [("pedidos", "sincrona")]),
            _servicio("usuarios", ["RF-01"]),
        ]
    )
    for servicio in modelo_sin_auth.servicios:
        servicio.etiquetas = []
    modelo_sin_auth.etiquetas_transversales = []
    diagrama = diagrama_contenedores(modelo_sin_auth, _sin_gateway())
    assert "gateway" not in diagrama
    assert "identidad" not in diagrama
    assert "eventos[[" not in diagrama and "-.->" not in diagrama
    assert 'usuarios -->|"HTTPS"| s_pedidos' in diagrama


# --- Documento -----------------------------------------------------------------------------------


def test_documento_completo():
    texto = documento_arquitectura(
        _arquitectura(),
        _modelo(),
        _decision(),
        FECHA,
        adrs={"api_gateway": "adr/0002-aplicar-el-patron-api-gateway.md"},
        nombre="Tienda en línea",
    )
    assert texto.splitlines()[0] == MARCA
    assert "# Arquitectura: Tienda en línea" in texto
    assert texto.count("```mermaid") == 2
    for seccion in (
        "## 1. Contexto",
        "## 2. Contenedores",
        "## 3. Servicios",
        "## 4. Dependencias entre servicios",
        "## 5. Patrones aplicados",
        "## 6. Validación de OPA",
    ):
        assert seccion in texto
    assert "| `pedidos` | `usuarios` | síncrona (HTTP) |" in texto
    assert "| API Gateway | traefik |" in texto
    assert "[ver ADR](adr/0002-aplicar-el-patron-api-gateway.md)" in texto
    assert "| `arquitectura.sin_ciclos` | sí |" in texto


def test_no_se_dibuja_una_arquitectura_rechazada():
    with pytest.raises(ErrorDiagrama, match="OPA no aprobó la arquitectura: ciclo"):
        documento_arquitectura(_arquitectura(), _modelo(), _decision(aprobado=False), FECHA)


def test_enlaces_solo_a_los_adr_que_existen(tmp_path: Path):
    arquitectura, decision, modelo = _arquitectura(), _decision(), _modelo()
    adrs = construir_adrs(arquitectura, decision, modelo)
    carpeta = tmp_path / "docs" / "adr"
    carpeta.mkdir(parents=True)
    gateway = next(a for a in adrs if a.patron == "api_gateway")
    (carpeta / gateway.archivo).write_text(MARCA + "\n", encoding="utf-8")

    enlaces = enlaces_adr(adrs, carpeta, tmp_path / "docs" / "arquitectura.md")
    assert enlaces == {"api_gateway": f"adr/{gateway.archivo}"}


def test_escribir_no_pisa_un_documento_escrito_a_mano(tmp_path: Path):
    destino = tmp_path / "arquitectura.md"
    destino.write_text("# Escrito por el equipo\n", encoding="utf-8")
    with pytest.raises(ErrorDiagrama, match="no lo generó el framework"):
        escribir_documento(MARCA + "\nnuevo\n", destino)
    assert destino.read_text(encoding="utf-8") == "# Escrito por el equipo\n"

    generado = tmp_path / "otro.md"
    escribir_documento(MARCA + "\nprimero\n", generado)
    escribir_documento(MARCA + "\nsegundo\n", generado)  # el suyo sí lo reemplaza
    assert "segundo" in generado.read_text(encoding="utf-8")


# --- CLI con OPA de verdad -----------------------------------------------------------------------


def _archivos(tmp_path: Path, **cambios) -> tuple[Path, Path]:
    arquitectura = tmp_path / "x.arquitectura.json"
    modelo = tmp_path / "x.modelo_requisitos.json"
    arquitectura.write_text(_arquitectura(**cambios).model_dump_json(), encoding="utf-8")
    modelo.write_text(_modelo().model_dump_json(), encoding="utf-8")
    return arquitectura, modelo


@con_opa
def test_cli_escribe_el_documento_tras_validar_con_opa(tmp_path: Path):
    arquitectura, modelo = _archivos(tmp_path)
    salida = tmp_path / "docs" / "arquitectura.md"
    resultado = runner.invoke(
        app,
        [
            "arquitectura",
            "diagrama",
            str(arquitectura),
            "--requisitos",
            str(modelo),
            "--salida",
            str(salida),
            "--adr",
            str(tmp_path / "docs" / "adr"),
            "--nombre",
            "Tienda",
        ],
    )
    assert resultado.exit_code == 0, resultado.output
    assert "OPA: Arquitectura aprobada" in resultado.output
    texto = salida.read_text(encoding="utf-8")
    assert "# Arquitectura: Tienda" in texto and texto.count("```mermaid") == 2


@con_opa
def test_cli_no_dibuja_una_arquitectura_con_ciclos(tmp_path: Path):
    arquitectura, modelo = _archivos(
        tmp_path,
        servicios=[
            _servicio("usuarios", ["RF-01"], [("pedidos", "sincrona")]),
            _servicio("pedidos", ["RF-02"], [("usuarios", "sincrona")]),
            _servicio("notificaciones", ["RF-03"]),
        ],
    )
    salida = tmp_path / "arquitectura.md"
    resultado = runner.invoke(
        app,
        [
            "arquitectura",
            "diagrama",
            str(arquitectura),
            "--requisitos",
            str(modelo),
            "--salida",
            str(salida),
        ],
    )
    assert resultado.exit_code == 1
    assert "arquitectura.sin_ciclos" in resultado.output
    assert not salida.exists()


def test_cli_rechaza_requisitos_de_otro_documento(tmp_path: Path):
    arquitectura, modelo = _archivos(tmp_path)
    texto = modelo.read_text(encoding="utf-8").replace("0" * 64, "f" * 64)
    modelo.write_text(texto, encoding="utf-8")
    resultado = runner.invoke(
        app, ["arquitectura", "diagrama", str(arquitectura), "--requisitos", str(modelo)]
    )
    assert resultado.exit_code == 1
    assert "documentos distintos" in resultado.output
