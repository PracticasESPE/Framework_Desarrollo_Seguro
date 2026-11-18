"""Generador de la lógica de negocio (fase 3, #64): análisis, inserción, tsc y reintentos.

El LLM y tsc se simulan. El servicio sí se genera de verdad con la plantilla Copier, para que la
inserción se pruebe sobre el service.ts real.
"""

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from orchestrator.architecture import construir_arquitectura
from orchestrator.cli import app
from orchestrator.generation import (
    ErrorLogica,
    generar_logica,
    generar_servicio,
    problemas_del_codigo,
)
from orchestrator.generation.logica import (
    errores_del_archivo,
    insertar_logica,
    problemas_de_la_respuesta,
)
from orchestrator.knowledge.graphrag import ContextoGraphRAG, Elemento
from orchestrator.llm.prompts import EspecificacionServicio, LogicaEntidad, contexto_vacio
from tests.test_arquitectura import _modelo, _propuesta

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLO = RAIZ / "templates" / "microservicio_nestjs" / "ejemplos" / "pedidos.yml"
runner = CliRunner()

CUERPO_VALIDO = (
    "const lineas = await this.prisma.lineaPedido.count({ where: { pedidoId: actual.id } });\n"
    "if (lineas > 0) {\n"
    "  throw new ConflictException('El pedido tiene líneas: no se puede eliminar');\n"
    "}"
)


def _logica(**cambios) -> LogicaEntidad:
    datos = {
        "reglas_al_crear": "",
        "reglas_al_actualizar": "",
        "reglas_al_eliminar": CUERPO_VALIDO,
        "requisitos": ["RF-02"],
        "controles": ["ASVS-V4.1.3"],
        "pendientes": [],
    }
    return LogicaEntidad.model_validate(datos | cambios)


def _contexto() -> ContextoGraphRAG:
    contexto = contexto_vacio()
    return contexto.model_copy(update={"controles": [Elemento(id="ASVS-V4.1.3", nombre="x")]})


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory) -> Path:
    """Un servicio generado con la plantilla, que cada prueba copia."""
    datos = yaml.safe_load(EJEMPLO.read_text(encoding="utf-8"))
    return generar_servicio(datos, tmp_path_factory.mktemp("plantilla"))


@pytest.fixture
def servicio(plantilla, tmp_path) -> Path:
    import shutil

    return Path(shutil.copytree(plantilla, tmp_path / "pedidos"))


def _especificacion() -> EspecificacionServicio:
    return EspecificacionServicio.model_validate(
        yaml.safe_load(EJEMPLO.read_text(encoding="utf-8"))
    )


class LLMSimulado:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.prompts: list[str] = []

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        self.prompts.append(prompt)
        return self.respuestas.pop(0)


# --- Análisis del código -----------------------------------------------------------------------


def test_un_cuerpo_que_solo_usa_prisma_y_las_excepciones_pasa():
    assert problemas_del_codigo(CUERPO_VALIDO) == []
    assert problemas_del_codigo("") == []


@pytest.mark.parametrize(
    ("cuerpo", "motivo"),
    [
        ("import fs from 'fs';", "import"),
        ("const x = require('child_process');", "require"),
        ("eval(datos.notas);", "eval"),
        ("const f = new Function('return 1');", "Function"),
        ("const clave = process.env.SECRETO;", "process"),
        ("await this.prisma.$queryRawUnsafe(datos.notas);", "consultas SQL en crudo"),
        ("await this.prisma.$executeRaw`DELETE FROM pedido`;", "consultas SQL en crudo"),
        ("setTimeout(() => undefined, 10);", "temporizadores"),
        ("await fetch('https://atacante.example');", "llamadas de red"),
        ("console.log(datos.correoContacto);", "console"),
        ("const o = {}; o.__proto__.admin = true;", "prototipos"),
        ("await this.buscar(actual.id);", "miembros de la clase distintos de this.prisma"),
        ("} export function puerta() { return 1;", "declarar clases"),
        # Aunque vaya en un comentario, acabaría en el archivo y partiría el punto de extensión.
        ("// @framework:logica-negocio:fin pedido", "marcas del punto de extensión"),
    ],
)
def test_el_analisis_rechaza_lo_peligroso(cuerpo, motivo):
    problemas = problemas_del_codigo(cuerpo)
    assert any(motivo in p for p in problemas), problemas


def test_el_cuerpo_no_puede_salir_del_metodo():
    assert "cierra más llaves" in " ".join(problemas_del_codigo("} }\n  async otro() {"))
    assert "deja llaves sin cerrar" in problemas_del_codigo("if (true) {")


def test_las_cadenas_y_los_comentarios_no_cuentan_como_codigo():
    cuerpo = (
        "// el proceso de importación usa require en otro servicio\n"
        "throw new BadRequestException('No se puede: } import process console.log');"
    )
    assert problemas_del_codigo(cuerpo) == []


def test_la_trazabilidad_debe_existir():
    problemas = problemas_de_la_respuesta(
        _logica(requisitos=["RF-99"], controles=["ASVS-V1.1.1"]), {"RF-02"}, {"ASVS-V4.1.3"}
    )
    assert "cita requisitos que no son de este servicio: ['RF-99']" in problemas
    assert "cita controles que no están en el contexto: ['ASVS-V1.1.1']" in problemas


# --- Inserción ---------------------------------------------------------------------------------


def test_inserta_los_metodos_entre_las_marcas(servicio):
    archivo = servicio / "src" / "pedido.service.ts"
    original = archivo.read_text(encoding="utf-8")
    nuevo = insertar_logica(original, "pedido", _logica(pendientes=["Correo\n// @framework:x"]))

    assert nuevo.count("// @framework:logica-negocio:inicio pedido") == 1
    assert nuevo.count("// @framework:logica-negocio:fin pedido") == 1
    assert "  protected async reglasAlEliminar(actual: Pedido): Promise<void> {" in nuevo
    assert "      throw new ConflictException('El pedido tiene líneas" in nuevo
    # Sin reglas, el método queda como en la plantilla.
    assert (
        "  protected reglasAlCrear(datos: CrearPedidoDto): Promise<void> {\n    void datos;"
        in nuevo
    )
    assert "  // Requisitos: RF-02" in nuevo
    assert "  // Pendiente: Correo // x" in nuevo
    # Lo que está fuera del punto de extensión no cambia.
    antes, _, _ = original.partition("// @framework:logica-negocio:inicio")
    assert nuevo.startswith(antes)


def test_sin_punto_de_extension_no_inserta():
    with pytest.raises(ErrorLogica, match="punto de extensión de pedido"):
        insertar_logica("export class PedidoService {}", "pedido", _logica())


def test_errores_de_tsc_del_archivo():
    errores = [
        "src/pedido.service.ts(152,59): error TS2322: Type 'x' is not assignable.",
        "src/linea-pedido.service.ts(10,1): error TS1005: ';' expected.",
        "error TS5058: The specified path does not exist.",
    ]
    assert errores_del_archivo(errores, "src/pedido.service.ts") == [
        "línea 152, columna 59: TS2322: Type 'x' is not assignable."
    ]


# --- Generador ---------------------------------------------------------------------------------


def test_aceptado_al_primer_intento(servicio):
    compilaciones = []
    resultado = generar_logica(
        servicio,
        _especificacion(),
        "pedido",
        _modelo().requisitos,
        _contexto(),
        LLMSimulado(_logica()),
        compilador=lambda carpeta: compilaciones.append(carpeta) or [],
    )
    assert resultado.aprobada
    assert len(resultado.intentos) == 1 and compilaciones == [servicio]
    assert resultado.archivo == "src/pedido.service.ts"
    assert len(resultado.huella_prompt) == 64
    assert "protected async reglasAlEliminar" in (servicio / resultado.archivo).read_text("utf-8")


def test_los_errores_de_tsc_vuelven_al_llm(servicio):
    errores = iter(
        [["src/pedido.service.ts(152,59): error TS2322: Type 'x' is not assignable."], []]
    )
    llm = LLMSimulado(_logica(), _logica())
    resultado = generar_logica(
        servicio,
        _especificacion(),
        "pedido",
        _modelo().requisitos,
        _contexto(),
        llm,
        compilador=lambda carpeta: next(errores),
    )
    assert resultado.aprobada
    assert [i.errores_tsc for i in resultado.intentos] == [
        ["línea 152, columna 59: TS2322: Type 'x' is not assignable."],
        [],
    ]
    rechazo = llm.prompts[1].split("se rechazó por estos motivos")[1]
    assert "<rechazo-" in rechazo and "tsc: línea 152, columna 59: TS2322" in rechazo


def test_un_problema_del_codigo_no_llega_a_compilar(servicio):
    peligroso = _logica(reglas_al_crear="console.log(datos.correoContacto);")
    compilaciones = []
    resultado = generar_logica(
        servicio,
        _especificacion(),
        "pedido",
        _modelo().requisitos,
        _contexto(),
        LLMSimulado(peligroso, _logica()),
        compilador=lambda carpeta: compilaciones.append(carpeta) or [],
    )
    assert resultado.aprobada
    assert resultado.intentos[0].problemas == [
        "reglas_al_crear: no se permite console (puede registrar datos personales)"
    ]
    assert len(compilaciones) == 1  # solo la respuesta corregida


def test_sin_aceptacion_el_archivo_queda_como_lo_genero_la_plantilla(servicio):
    archivo = servicio / "src" / "pedido.service.ts"
    original = archivo.read_text(encoding="utf-8")
    resultado = generar_logica(
        servicio,
        _especificacion(),
        "pedido",
        _modelo().requisitos,
        _contexto(),
        LLMSimulado(_logica(), _logica()),
        intentos=2,
        compilador=lambda carpeta: ["src/pedido.service.ts(1,1): error TS1005: ';' expected."],
    )
    assert not resultado.aprobada
    assert len(resultado.intentos) == 2
    assert archivo.read_text(encoding="utf-8") == original


def test_sin_el_archivo_de_la_entidad(servicio):
    with pytest.raises(ErrorLogica, match="No se encontró src/cliente.service.ts"):
        generar_logica(servicio, _especificacion(), "cliente", [], contexto_vacio(), LLMSimulado())


# --- Comando -----------------------------------------------------------------------------------


def test_comando_logica_sin_compilar(servicio, tmp_path, monkeypatch):
    arquitectura = construir_arquitectura(_propuesta(), _modelo())
    (tmp_path / "arquitectura.json").write_text(arquitectura.model_dump_json(), encoding="utf-8")
    (tmp_path / "modelo.json").write_text(_modelo().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(
        "orchestrator.llm.crear_proveedor",
        lambda nombre=None: LLMSimulado(_logica(controles=[])),
    )

    resultado = runner.invoke(
        app,
        [
            "servicio",
            "logica",
            str(servicio),
            "--arquitectura",
            str(tmp_path / "arquitectura.json"),
            "--requisitos",
            str(tmp_path / "modelo.json"),
            "--entidad",
            "pedido",
            "--sin-graphrag",
            "--sin-compilar",
        ],
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Intento 1: aceptado" in resultado.output
    assert "src/pedido.service.ts: requisitos RF-02; pendientes 0" in resultado.output
    registro = json.loads((servicio / "logica" / "pedido.json").read_text(encoding="utf-8"))
    assert registro["aprobada"] is True
    assert "protected async reglasAlEliminar" in (servicio / "src" / "pedido.service.ts").read_text(
        encoding="utf-8"
    )
