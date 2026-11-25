"""Fase 3 completa: los N servicios de arquitectura.json (orchestrator/generation/sistema.py).

El LLM se simula. Estas pruebas no compilan (`compilar_servicios=False`): la instalación, tsc y
Jest se comprueban con la ejecución real (ver orchestrator/generation/README.md).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from orchestrator.generation import validar_estructura
from orchestrator.generation.sistema import (
    ARCHIVO_RESUMEN,
    ErrorSistema,
    enlazar_directorio,
    generar_sistema,
    huella_del_lock,
)
from orchestrator.llm import ErrorLLM
from orchestrator.llm.prompts import EntidadesPropuestas, LogicaEntidad
from tests.test_arquitectura import _modelo
from tests.test_parametros_estructura import _arquitectura, _con_entidades, _tienda

REGLA = (
    "if (datos.nombre === 'prohibido') {\n"
    "  throw new BadRequestException('Nombre no permitido');\n"
    "}"
)


class LLMSimulado:
    """Devuelve las entidades que pide el prompt y una regla de negocio sencilla."""

    def __init__(self, falla_en: str | None = None) -> None:
        self.falla_en = falla_en
        self.llamadas: list[str] = []

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        if issubclass(esquema, EntidadesPropuestas):
            servicio = re.search(r'nombre="([a-z_]+)"', prompt).group(1)
            self.llamadas.append(f"especificacion:{servicio}")
            if servicio == self.falla_en:
                raise ErrorLLM("El proveedor no respondió")
            linea = prompt.split("Entidades que le asignó la arquitectura:")[1].splitlines()[0]
            entidades = re.findall(r"\(([a-z][a-z0-9_]*)\)", linea)
            return esquema.model_validate(
                {
                    "entidades": [
                        {"nombre": e, "campos": [{"nombre": "nombre", "tipo": "texto", "max": 80}]}
                        for e in entidades
                    ]
                }
            )
        if esquema is LogicaEntidad:
            self.llamadas.append("logica")
            return LogicaEntidad(
                reglas_al_crear=REGLA,
                reglas_al_actualizar="",
                reglas_al_eliminar="",
                requisitos=[],
                controles=[],
                pendientes=[],
            )
        raise AssertionError(f"Esquema inesperado: {esquema.__name__}")


def _generar(tmp_path: Path, llm=None, **opciones):
    return generar_sistema(
        _tienda(),
        _modelo(),
        tmp_path / "sistema",
        llm or LLMSimulado(),
        documento="tienda",
        compilar_servicios=False,
        **opciones,
    )


def test_genera_un_servicio_por_cada_servicio_de_la_arquitectura(tmp_path: Path):
    llm = LLMSimulado()
    resultado = _generar(tmp_path, llm)
    destino = tmp_path / "sistema"

    assert [s.servicio for s in resultado.servicios] == ["usuarios", "pedidos", "notificaciones"]
    assert resultado.completos == 3 and resultado.compilado is False
    pedidos = resultado.servicios[1]
    assert (pedidos.puerto, pedidos.base_datos, pedidos.prefijo) == (
        3002,
        "pedidos_db",
        "/api/pedidos",
    )
    assert [e.nombre for e in pedidos.entidades] == ["pedido", "linea_pedido"]
    assert [e.ruta for e in pedidos.entidades] == [
        "/api/pedidos/pedido",
        "/api/pedidos/linea-pedido",
    ]
    assert pedidos.estructura_valida and pedidos.dependencias_permitidas
    assert pedidos.compila is None  # sin compilar
    assert all(e.logica == "aceptada" for s in resultado.servicios for e in s.entidades)
    # Una especificación por servicio y la lógica de cada entidad, con su registro.
    assert len(llm.llamadas) == 3 + 4
    assert (destino / "especificaciones" / "pedidos.yml").is_file()
    assert (destino / "pedidos" / "logica" / "linea_pedido.json").is_file()
    servicio_ts = (destino / "pedidos" / "src" / "pedido.service.ts").read_text(encoding="utf-8")
    assert "throw new BadRequestException('Nombre no permitido');" in servicio_ts
    # La estructura sigue siendo la de la plantilla después de la lógica.
    assert validar_estructura(destino / "pedidos").valida
    guardado = json.loads((destino / ARCHIVO_RESUMEN).read_text(encoding="utf-8"))
    assert guardado["documento"] == "tienda" and len(guardado["servicios"]) == 3


def test_un_servicio_que_falla_no_detiene_los_demas(tmp_path: Path):
    resultado = _generar(tmp_path, LLMSimulado(falla_en="pedidos"))

    usuarios, pedidos, notificaciones = resultado.servicios
    assert usuarios.completo and notificaciones.completo
    assert not pedidos.completo
    assert pedidos.error == "El proveedor no respondió"
    assert all(e.logica == "omitida" for e in pedidos.entidades)
    assert not (tmp_path / "sistema" / "pedidos").exists()


def test_sin_logica_solo_genera_con_la_plantilla(tmp_path: Path):
    llm = LLMSimulado()
    resultado = _generar(tmp_path, llm, con_logica=False)
    assert llm.llamadas == [
        "especificacion:usuarios",
        "especificacion:pedidos",
        "especificacion:notificaciones",
    ]
    assert all(e.logica == "omitida" for s in resultado.servicios for e in s.entidades)


def test_avisa_del_avance_de_cada_servicio(tmp_path: Path):
    avisos: list[tuple[str, float | None]] = []
    _generar(tmp_path, avance=lambda mensaje, progreso=None: avisos.append((mensaje, progreso)))

    assert avisos[0][0].startswith("usuarios (1/3): el LLM propone los campos de 1 entidades")
    assert any(m.startswith("pedidos (2/3): lógica de negocio de linea_pedido") for m, _ in avisos)
    progresos = [p for _, p in avisos if p is not None]
    assert progresos == sorted(progresos) and progresos[-1] == 1.0


def test_la_cancelacion_detiene_la_fase(tmp_path: Path):
    class Cancelada(Exception):
        pass

    llamadas = 0

    def comprobar() -> None:
        nonlocal llamadas
        llamadas += 1
        if llamadas > 3:
            raise Cancelada

    with pytest.raises(Cancelada):
        _generar(tmp_path, comprobar_cancelacion=comprobar)


def test_no_escribe_sobre_una_carpeta_con_contenido(tmp_path: Path):
    (tmp_path / "sistema").mkdir()
    (tmp_path / "sistema" / "otro.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ErrorSistema, match="no está vacía"):
        _generar(tmp_path)


def test_una_arquitectura_sin_parametros_validos_no_genera_nada(tmp_path: Path):
    arquitectura = _arquitectura(_con_entidades("pedidos", ["RF-01", "RF-02", "RF-03"], ["Prisma"]))
    with pytest.raises(ErrorSistema, match="nombre reservado"):
        generar_sistema(arquitectura, _modelo(), tmp_path / "sistema", LLMSimulado())
    assert not (tmp_path / "sistema").exists()


# --- Dependencias compartidas ------------------------------------------------------------------


def test_todos_los_servicios_comparten_el_lock_salvo_el_nombre(tmp_path: Path):
    _generar(tmp_path, con_logica=False)
    huellas = {
        huella_del_lock(tmp_path / "sistema" / s) for s in ("usuarios", "pedidos", "notificaciones")
    }
    assert len(huellas) == 1

    lock = tmp_path / "sistema" / "pedidos" / "package-lock.json"
    datos = json.loads(lock.read_text(encoding="utf-8"))
    datos["packages"]["node_modules/effect"]["version"] = "3.20.0"
    lock.write_text(json.dumps(datos), encoding="utf-8")
    assert huella_del_lock(lock.parent) not in huellas


def test_node_modules_enlazado_es_valido_pero_otro_enlace_no(tmp_path: Path):
    _generar(tmp_path, con_logica=False)
    servicio = tmp_path / "sistema" / "pedidos"
    compartidas = tmp_path / "compartidas" / "node_modules"
    compartidas.mkdir(parents=True)
    (compartidas / "paquete.js").write_text("x", encoding="utf-8")

    enlazar_directorio(servicio / "node_modules", compartidas)
    assert (servicio / "node_modules" / "paquete.js").is_file()
    assert validar_estructura(servicio).valida

    enlazar_directorio(servicio / "src" / "otra", compartidas)
    assert "src/otra es un enlace" in validar_estructura(servicio).problemas
    # Borrar el enlace no borra las dependencias compartidas.
    os.rmdir(servicio / "src" / "otra") if os.name == "nt" else (servicio / "src" / "otra").unlink()
    assert (compartidas / "paquete.js").is_file()


def test_las_pruebas_del_llm_no_son_archivos_inesperados(tmp_path: Path):
    _generar(tmp_path, con_logica=False)
    servicio = tmp_path / "sistema" / "pedidos"
    (servicio / "src" / "pedido.reglas.spec.ts").write_text("// pruebas", encoding="utf-8")
    (servicio / "pruebas").mkdir()
    (servicio / "pruebas" / "pedido.json").write_text("{}", encoding="utf-8")
    assert validar_estructura(servicio).valida

    (servicio / "src" / "otra.reglas.spec.ts").write_text("// no es una entidad", encoding="utf-8")
    assert "Archivo inesperado: src/otra.reglas.spec.ts" in validar_estructura(servicio).problemas


# --- CLI ---------------------------------------------------------------------------------------


def test_cli_servicio_sistema(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from typer.testing import CliRunner

    from orchestrator.cli import app

    arquitectura = tmp_path / "tienda.arquitectura.json"
    requisitos = tmp_path / "tienda.modelo_requisitos.json"
    arquitectura.write_text(_tienda().model_dump_json(), encoding="utf-8")
    requisitos.write_text(_modelo().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr("orchestrator.llm.crear_proveedor", lambda nombre=None: LLMSimulado())
    destino = tmp_path / "servicios"

    resultado = CliRunner().invoke(
        app,
        [
            "servicio",
            "sistema",
            str(arquitectura),
            "--requisitos",
            str(requisitos),
            "--destino",
            str(destino),
            "--sin-compilar",
            "--sin-graphrag",
        ],
    )

    assert resultado.exit_code == 0, resultado.output
    assert "pedidos (2/3): lógica de negocio de linea_pedido" in resultado.output
    assert "3 de 3 servicios completos" in resultado.output
    assert (destino / "sistema.json").is_file()
    assert (destino / "notificaciones" / "src" / "notificacion.service.ts").is_file()


# --- Límite de uso del LLM ---------------------------------------------------------------------


class LLMConLimite(LLMSimulado):
    """Falla con `errores` (en orden) y después responde como LLMSimulado."""

    def __init__(self, *errores: Exception) -> None:
        super().__init__()
        self.errores = list(errores)

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        if self.errores:
            raise self.errores.pop(0)
        return super().generar_estructurado(prompt, esquema, nivel, sistema)


def test_espera_el_limite_de_uso_y_reintenta(tmp_path: Path):
    from orchestrator.llm.base import ErrorLimiteLLM

    esperas: list[float] = []
    avisos: list[str] = []
    llm = LLMConLimite(
        ErrorLimiteLLM("todos los proveedores (groq, gemini) alcanzaron su límite de uso", 7.0),
        ErrorLimiteLLM("todos los proveedores (groq, gemini) alcanzaron su límite de uso", 7.0),
    )
    resultado = _generar(
        tmp_path, llm, esperar=esperas.append, avance=lambda m, p=None: avisos.append(m)
    )

    assert resultado.completos == 3
    assert esperas == [7.0, 7.0]
    assert any(m.endswith("alcanzaron su límite de uso: se reintenta en 7 s") for m in avisos)


def test_la_cuota_diaria_no_se_espera_y_corta_el_resto(tmp_path: Path):
    from orchestrator.llm.base import ErrorLimiteLLM

    esperas: list[float] = []
    llm = LLMConLimite(ErrorLimiteLLM("gemini: cuota diaria agotada", 3600.0, diario=True))
    resultado = _generar(tmp_path, llm, esperar=esperas.append)

    assert esperas == []
    assert resultado.completos == 0
    assert resultado.servicios[0].error == "gemini: cuota diaria agotada"
    # Los siguientes no vuelven a gastar llamadas ni esperas.
    assert "se agotaron las esperas" in resultado.servicios[1].error
    assert llm.llamadas == []


def test_tras_agotar_las_esperas_no_vuelve_a_esperar(tmp_path: Path):
    from orchestrator.llm.base import ErrorProveedorLLM

    esperas: list[float] = []
    sin_proveedor = [ErrorProveedorLLM("ningún proveedor de LLM disponible (groq, gemini)")] * 10
    resultado = _generar(tmp_path, LLMConLimite(*sin_proveedor), esperar=esperas.append)

    assert esperas == [30.0, 60.0, 120.0]  # solo en la primera llamada
    assert [s.completo for s in resultado.servicios] == [False, False, False]


def test_una_entidad_sin_poder_pedir_su_logica_deja_el_servicio_incompleto(tmp_path: Path):
    class FallaLaLogica(LLMSimulado):
        def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
            if esquema is LogicaEntidad:
                raise ErrorLLM("La respuesta no cumple el esquema")
            return super().generar_estructurado(prompt, esquema, nivel, sistema)

    resultado = _generar(tmp_path, FallaLaLogica())

    usuarios = resultado.servicios[0]
    assert usuarios.estructura_valida and usuarios.error is None
    assert usuarios.entidades[0].logica == "error"
    assert not usuarios.completo and resultado.completos == 0


def test_los_errores_no_muestran_el_cuerpo_de_la_respuesta_del_proveedor():
    from orchestrator.generation.sistema import mensaje_breve

    error = (
        "groq: error 413 de la API: Error code: 413 - {'error': {'message': 'Request too large "
        "for model in organization `org_01m7158ank` service tier on_demand'}}"
    )
    assert mensaje_breve(error) == "groq: error 413 de la API"
    assert mensaje_breve("gemini: límite de peticiones alcanzado") == (
        "gemini: límite de peticiones alcanzado"
    )
    assert mensaje_breve("primera línea\nsegunda") == "primera línea"


# --- Comprobación final con tsc ----------------------------------------------------------------


def test_las_pruebas_del_llm_que_no_compilan_se_descartan(tmp_path: Path, monkeypatch):
    """ts-jest no comprueba tipos: lo que pasa en Jest puede no pasar el tsc del Gate 1."""
    import orchestrator.generation.sistema as sistema
    from orchestrator.generation.sistema import EntidadGenerada, ServicioGenerado

    carpeta = tmp_path / "pagos"
    (carpeta / "src").mkdir(parents=True)
    spec = carpeta / "src" / "linea-pedido.reglas.spec.ts"
    spec.write_text("// pruebas del LLM", encoding="utf-8")
    error = "src/linea-pedido.reglas.spec.ts(44,39): error TS2352: Conversion of type"
    llamadas = []

    def compilar_falso(ruta):
        llamadas.append(ruta)
        return [error] if spec.exists() else []

    monkeypatch.setattr(sistema, "compilar", compilar_falso)
    resumen = ServicioGenerado(
        servicio="pagos",
        carpeta="pagos",
        puerto=3001,
        base_datos="pagos_db",
        prefijo="/api/pagos",
        estructura_valida=True,
        entidades=[
            EntidadGenerada(
                nombre="linea_pedido",
                ruta="/api/pagos/linea-pedido",
                logica="aceptada",
                pruebas_aceptadas=17,
            )
        ],
    )

    sistema._compilar_al_final(carpeta, resumen)

    assert not spec.exists()
    entidad = resumen.entidades[0]
    assert (entidad.pruebas_aceptadas, entidad.pruebas_descartadas) == (0, 17)
    assert entidad.detalle.startswith("Pruebas descartadas: no compilan con tsc (src/linea-pedido")
    assert resumen.compila is True and resumen.completo
    assert len(llamadas) == 2  # se vuelve a compilar después de quitarlas


def test_si_sigue_sin_compilar_el_servicio_no_esta_completo(tmp_path: Path, monkeypatch):
    import orchestrator.generation.sistema as sistema
    from orchestrator.generation.sistema import ServicioGenerado

    monkeypatch.setattr(sistema, "compilar", lambda ruta: ["src/pago.service.ts(3,1): error TS1"])
    resumen = ServicioGenerado(
        servicio="pagos",
        carpeta="pagos",
        puerto=3001,
        base_datos="pagos_db",
        prefijo="/api/pagos",
        estructura_valida=True,
    )
    sistema._compilar_al_final(tmp_path, resumen)
    assert resumen.compila is False and not resumen.completo
