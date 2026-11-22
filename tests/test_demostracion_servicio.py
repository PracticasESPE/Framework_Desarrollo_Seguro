"""`framework servicio demo`: la demostración de la fase 3 con un solo comando.

Genera un servicio de verdad con Copier (sin LLM, sin Docker y sin red), así que cada prueba
tarda unos segundos. La compilación con npm se simula.
"""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.generation import ResultadoEstructura
from orchestrator.generation import demostracion as modulo

runner = CliRunner()


def _demo(destino: Path, *opciones: str):
    return runner.invoke(app, ["servicio", "demo", "--destino", str(destino), *opciones])


def test_la_demostracion_completa_pasa_todos_los_pasos(tmp_path: Path):
    resultado = _demo(tmp_path / "demo")

    assert resultado.exit_code == 0, resultado.output
    salida = resultado.output
    assert "[1/6] Parámetros de cada servicio" in salida
    assert "7 servicios en 01_tienda_en_linea.arquitectura.json" in salida
    assert "pedidos      3004" in salida
    assert "Estructura válida; rutas: /api/pedidos/pedido, /api/pedidos/linea-pedido" in salida
    assert "todas las dependencias están en la lista permitida" in salida
    assert "Detectado: un servicio sin sus controles de seguridad" in salida
    assert "Rechazado: nunca se llegaría a descargar." in salida
    assert "Resultado: 6 de 6 pasos correctos" in salida
    assert "NO se" not in salida
    # Lo que falta también se dice, para que nadie crea que la fase 3 está completa.
    assert "Todavía no está en el motor" in salida
    assert "La fase 3 en la API y el dashboard" in salida
    assert "framework servicio logica" in salida


def test_deja_el_servicio_y_borra_las_copias_de_los_controles(tmp_path: Path):
    destino = tmp_path / "demo"
    _demo(destino)

    assert (destino / "pedidos" / "package.json").is_file()
    assert not (destino / "pedidos-roto").exists()
    assert not (destino / "pedidos-malo").exists()


def test_se_puede_repetir_sin_borrar_nada_a_mano(tmp_path: Path):
    destino = tmp_path / "demo"
    assert _demo(destino).exit_code == 0
    segunda = _demo(destino)

    assert segunda.exit_code == 0, segunda.output
    assert "Resultado: 6 de 6 pasos correctos" in segunda.output


def test_nunca_borra_una_carpeta_que_no_creo(tmp_path: Path):
    ajena = tmp_path / "mis-servicios"
    (ajena / "pedidos").mkdir(parents=True)
    importante = ajena / "pedidos" / "importante.txt"
    importante.write_text("no borrar", encoding="utf-8")

    resultado = _demo(ajena)

    assert resultado.exit_code == 1
    assert "no lo creó la demostración" in resultado.output
    assert importante.read_text(encoding="utf-8") == "no borrar"


def test_una_carpeta_vacia_si_se_puede_usar(tmp_path: Path):
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    assert _demo(vacia).exit_code == 0


def test_falla_si_la_validacion_no_detecta_un_control_quitado(tmp_path: Path, monkeypatch):
    # Una validación que da por buena cualquier estructura: los controles negativos lo delatan.
    monkeypatch.setattr(
        modulo, "validar_estructura", lambda *_a, **_k: ResultadoEstructura(archivos=["a"])
    )
    resultado = _demo(tmp_path / "demo")

    assert resultado.exit_code == 1
    assert "NO se detectó: la validación de la estructura no protege." in resultado.output
    assert "Resultado: 5 de 6 pasos correctos" in resultado.output


def test_falla_si_la_lista_deja_pasar_un_paquete_inventado(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(modulo, "verificar_servicio", lambda *_a, **_k: [])
    resultado = _demo(tmp_path / "demo")

    assert resultado.exit_code == 1
    assert "NO se rechazó: la lista de dependencias permitidas no protege." in resultado.output


def test_una_arquitectura_ilegible_se_informa_y_la_demostracion_falla(tmp_path: Path):
    mala = tmp_path / "mala.json"
    mala.write_text("{no es json", encoding="utf-8")
    resultado = _demo(tmp_path / "demo", "--arquitectura", str(mala))

    assert resultado.exit_code == 1
    assert "No se pudo leer mala.json" in resultado.output
    assert "-> FALLA" in resultado.output


def test_compilar_instala_y_compila_con_tsc(tmp_path: Path, monkeypatch):
    llamadas: list[str] = []
    from orchestrator.generation import logica

    monkeypatch.setattr(
        logica, "preparar", lambda carpeta: llamadas.append(f"preparar {carpeta.name}")
    )
    monkeypatch.setattr(logica, "compilar", lambda carpeta: llamadas.append("tsc") or [])
    resultado = _demo(tmp_path / "demo", "--compilar")

    assert resultado.exit_code == 0, resultado.output
    assert llamadas == ["preparar pedidos", "tsc"]
    assert "[7/7] Instalar, generar el cliente de Prisma y compilar con tsc" in resultado.output
    assert "El servicio compila sin errores (tsc)." in resultado.output


def test_compilar_informa_los_errores_de_tsc(tmp_path: Path, monkeypatch):
    from orchestrator.generation import logica

    monkeypatch.setattr(logica, "preparar", lambda carpeta: None)
    monkeypatch.setattr(
        logica, "compilar", lambda carpeta: ["src/a.ts(1,1): error TS2304: Cannot find name 'x'."]
    )
    resultado = _demo(tmp_path / "demo", "--compilar")

    assert resultado.exit_code == 1
    assert "error TS2304" in resultado.output


def test_arbol_muestra_los_archivos_del_servicio(tmp_path: Path):
    sin = _demo(tmp_path / "a")
    con = _demo(tmp_path / "b", "--arbol")

    assert "jwt-auth.guard.ts" not in sin.output.split("[4/6]")[0]
    assert "jwt-auth.guard.ts" in con.output.split("[4/6]")[0]


@pytest.mark.parametrize("nombre", ["pedidos-roto", "pedidos-malo"])
def test_las_copias_se_borran_aunque_un_paso_falle(tmp_path: Path, monkeypatch, nombre: str):
    monkeypatch.setattr(modulo, "verificar_servicio", lambda *_a, **_k: [])
    destino = tmp_path / "demo"
    _demo(destino)

    assert not (destino / nombre).exists()
