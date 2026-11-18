"""Pruebas de la comparación de proveedores con un proveedor simulado."""

from evaluation.comparacion_llm.comparar import (
    ETIQUETAS,
    CodigoGenerado,
    RequisitoExtraido,
    cargar_requisitos,
    evaluar_proveedor,
    evaluar_requisito,
    tabla_markdown,
)
from orchestrator.llm import ErrorProveedorLLM, ErrorSalidaEstructurada


class ProveedorSimulado:
    modelos = {"rapido": "rapido-x", "razonamiento": "razonador-x"}

    def __init__(self, falla_generacion: bool = False):
        self.falla_generacion = falla_generacion

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        assert "<requisito" in prompt and sistema
        if esquema is RequisitoExtraido:
            assert nivel == "rapido"
            return RequisitoExtraido(
                id="RF-01",
                tipo="funcional",
                actor="cliente",
                accion="registrarse",
                entidades=["Usuario"],
                servicio_sugerido="usuarios",
                etiquetas=["autenticacion", "inventada"],
            )
        assert nivel == "razonamiento"
        if self.falla_generacion:
            raise ErrorSalidaEstructurada("no cumplió el esquema")
        return CodigoGenerado(nombre_archivo="x.service.ts", codigo="export class X {}")


def test_los_cinco_requisitos_usan_etiquetas_de_la_lista():
    requisitos = cargar_requisitos()
    assert len(requisitos) == 5
    for requisito in requisitos:
        assert requisito["tipo"] in {"funcional", "no_funcional"}
        assert set(requisito["etiquetas"]) <= set(ETIQUETAS)


def test_metricas_por_requisito():
    requisitos = cargar_requisitos()
    resultado = evaluar_proveedor(
        "simulado", ProveedorSimulado(), requisitos, compilar=lambda codigo: True
    )

    rf01, _, _, rnf01, _ = resultado.requisitos
    assert rf01.json_valido and rf01.tipo_correcto
    assert rf01.cobertura_etiquetas == 0.33
    assert rf01.etiquetas_fuera_de_lista == 1
    assert rf01.codigo_generado and rf01.compila is True
    assert rnf01.tipo_correcto is False
    assert resultado.modelos["razonamiento"] == "razonador-x"


def test_un_fallo_de_generacion_se_registra_sin_detener_la_prueba():
    resultado = evaluar_proveedor(
        "simulado",
        ProveedorSimulado(falla_generacion=True),
        cargar_requisitos(),
        compilar=lambda codigo: True,
    )
    assert all(not r.codigo_generado and r.compila is None for r in resultado.requisitos)
    assert all("generación" in r.errores[0] for r in resultado.requisitos)


def test_tabla_markdown():
    requisitos = cargar_requisitos()
    con_tsc = evaluar_proveedor("a", ProveedorSimulado(), requisitos, compilar=lambda c: True)
    sin_tsc = evaluar_proveedor("b", ProveedorSimulado(), requisitos, compilar=lambda c: None)
    tabla = tabla_markdown([con_tsc, sin_tsc], "2026-10-07")

    fila_a = next(linea for linea in tabla.splitlines() if linea.startswith("| a "))
    fila_b = next(linea for linea in tabla.splitlines() if linea.startswith("| b "))
    assert "| 5/5 | 3/5 |" in fila_a
    assert "| 5/5 | 5/5 |" in fila_a
    assert "no evaluado" in fila_b


class ProveedorSaturado(ProveedorSimulado):
    """Falla por saturación del servicio las primeras `fallos` llamadas."""

    def __init__(self, fallos: int):
        super().__init__()
        self.fallos = fallos

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        if self.fallos > 0:
            self.fallos -= 1
            raise ErrorProveedorLLM("error 503 de la API")
        return super().generar_estructurado(prompt, esquema, nivel, sistema)


def test_un_fallo_del_servicio_se_reintenta_y_no_cuenta_como_error():
    requisito = cargar_requisitos()[0]
    resultado = evaluar_requisito(
        ProveedorSaturado(fallos=1), requisito, compilar=lambda c: True, esperas=(0,)
    )
    assert resultado.json_valido and resultado.codigo_generado
    assert resultado.reintentos_servicio == 1
    assert resultado.errores == []


def test_un_servicio_caido_se_registra_tras_agotar_los_reintentos():
    requisito = cargar_requisitos()[0]
    resultado = evaluar_requisito(
        ProveedorSaturado(fallos=99), requisito, compilar=lambda c: True, esperas=(0, 0)
    )
    assert not resultado.json_valido and not resultado.codigo_generado
    assert resultado.reintentos_servicio == 4
    assert len(resultado.errores) == 2
