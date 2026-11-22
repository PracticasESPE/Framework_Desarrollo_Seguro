"""Generador de las pruebas Jest de la lógica de negocio con el LLM (fase 3).

El LLM y Jest se simulan: las pruebas no necesitan red ni Node.js.
"""

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.generation import generar_pruebas, generar_servicio
from orchestrator.generation.pruebas import (
    ResultadoJest,
    archivo_de_pruebas,
    leer_informe,
    problemas_de_las_pruebas,
    problemas_del_caso,
)
from orchestrator.llm.prompts import (
    CasoPrueba,
    EspecificacionServicio,
    LogicaEntidad,
    PruebasEntidad,
    prompt_pruebas,
)
from tests.test_arquitectura import _modelo

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLO = RAIZ / "templates" / "microservicio_nestjs" / "ejemplos" / "pedidos.yml"
runner = CliRunner()

CUERPO = (
    "prisma.lineaPedido.count.mockResolvedValue(2);\n"
    "await expect(reglas.reglasAlEliminar({ id: 'x' } as unknown as Pedido)).rejects"
    ".toBeInstanceOf(ConflictException);"
)
LOGICA = LogicaEntidad(
    reglas_al_crear="",
    reglas_al_actualizar="",
    reglas_al_eliminar=(
        "const n = await this.prisma.lineaPedido.count({ where: { pedidoId: actual.id } });\n"
        "if (n > 0) { throw new ConflictException('Tiene líneas'); }"
    ),
    requisitos=["RF-02"],
    controles=[],
    pendientes=["Avisar por correo al cliente"],
)


def _especificacion() -> EspecificacionServicio:
    return EspecificacionServicio.model_validate(
        yaml.safe_load(EJEMPLO.read_text(encoding="utf-8"))
    )


def _caso(nombre="rechaza borrar un pedido con líneas", cuerpo=CUERPO, requisito="RF-02"):
    return CasoPrueba(nombre=nombre, metodo="reglasAlEliminar", requisito=requisito, cuerpo=cuerpo)


def _pruebas(*casos) -> PruebasEntidad:
    return PruebasEntidad(casos=list(casos) or [_caso()])


def _jest(*estados, error=None) -> ResultadoJest:
    return ResultadoJest(
        error_de_compilacion=error,
        estados={
            n: (e, None if e == "passed" else f"Expected X, received Y ({n})")
            for n, e in enumerate(estados, 1)
        },
    )


class LLMSimulado:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.prompts: list[str] = []

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        self.prompts.append(prompt)
        return self.respuestas.pop(0)


@pytest.fixture
def servicio(tmp_path) -> Path:
    datos = yaml.safe_load(EJEMPLO.read_text(encoding="utf-8"))
    return generar_servicio(datos, tmp_path)


# --- Análisis de los casos ---------------------------------------------------------------------


def test_un_caso_con_el_doble_de_prisma_pasa():
    assert problemas_del_caso(_caso()) == []


@pytest.mark.parametrize(
    ("cuerpo", "motivo"),
    [
        ("jest.mock('../prisma.service'); expect(1).toBe(1);", "sustituir módulos"),
        ("const m = jest.requireActual('fs'); expect(m).toBeDefined();", "sustituir módulos"),
        ("it('otro', async () => { expect(1).toBe(1); });", "anidados"),
        ("describe.skip('x', () => undefined); expect(1).toBe(1);", "anidados"),
        ("import fs from 'fs'; expect(fs).toBeDefined();", "import"),
        ("console.log(reglas); expect(1).toBe(1);", "console"),
        ("expect(process.env.CLAVE).toBeUndefined();", "process"),
        ("}); it('escapa', async () => { expect(1).toBe(1);", "cierra más llaves"),
    ],
)
def test_el_analisis_rechaza_lo_peligroso_en_las_pruebas(cuerpo, motivo):
    problemas = problemas_del_caso(_caso(cuerpo=cuerpo))
    assert any(motivo in p for p in problemas), problemas


def test_el_requisito_de_cada_caso_lo_implementa_el_codigo():
    problemas = problemas_de_las_pruebas(_pruebas(_caso(requisito="RF-99")), {"RF-02"})
    assert problemas == [
        "caso 1 («rechaza borrar un pedido con líneas»): el código no implementa RF-99"
    ]


# --- Archivo -----------------------------------------------------------------------------------


def test_el_motor_arma_el_archivo_y_el_llm_solo_aporta_los_cuerpos():
    with pytest.raises(ValueError):  # el esquema ya no admite saltos de línea en el nombre
        _caso(nombre="el pedido \n  });  it('otro")
    caso = _caso(nombre="el cliente's pedido no se borra")
    texto = archivo_de_pruebas(_especificacion(), "pedido", [(1, caso)])
    assert "import { PedidoService } from './pedido.service';" in texto
    assert "import type { CrearPedidoDto } from './dto/crear-pedido.dto';" in texto
    assert "import type { Pedido } from './generated/prisma/client';" in texto
    assert "  lineaPedido: { findUnique: jest.fn(), findFirst: jest.fn()," in texto
    assert "  reglasAlEliminar(actual: Pedido): Promise<void>;" in texto
    # El nombre del caso es un literal seguro: sin saltos de línea y con la comilla escapada.
    assert "  it('01. el cliente\\'s pedido no se borra (RF-02)', async () => {" in texto
    assert "    prisma.lineaPedido.count.mockResolvedValue(2);" in texto
    assert texto.count("describe(") == 1


def test_leer_el_informe_de_jest():
    informe = {
        "testResults": [
            {
                "status": "failed",
                "message": "",
                "assertionResults": [
                    {"title": "01. pasa (RF-02)", "status": "passed", "failureMessages": []},
                    {"title": "02. falla", "status": "failed", "failureMessages": ["Expected 1"]},
                ],
            }
        ]
    }
    resultado = leer_informe(informe)
    assert resultado.error_de_compilacion is None
    assert resultado.estados == {1: ("passed", None), 2: ("failed", "Expected 1")}

    sin_compilar = leer_informe(
        {
            "testResults": [
                {
                    "status": "failed",
                    "message": "TS2339: Property 'x' does not exist",
                    "assertionResults": [],
                }
            ]
        }
    )
    assert "TS2339" in sin_compilar.error_de_compilacion


# --- Generador ---------------------------------------------------------------------------------


def _generar(servicio, llm, ejecutor, intentos=3):
    return generar_pruebas(
        servicio,
        _especificacion(),
        "pedido",
        LOGICA,
        _modelo().requisitos[1:2],
        llm,
        intentos=intentos,
        ejecutor=ejecutor,
    )


def test_aceptadas_al_primer_intento(servicio):
    ejecuciones = []

    def ejecutor(carpeta, archivo):
        ejecuciones.append(archivo)
        return _jest("passed")

    resultado = _generar(servicio, LLMSimulado(_pruebas()), ejecutor)
    assert (resultado.aceptadas, resultado.descartadas) == (1, [])
    assert ejecuciones == ["src/pedido.reglas.spec.ts"]
    assert (servicio / "src" / "pedido.reglas.spec.ts").is_file()
    assert len(resultado.huella_prompt) == 64


def test_los_fallos_de_jest_vuelven_al_llm(servicio):
    resultados = iter([_jest("failed"), _jest("passed")])
    llm = LLMSimulado(_pruebas(), _pruebas())
    resultado = _generar(servicio, llm, lambda c, a: next(resultados))
    assert resultado.aceptadas == 1 and len(resultado.intentos) == 2
    rechazo = llm.prompts[1].split("se rechazaron por estos motivos")[1]
    assert (
        "falla el caso «rechaza borrar un pedido con líneas»: Expected X, received Y (1)" in rechazo
    )


def test_un_archivo_que_no_compila_vuelve_con_el_error(servicio):
    resultados = iter([_jest(error="TS2339: Property 'pedidoID' does not exist"), _jest("passed")])
    llm = LLMSimulado(_pruebas(), _pruebas())
    resultado = _generar(servicio, llm, lambda c, a: next(resultados))
    assert resultado.aceptadas == 1
    assert "no compila o no se ejecuta: TS2339" in llm.prompts[1]


def test_los_casos_que_siguen_fallando_se_descartan_y_quedan_registrados(servicio):
    dos = _pruebas(_caso(), _caso(nombre="permite borrar un pedido sin líneas"))
    resultados = iter([_jest("passed", "failed"), _jest("passed", "failed"), _jest("passed")])
    resultado = _generar(servicio, LLMSimulado(dos, dos), lambda c, a: next(resultados), intentos=2)

    assert resultado.aceptadas == 1
    assert [c.nombre for c in resultado.descartadas] == ["permite borrar un pedido sin líneas"]
    assert resultado.descartadas[0].error == "Expected X, received Y (2)"
    contenido = (servicio / "src" / "pedido.reglas.spec.ts").read_text(encoding="utf-8")
    assert "permite borrar" not in contenido and "01. rechaza borrar" in contenido
    assert len(resultado.intentos) == 3  # dos intentos y la confirmación sin el caso que falla


def test_si_nada_pasa_no_queda_archivo(servicio):
    resultado = _generar(
        servicio,
        LLMSimulado(_pruebas(), _pruebas()),
        lambda c, a: _jest(error="SyntaxError"),
        intentos=2,
    )
    assert resultado.aceptadas == 0
    assert not (servicio / "src" / "pedido.reglas.spec.ts").exists()


def test_un_problema_del_analisis_no_llega_a_jest(servicio):
    ejecuciones = []

    def ejecutor(carpeta, archivo):
        ejecuciones.append(archivo)
        return _jest("passed")

    malo = _pruebas(_caso(cuerpo="jest.mock('./prisma.service'); expect(1).toBe(1);"))
    resultado = _generar(servicio, LLMSimulado(malo, _pruebas()), ejecutor)
    assert resultado.aceptadas == 1
    assert resultado.intentos[0].problemas and len(ejecuciones) == 1


# --- Prompt ------------------------------------------------------------------------------------


def test_el_prompt_lleva_el_codigo_los_requisitos_y_los_pendientes():
    prompt = prompt_pruebas(
        _especificacion(), "pedido", LOGICA, _modelo().requisitos[1:2], "a1b2c3d4"
    )
    assert prompt.nombre == "pruebas" and prompt.nivel == "razonamiento"
    assert "<codigo-a1b2c3d4>" in prompt.usuario
    assert "async reglasAlEliminar(actual) {" in prompt.usuario
    assert "// sin reglas: no hay nada que probar" in prompt.usuario
    assert "- Avisar por correo al cliente" in prompt.usuario
    assert "Tipos disponibles: CrearPedidoDto, ActualizarPedidoDto y Pedido." in prompt.usuario
    assert "- prisma.lineaPedido: pedidoId, productoId" in prompt.usuario
    assert "sin jest.mock" in prompt.sistema
    with pytest.raises(ValueError, match="no tiene la entidad cliente"):
        prompt_pruebas(_especificacion(), "cliente", LOGICA, [])


# --- Comando -----------------------------------------------------------------------------------


def test_comando_pruebas(servicio, tmp_path, monkeypatch):
    from orchestrator.generation import ResultadoLogica
    from orchestrator.generation import pruebas as modulo

    (servicio / "logica").mkdir()
    registro = ResultadoLogica(
        servicio="pedidos",
        entidad="pedido",
        archivo="src/pedido.service.ts",
        aprobada=True,
        huella_prompt="0" * 64,
        intentos=[],
        logica=LOGICA,
    )
    (servicio / "logica" / "pedido.json").write_text(registro.model_dump_json(), encoding="utf-8")
    (tmp_path / "modelo.json").write_text(_modelo().model_dump_json(), encoding="utf-8")
    monkeypatch.setattr("orchestrator.generation.preparar", lambda carpeta: None)
    monkeypatch.setattr(
        "orchestrator.llm.crear_proveedor", lambda nombre=None: LLMSimulado(_pruebas())
    )
    original = modulo.generar_pruebas
    monkeypatch.setattr(
        "orchestrator.generation.generar_pruebas",
        lambda *a, **k: original(*a, **k, ejecutor=lambda c, r: _jest("passed")),
    )

    resultado = runner.invoke(
        app, ["servicio", "pruebas", str(servicio), "--requisitos", str(tmp_path / "modelo.json")]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Intento 1: 1/1 casos pasan" in resultado.output
    assert "src/pedido.reglas.spec.ts: 1 pruebas" in resultado.output
    guardado = json.loads((servicio / "pruebas" / "pedido.json").read_text(encoding="utf-8"))
    assert guardado["aceptadas"] == 1


def test_comando_pruebas_sin_logica(servicio, tmp_path):
    (tmp_path / "modelo.json").write_text(_modelo().model_dump_json(), encoding="utf-8")
    resultado = runner.invoke(
        app,
        [
            "servicio",
            "pruebas",
            str(servicio),
            "--requisitos",
            str(tmp_path / "modelo.json"),
            "--entidad",
            "pedido",
        ],
    )
    assert resultado.exit_code == 1
    assert "ejecuta antes «servicio logica»" in resultado.output
