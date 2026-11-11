"""Normalización del texto, unidades de requisito y esquema Pydantic Requisito (fase 1).

La segmentación se mide con el dataset de evaluación: cada requisito de la referencia debe caer en
una sola unidad y, cuando la referencia da una ubicación «sección.punto», en esa misma. La
referencia solo la leen estas pruebas, nunca el framework.
"""

import json
import os
import re
from functools import cache
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.ingest import (
    ClasificacionRequisito,
    ModeloRequisitos,
    Requisito,
    UnidadTexto,
    construir_requisitos,
    extraer_markdown,
    normalizar_texto,
    segmentar,
)
from orchestrator.ingest.normalizacion import LARGO_MAXIMO_UNIDAD
from orchestrator.ingest.requisito import Etiqueta

DATASETS = Path(__file__).resolve().parent.parent / "evaluation" / "datasets"
DOCUMENTOS = sorted(p.parent for p in DATASETS.glob("*/referencia.yaml"))
runner = CliRunner()


def _normalizar(texto: str) -> str:
    return " ".join(texto.split())


def _referencia(carpeta: Path) -> dict:
    return yaml.safe_load((carpeta / "referencia.yaml").read_text(encoding="utf-8"))


@cache
def _unidades(carpeta: Path, formato: str) -> list[UnidadTexto]:
    """Una sola extracción por documento y formato en toda la sesión de pruebas."""
    return segmentar(extraer_markdown(carpeta / f"requisitos.{formato}").markdown)


# --- Normalización ---------------------------------------------------------------------------


def test_normalizar_espacios_y_unicode():
    # «é» escrita como «e» + tilde combinada, espacio no separable, tabulador y espacio fino.
    resultado = normalizar_texto("Cafe\u0301\u00a0con\tleche\u2009 y  pan  \r\n\r\nfin")
    assert resultado.texto == "Café con leche y pan\n\nfin\n"
    assert resultado.invisibles_eliminados == 0


def test_normalizar_elimina_y_cuenta_los_invisibles():
    # Ancho cero, guion opcional y un control de dirección (técnica Trojan Source).
    texto = "El cliente\u200b puede\u00ad pagar\u202e con tarjeta\x07."
    resultado = normalizar_texto(texto)
    assert resultado.texto == "El cliente puede pagar con tarjeta.\n"
    assert resultado.invisibles_eliminados == 3


# --- Segmentación ----------------------------------------------------------------------------

EJEMPLO = """\
# Tienda: documento de requisitos

Versión 1.0.

## 2. Usuarios

| Usuario | Quién es |
|---|---|
| Cliente | Persona registrada |

## 3. Cuenta del cliente

1. El cliente se registra con su correo.

2. El cliente entra con su contraseña
y la cuenta se bloquea tras cinco intentos.

## 10. Fuera del alcance

- Una aplicación móvil.
- Envíos internacionales.
"""


def test_segmentar_reconoce_cada_bloque_con_su_ubicacion():
    unidades = segmentar(EJEMPLO)
    assert [(u.ubicacion, u.bloque) for u in unidades] == [
        ("0, párrafo 1", "parrafo"),
        ("2, tabla 1", "tabla"),
        ("3.1", "lista"),
        ("3.2", "lista"),
        ("10, viñeta 1", "vineta"),
        ("10, viñeta 2", "vineta"),
    ]
    # Una línea partida (como en un PDF) sigue siendo el mismo punto.
    assert unidades[3].texto == (
        "El cliente entra con su contraseña y la cuenta se bloquea tras cinco intentos."
    )
    assert unidades[1].texto == "Usuario | Quién es\nCliente | Persona registrada"
    assert unidades[2].titulo_seccion == "Cuenta del cliente"


def test_segmentar_texto_sin_marcas_de_titulo():
    """En un TXT, «3. Cuenta» aislada es un título y «1. El cliente...» un punto de la lista."""
    texto = "Tienda\n\n3. Cuenta del cliente\n\n1. El cliente se registra.\n2. El cliente paga.\n"
    unidades = segmentar(texto)
    assert [(u.ubicacion, u.seccion, u.texto) for u in unidades] == [
        ("3.1", "3", "El cliente se registra."),
        ("3.2", "3", "El cliente paga."),
    ]


def test_una_conversacion_no_toma_las_preguntas_como_titulos():
    texto = (
        "Reunión con el cliente\n\n"
        "Analista: ¿Quiénes usarían el sistema?\n\n"
        "Cliente: Los jugadores y la recepción.\n\n"
        "Analista: ¡Perfecto!\n\n"
        "Cliente: Cada jugador ve solo sus reservas.\n"
    )
    unidades = segmentar(texto)
    assert [(u.ubicacion, u.titulo_seccion) for u in unidades] == [
        ("0, párrafo 1", "Reunión con el cliente"),
        ("0, párrafo 2", "Reunión con el cliente"),
        ("0, párrafo 3", "Reunión con el cliente"),
        ("0, párrafo 4", "Reunión con el cliente"),
    ]
    assert unidades[0].texto == "Analista: ¿Quiénes usarían el sistema?"


def test_titulos_sin_numero_no_repiten_ubicaciones():
    texto = "Inicio\n\nPrimer párrafo.\n\nOtro tema\n\nSegundo párrafo.\n\n3. Cuenta\n\n1. Uno.\n"
    unidades = segmentar(texto)
    assert [(u.ubicacion, u.titulo_seccion) for u in unidades] == [
        ("0, párrafo 1", "Inicio"),
        ("0, párrafo 2", "Otro tema"),
        ("3.1", "Cuenta"),
    ]


def test_un_texto_sin_estructura_se_divide_en_oraciones():
    """Un correo de un solo párrafo mezcla varios requisitos: cada oración es una unidad."""
    oraciones = [
        "bueno te cuento rapido porque estoy entre consultas jaja.",
        "queremos que el dueño se registre con su mail y una contraseña.",
        "la historia clinica la ven solo los veterinarios, no la recepcionista!",
        "si alguien se olvida la clave que le llegue un link al mail?",
        "cualquier cosa me mandas un audio",
    ]
    relleno = " ".join(["los turnos son de media hora y atendemos de lunes a sabado."] * 8)
    texto = " ".join([*oraciones[:4], relleno, oraciones[4]])
    assert len(texto) > LARGO_MAXIMO_UNIDAD

    unidades = segmentar(texto + "\n")

    assert len(unidades) == 4 + 8 + 1
    assert [u.texto for u in unidades[:4]] == oraciones[:4]
    assert unidades[-1].texto == oraciones[4]
    assert unidades[0].ubicacion == "0, párrafo 1, oración 1"
    assert unidades[-1].ubicacion == "0, párrafo 1, oración 13"
    assert {u.bloque for u in unidades} == {"parrafo"}
    assert all(len(u.texto) <= LARGO_MAXIMO_UNIDAD for u in unidades)
    # Juntas siguen siendo el texto original, sin perder ni cambiar palabras.
    assert " ".join(u.texto for u in unidades) == texto


def test_un_bloque_corto_no_se_divide():
    texto = "El cliente se registra. Después confirma su correo. Luego entra."
    assert [u.ubicacion for u in segmentar(texto + "\n")] == ["0, párrafo 1"]


@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda c: c.name)
def test_los_formatos_dan_las_mismas_unidades(carpeta):
    def clave(unidades):
        return [(u.ubicacion, u.bloque, _normalizar(u.texto)) for u in unidades]

    fuente = clave(_unidades(carpeta, "md"))
    assert clave(_unidades(carpeta, "txt")) == fuente
    assert clave(_unidades(carpeta, "docx")) == fuente


@pytest.mark.parametrize("formato", ["md", "txt", "docx"])
@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda c: c.name)
def test_cada_requisito_de_la_referencia_esta_en_una_unidad(carpeta, formato):
    unidades = _unidades(carpeta, formato)
    assert len({u.ubicacion for u in unidades}) == len(unidades), "ubicaciones repetidas"
    for requisito in _referencia(carpeta)["requisitos"]:
        coinciden = [u for u in unidades if _normalizar(requisito["texto"]) in u.texto]
        assert len(coinciden) == 1, requisito["id"]
        if re.fullmatch(r"\d+\.\d+", requisito["ubicacion"]):
            assert coinciden[0].ubicacion == requisito["ubicacion"], requisito["id"]


@pytest.mark.skipif(os.environ.get("DOCLING_PDF") != "1", reason="Lento: DOCLING_PDF=1")
@pytest.mark.parametrize("carpeta", DOCUMENTOS, ids=lambda c: c.name)
def test_el_pdf_da_las_mismas_unidades(carpeta):
    def clave(unidades):
        return [(u.ubicacion, u.bloque, _normalizar(u.texto)) for u in unidades]

    assert clave(_unidades(carpeta, "pdf")) == clave(_unidades(carpeta, "md"))


# --- Esquema Requisito -----------------------------------------------------------------------

UNIDAD = UnidadTexto(
    ubicacion="3.1",
    seccion="3",
    titulo_seccion="Cuenta del cliente",
    bloque="lista",
    texto="El cliente debe poder registrarse con su correo electrónico y una contraseña.",
)
CLASIFICACION = {
    "es_requisito": True,
    "tipo": "funcional",
    "actor": "cliente",
    "accion": "registrarse con correo",
    "entidades": ["Usuario", "usuario", "Cuenta"],
    "servicio_sugerido": "usuarios",
    "etiquetas": ["autenticacion", "hash_password", "autenticacion"],
}


def test_las_etiquetas_son_las_del_vocabulario_del_dataset():
    vocabulario = yaml.safe_load((DATASETS / "vocabulario.yaml").read_text(encoding="utf-8"))
    assert list(Etiqueta.__args__) == vocabulario["etiquetas"]
    assert (
        list(ClasificacionRequisito.model_fields["tipo"].annotation.__args__[0].__args__)
        == (vocabulario["tipos"])
    )


def test_construir_requisito_desde_unidad_y_clasificacion():
    clasificacion = ClasificacionRequisito.model_validate(CLASIFICACION)
    [requisito] = construir_requisitos([(UNIDAD, clasificacion)])

    assert requisito.id == "RF-01"
    assert requisito.texto == UNIDAD.texto  # el texto es el del documento, no el del LLM
    assert requisito.ubicacion == "3.1"
    assert requisito.entidades == ["Usuario", "Cuenta"]
    assert requisito.etiquetas == ["autenticacion", "hash_password"]


def test_numeracion_por_tipo_y_unidades_descartadas():
    def clasificacion(**cambios):
        return ClasificacionRequisito.model_validate(CLASIFICACION | cambios)

    tabla = UNIDAD.model_copy(update={"bloque": "tabla", "ubicacion": "2, tabla 1"})
    pares = [
        (UNIDAD, clasificacion()),
        (UNIDAD.model_copy(update={"ubicacion": "9.1"}), clasificacion(tipo="no_funcional")),
        (
            UNIDAD.model_copy(update={"ubicacion": "1, párrafo 1"}),
            clasificacion(es_requisito=False),
        ),
        (tabla, clasificacion()),  # las tablas solo dan contexto
        (UNIDAD.model_copy(update={"ubicacion": "3.2"}), clasificacion()),
    ]
    assert [(r.id, r.ubicacion) for r in construir_requisitos(pares)] == [
        ("RF-01", "3.1"),
        ("RNF-01", "9.1"),
        ("RF-02", "3.2"),
    ]


@pytest.mark.parametrize(
    ("cambios", "error"),
    [
        ({"tipo": None}, "Un requisito necesita tipo"),
        ({"actor": "", "servicio_sugerido": None}, "actor"),
        ({"etiquetas": ["sql_injection"]}, "etiquetas"),
        ({"servicio_sugerido": "Pedidos y Pagos"}, "servicio_sugerido"),
        ({"accion": "x" * 201}, "accion"),
        ({"prioridad": "alta"}, "Extra inputs are not permitted"),
    ],
)
def test_la_clasificacion_rechaza_salidas_incompletas_o_fuera_de_lista(cambios, error):
    with pytest.raises(ValidationError, match=error):
        ClasificacionRequisito.model_validate(CLASIFICACION | cambios)


def test_una_unidad_que_no_es_requisito_no_necesita_mas_campos():
    assert not ClasificacionRequisito(es_requisito=False).es_requisito


def test_listas_nulas_del_llm_son_listas_vacias():
    clasificacion = ClasificacionRequisito.model_validate_json(
        '{"es_requisito": false, "entidades": null, "etiquetas": null}'
    )
    assert (clasificacion.entidades, clasificacion.etiquetas) == ([], [])


def _requisito(**cambios) -> dict:
    base = {k: v for k, v in CLASIFICACION.items() if k != "es_requisito"}
    return base | {"id": "RF-01", "texto": UNIDAD.texto, "ubicacion": "3.1"} | cambios


@pytest.mark.parametrize(
    ("cambios", "error"),
    [
        ({"id": "RNF-01"}, "no corresponde a un requisito funcional"),
        ({"id": "R-1"}, "id"),
        ({"texto": "corto"}, "texto"),
        ({"entidades": ["x"] * 16}, "entidades"),
    ],
)
def test_el_requisito_valida_id_texto_y_listas(cambios, error):
    with pytest.raises(ValidationError, match=error):
        Requisito.model_validate(_requisito(**cambios))


def test_modelo_de_requisitos_rechaza_ids_repetidos_y_vacio():
    documento = {"nombre": "requisitos.pdf", "sha256": "a" * 64, "herramienta": "docling 2.148.0"}
    with pytest.raises(ValidationError, match="Ids repetidos: RF-01"):
        ModeloRequisitos(documento=documento, requisitos=[_requisito(), _requisito()])
    with pytest.raises(ValidationError, match="requisitos"):
        ModeloRequisitos(documento=documento, requisitos=[])

    modelo = ModeloRequisitos(documento=documento, requisitos=[_requisito()])
    copia = ModeloRequisitos.model_validate_json(modelo.model_dump_json())
    assert copia == modelo
    assert copia.version_esquema == "1.0"


# --- CLI -------------------------------------------------------------------------------------


def test_comando_normalizar_guarda_las_unidades(tmp_path):
    origen = DOCUMENTOS[1] / "requisitos.txt"
    resultado = runner.invoke(
        app, ["requisitos", "normalizar", str(origen), "--destino", str(tmp_path)]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Unidades: 49 (lista: 33, parrafo: 6, tabla: 2, vineta: 8)" in resultado.output
    guardado = json.loads((tmp_path / "requisitos-txt.unidades.json").read_text("utf-8"))
    assert guardado["documento"]["formato"] == "txt"
    assert guardado["unidades"][0]["ubicacion"] == "0, párrafo 1"


def test_comando_normalizar_avisa_de_invisibles(tmp_path):
    ruta = tmp_path / "requisitos.md"
    ruta.write_text("## 1. Cuentas\n\n1. El cliente\u200b se registra.\n", encoding="utf-8")
    resultado = runner.invoke(
        app, ["requisitos", "normalizar", str(ruta), "--destino", str(tmp_path)]
    )
    assert resultado.exit_code == 0, resultado.output
    assert "se eliminaron 1 caracteres invisibles" in resultado.output


def test_el_esquema_publicado_esta_al_dia():
    """docs/esquemas lo consumen el dashboard y la API: si cambia el modelo, hay que regenerarlo
    con «uv run framework requisitos esquema --salida docs/esquemas/modelo_requisitos.schema.json».
    """
    publicado = DATASETS.parent.parent / "docs" / "esquemas" / "modelo_requisitos.schema.json"
    assert json.loads(publicado.read_text("utf-8")) == ModeloRequisitos.model_json_schema()


def test_comando_esquema(tmp_path):
    resultado = runner.invoke(app, ["requisitos", "esquema"])
    assert resultado.exit_code == 0
    esquema = json.loads(resultado.output)
    assert esquema["title"] == "ModeloRequisitos"
    assert "Requisito" in esquema["$defs"]

    destino = tmp_path / "esquema.json"
    resultado = runner.invoke(app, ["requisitos", "esquema", "--salida", str(destino)])
    assert resultado.exit_code == 0
    assert json.loads(destino.read_text("utf-8")) == esquema
