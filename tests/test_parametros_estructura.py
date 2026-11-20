"""Parámetros de la plantilla por servicio y validación de la estructura generada (#69).

orchestrator/generation/parametros.py convierte cada servicio de arquitectura.json en los
parámetros de la plantilla (nombre, base, puerto, entidades y rutas); estructura.py comprueba que lo
que genera Copier es lo que corresponde a la especificación. Sin red ni LLM.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from orchestrator.architecture import construir_arquitectura
from orchestrator.cli import app
from orchestrator.generation import (
    ARCHIVOS_DE_SEGURIDAD,
    PUERTO_BASE,
    RUTA_PLANTILLA,
    ErrorParametros,
    ErrorPlantilla,
    arbol,
    archivos_esperados,
    especificacion,
    generar_servicio,
    leer_especificacion,
    parametros_de_arquitectura,
    validar_estructura,
)
from orchestrator.llm.prompts import (
    EntidadesPropuestas,
    esquema_de_entidades,
    identificador_de_entidad,
    prompt_especificacion,
)
from orchestrator.llm.prompts.contexto import contexto_vacio
from tests.test_arquitectura import _modelo, _propuesta, _servicio

runner = CliRunner()
EJEMPLOS = RUTA_PLANTILLA / "ejemplos"


def _arquitectura(*servicios: dict):
    """Una arquitectura válida; con `servicios`, sustituye los de la propuesta de prueba."""
    cambios = {"servicios": list(servicios)} if servicios else {}
    return construir_arquitectura(_propuesta(**cambios), _modelo())


def _con_entidades(nombre: str, requisitos: list[str], entidades: list[str], depende_de=()):
    return _servicio(nombre, requisitos, depende_de) | {"entidades": entidades}


def _tienda():
    return _arquitectura(
        _con_entidades("usuarios", ["RF-01"], ["Usuario"]),
        _con_entidades("pedidos", ["RF-02"], ["Pedido", "LineaPedido"], [("usuarios", "sincrona")]),
        _con_entidades("notificaciones", ["RF-03"], ["Notificacion"], [("pedidos", "asincrona")]),
    )


def _propuesta_de(*entidades: str) -> EntidadesPropuestas:
    return EntidadesPropuestas.model_validate(
        {
            "entidades": [
                {"nombre": e, "campos": [{"nombre": "nota", "tipo": "texto", "max": 50}]}
                for e in entidades
            ]
        }
    )


# --- Nombres de las entidades ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nombre", "identificador"),
    [
        ("Pedido", "pedido"),
        ("LineaPedido", "linea_pedido"),
        ("HistoriaClinica", "historia_clinica"),
        ("Línea de pedido", "linea_de_pedido"),
        ("ImagenURLProducto", "imagen_url_producto"),
        ("item-carrito", "item_carrito"),
        ("Ñandú", "nandu"),
        ("2FA", "2_fa"),  # no es un identificador válido: lo rechazan los parámetros
    ],
)
def test_identificador_de_entidad(nombre: str, identificador: str):
    assert identificador_de_entidad(nombre) == identificador


# --- Parámetros por servicio -------------------------------------------------------------------


def test_cada_servicio_recibe_nombre_base_puerto_entidades_y_rutas():
    parametros = parametros_de_arquitectura(_tienda())

    assert [p.servicio for p in parametros.servicios] == ["usuarios", "pedidos", "notificaciones"]
    pedidos = parametros.de("pedidos")
    assert pedidos.base_datos == "pedidos_db"
    assert pedidos.puerto == PUERTO_BASE + 1 == 3002  # 3000 es el servicio de referencia
    assert pedidos.prefijo == "/api/pedidos"
    assert pedidos.audiencia == "pedidos-api"
    assert pedidos.requisitos == ("RF-02",)
    assert pedidos.nombres_de_entidades == ["pedido", "linea_pedido"]
    assert pedidos.rutas == ["/api/pedidos/pedido", "/api/pedidos/linea-pedido"]
    linea = pedidos.entidades[1]
    assert (linea.original, linea.clase, linea.archivo) == (
        "LineaPedido",
        "LineaPedido",
        "linea-pedido",
    )
    assert parametros.advertencias == ()


def test_los_puertos_son_estables_y_distintos():
    puertos = [p.puerto for p in parametros_de_arquitectura(_tienda()).servicios]
    assert puertos == [3001, 3002, 3003]


def test_un_servicio_con_guion_bajo_usa_guion_en_las_rutas():
    arquitectura = _arquitectura(
        _con_entidades("historia_clinica", ["RF-01", "RF-02", "RF-03"], ["Consulta"])
    )
    parametros = parametros_de_arquitectura(arquitectura).de("historia_clinica")
    assert parametros.prefijo == "/api/historia-clinica"
    assert parametros.rutas == ["/api/historia-clinica/consulta"]


def test_la_descripcion_queda_en_una_linea_de_300_caracteres():
    servicio = _con_entidades("pedidos", ["RF-01", "RF-02", "RF-03"], ["Pedido"])
    servicio["responsabilidad"] = "Gestiona\tlos pedidos   y " + "x" * 400
    parametros = parametros_de_arquitectura(_arquitectura(servicio)).de("pedidos")
    assert parametros.descripcion.startswith("Gestiona los pedidos y x")
    assert len(parametros.descripcion) == 300


def test_un_servicio_que_no_existe():
    with pytest.raises(KeyError, match="usa: usuarios, pedidos, notificaciones"):
        parametros_de_arquitectura(_tienda()).de("pagos")


def test_reune_todos_los_problemas_de_las_entidades():
    arquitectura = _arquitectura(
        _con_entidades("usuarios", ["RF-01"], ["2FA", "Prisma"]),
        _con_entidades("pedidos", ["RF-02", "RF-03"], ["Pedido", "pedido", "A-"]),
    )
    with pytest.raises(ErrorParametros) as error:
        parametros_de_arquitectura(arquitectura)

    problemas = error.value.problemas
    assert len(problemas) == 4
    assert "usuarios: la entidad «2FA» no da un identificador válido («2_fa»)" in problemas[0]
    assert "«Prisma» («prisma») tiene un nombre reservado" in problemas[1]
    assert "«pedido» y «Pedido» dan el mismo identificador «pedido»" in problemas[2]
    assert "«A-» no da un identificador válido («a»)" in problemas[3]


def test_dos_servicios_no_pueden_compartir_base_de_datos():
    otro = _con_entidades("pedidos", ["RF-02", "RF-03"], ["Pedido"]) | {"base_datos": "usuarios_db"}
    with pytest.raises(ErrorParametros, match="usuarios y pedidos comparten la base de datos"):
        parametros_de_arquitectura(
            _arquitectura(_con_entidades("usuarios", ["RF-01"], ["U1"]), otro)
        )


def test_una_entidad_en_dos_servicios_es_una_advertencia():
    """Cada servicio tiene su base: son tablas distintas, a menudo una proyección de lectura."""
    conectados = _arquitectura(
        _con_entidades("reservas", ["RF-01"], ["Reserva"]),
        _con_entidades(
            "pagos", ["RF-02", "RF-03"], ["Pago", "Reserva"], [("reservas", "asincrona")]
        ),
    )
    sueltos = _arquitectura(
        _con_entidades("usuarios", ["RF-01"], ["Mascota"]),
        _con_entidades("historias", ["RF-02", "RF-03"], ["Mascota"]),
    )

    (aviso,) = parametros_de_arquitectura(conectados).advertencias
    assert aviso.startswith("La entidad «reserva» está en reservas, pagos")
    assert "no hay una dependencia" not in aviso
    (aviso,) = parametros_de_arquitectura(sueltos).advertencias
    assert "no hay una dependencia declarada entre ellos" in aviso


def test_sin_entidades_en_la_arquitectura_las_propone_el_llm():
    arquitectura = _arquitectura(_con_entidades("pedidos", ["RF-01", "RF-02", "RF-03"], []))
    parametros = parametros_de_arquitectura(arquitectura)
    assert parametros.de("pedidos").entidades == ()
    assert parametros.de("pedidos").esquema_de_la_respuesta() is EntidadesPropuestas
    assert "no le asigna entidades; las propondrá el LLM" in parametros.advertencias[0]


# --- Respuesta del LLM -------------------------------------------------------------------------


def test_el_esquema_exige_las_entidades_de_la_arquitectura():
    esquema = esquema_de_entidades(["pedido", "linea_pedido"])
    datos = _propuesta_de("pedido", "linea_pedido").model_dump()
    assert esquema.model_validate(datos)

    with pytest.raises(ValidationError, match="faltan linea_pedido; sobran cliente"):
        esquema.model_validate(_propuesta_de("pedido", "cliente").model_dump())
    with pytest.raises(ValidationError, match="sobran cupon"):
        esquema.model_validate(_propuesta_de("pedido", "linea_pedido", "cupon").model_dump())


def test_el_prompt_da_los_identificadores_y_el_esquema_estricto():
    pedidos = _tienda().servicios[1]
    prompt = prompt_especificacion(pedidos, [], contexto_vacio(), codigo="a1b2c3d4")

    assert "Pedido (pedido), LineaPedido (linea_pedido)" in prompt.usuario
    with pytest.raises(ValidationError):
        prompt.esquema.model_validate(_propuesta_de("pedido").model_dump())


def test_la_especificacion_junta_la_arquitectura_y_los_campos_del_llm(tmp_path: Path):
    parametros = parametros_de_arquitectura(_tienda()).de("pedidos")
    datos = especificacion(parametros, _propuesta_de("pedido", "linea_pedido")).para_plantilla()

    assert (datos["servicio"], datos["base_datos"], datos["puerto"]) == (
        "pedidos",
        "pedidos_db",
        3002,
    )
    assert [e["nombre"] for e in datos["entidades"]] == ["pedido", "linea_pedido"]
    resultado = validar_estructura(generar_servicio(datos, tmp_path))
    assert resultado.valida, resultado.problemas
    assert resultado.rutas == parametros.rutas


def test_la_especificacion_rechaza_otras_entidades():
    parametros = parametros_de_arquitectura(_tienda()).de("pedidos")
    with pytest.raises(ValidationError, match="faltan linea_pedido"):
        especificacion(parametros, _propuesta_de("pedido"))


# --- Estructura generada -----------------------------------------------------------------------


@pytest.mark.parametrize("ejemplo", ["pedidos.yml", "todos-los-tipos.yml"])
def test_los_ejemplos_generan_la_estructura_esperada(tmp_path: Path, ejemplo: str):
    datos = leer_especificacion(EJEMPLOS / ejemplo)
    carpeta = generar_servicio(datos, tmp_path)
    resultado = validar_estructura(carpeta)

    assert resultado.valida, resultado.problemas
    assert set(resultado.archivos) == archivos_esperados(datos)
    assert set(ARCHIVOS_DE_SEGURIDAD) <= set(resultado.archivos)
    assert len(resultado.rutas) == len(datos["entidades"])


def test_los_archivos_esperados_salen_de_la_plantilla(tmp_path: Path):
    esperados = archivos_esperados(leer_especificacion(EJEMPLOS / "pedidos.yml"))
    assert ".copier-answers.yml" in esperados and "src/pedidos.module.ts" in esperados
    assert "test/pedidos.e2e-spec.ts" in esperados
    for entidad in ("pedido", "linea-pedido"):
        assert f"src/{entidad}.controller.ts" in esperados
        assert f"src/dto/crear-{entidad}.dto.ts" in esperados
    assert not any(".jinja" in a or "{" in a for a in esperados)


@pytest.fixture
def pedidos(tmp_path: Path) -> Path:
    return generar_servicio(leer_especificacion(EJEMPLOS / "pedidos.yml"), tmp_path)


def _reemplazar(carpeta: Path, archivo: str, antes: str, despues: str) -> None:
    ruta = carpeta / archivo
    texto = ruta.read_text(encoding="utf-8")
    assert antes in texto
    ruta.write_text(texto.replace(antes, despues), encoding="utf-8")


@pytest.mark.parametrize(
    ("cambio", "problema"),
    [
        (lambda c: (c / "src/seguridad/http.ts").unlink(), "Falta src/seguridad/http.ts"),
        (
            lambda c: (c / "src/puerta-trasera.ts").write_text("x", encoding="utf-8"),
            "Archivo inesperado: src/puerta-trasera.ts",
        ),
        (
            lambda c: _reemplazar(
                c, "src/pedido.controller.ts", "@Controller('pedidos/pedido')", "@Controller('x')"
            ),
            "src/pedido.controller.ts: declara ['x'], no ['pedidos/pedido']",
        ),
        (
            lambda c: _reemplazar(
                c,
                "src/pedidos.module.ts",
                "    { provide: APP_GUARD, useClass: JwtAuthGuard },\n",
                "",
            ),
            "el módulo no registra un control global",
        ),
        (
            lambda c: _reemplazar(c, "src/pedidos.module.ts", "LineaPedidoController]", "]"),
            "los controladores son ['PedidoController']",
        ),
        (
            lambda c: _reemplazar(
                c,
                "src/pedido.service.ts",
                "// @framework:logica-negocio:fin pedido",
                "",
            ),
            "la marca «// @framework:logica-negocio:fin pedido» no aparece una vez",
        ),
        (
            lambda c: _reemplazar(c, "prisma/schema.prisma", "model LineaPedido {", "model Otra {"),
            "prisma/schema.prisma: los modelos son ['Otra', 'Pedido']",
        ),
        (
            lambda c: _reemplazar(c, "Dockerfile", "USER 65532:65532", "USER root"),
            "la imagen no corre con el usuario sin privilegios",
        ),
        (
            lambda c: _reemplazar(
                c, ".env.example", "KEYCLOAK_AUDIENCE=pedidos-api", "KEYCLOAK_AUDIENCE=x"
            ),
            "la audiencia no es la del servicio",
        ),
        (
            lambda c: _reemplazar(
                c, "README.md", "# Servicio pedidos", "# Servicio {{ servicio }}"
            ),
            "README.md quedó sin renderizar",
        ),
    ],
)
def test_detecta_una_estructura_alterada(pedidos: Path, cambio, problema: str):
    cambio(pedidos)
    resultado = validar_estructura(pedidos)
    assert not resultado.valida
    assert any(problema in p for p in resultado.problemas), resultado.problemas


def test_no_cuenta_lo_que_crean_la_instalacion_y_el_llm(pedidos: Path):
    for producido in (
        "node_modules/x/a.js",
        "dist/main.js",
        "coverage/lcov.info",
        "logica/pedido.json",
        "src/generated/prisma/client.ts",
        "openapi/pedidos.json",
    ):
        (pedidos / producido).parent.mkdir(parents=True, exist_ok=True)
        (pedidos / producido).write_text("x", encoding="utf-8")
    (pedidos / ".env").write_text("DATABASE_URL=x", encoding="utf-8")
    assert validar_estructura(pedidos).valida


def test_sin_respuestas_de_copier_no_hay_especificacion(pedidos: Path):
    (pedidos / ".copier-answers.yml").unlink()
    resultado = validar_estructura(pedidos)
    assert resultado.problemas == [
        "No hay especificación: falta .copier-answers.yml o no tiene servicio y entidades"
    ]


@pytest.mark.skipif(os.name == "nt", reason="crear enlaces simbólicos en Windows exige permisos")
def test_un_enlace_simbolico_no_se_acepta(pedidos: Path):
    (pedidos / "src" / "enlace.ts").symlink_to("/etc/passwd")
    assert "src/enlace.ts es un enlace simbólico" in validar_estructura(pedidos).problemas


def test_un_archivo_de_seguridad_es_obligatorio_aunque_falte_en_la_plantilla(tmp_path: Path):
    plantilla = tmp_path / "plantilla"
    shutil.copytree(RUTA_PLANTILLA, plantilla)
    (plantilla / "plantilla" / "src" / "seguridad" / "http.ts").unlink()
    datos = leer_especificacion(EJEMPLOS / "pedidos.yml")

    with pytest.raises(ErrorPlantilla, match="Falta src/seguridad/http.ts"):
        generar_servicio(datos, tmp_path / "servicios", plantilla)
    # Un servicio que no pasa la validación no se queda en el destino.
    assert not (tmp_path / "servicios" / "pedidos").exists()


def test_arbol_de_archivos():
    texto = arbol(["b.txt", "src/a.ts", "src/dto/c.ts", "a.txt"], "svc")
    assert texto == (
        "svc/\n"
        "|-- src/\n"
        "|   |-- dto/\n"
        "|   |   `-- c.ts\n"
        "|   `-- a.ts\n"
        "|-- a.txt\n"
        "`-- b.txt\n"
        "\n"
        "2 carpetas, 4 archivos"
    )


# --- CLI --------------------------------------------------------------------------------------


@pytest.fixture
def arquitectura_json(tmp_path: Path) -> Path:
    ruta = tmp_path / "tienda.arquitectura.json"
    ruta.write_text(_tienda().model_dump_json(), encoding="utf-8")
    return ruta


def test_cli_parametros_de_cada_servicio(arquitectura_json: Path, tmp_path: Path):
    salida = tmp_path / "parametros.json"
    resultado = runner.invoke(
        app, ["servicio", "parametros", str(arquitectura_json), "--salida", str(salida)]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "3 servicios en tienda.arquitectura.json" in resultado.output
    assert "pedidos  (puerto 3002, base pedidos_db, audiencia pedidos-api)" in resultado.output
    assert "LineaPedido" in resultado.output and "/api/pedidos/linea-pedido" in resultado.output
    guardado = json.loads(salida.read_text(encoding="utf-8"))
    assert [s["servicio"] for s in guardado["servicios"]] == [
        "usuarios",
        "pedidos",
        "notificaciones",
    ]


def test_cli_parametros_explica_los_problemas(tmp_path: Path):
    ruta = tmp_path / "mal.arquitectura.json"
    arquitectura = _arquitectura(_con_entidades("pedidos", ["RF-01", "RF-02", "RF-03"], ["Prisma"]))
    ruta.write_text(arquitectura.model_dump_json(), encoding="utf-8")
    resultado = runner.invoke(app, ["servicio", "parametros", str(ruta)])
    assert resultado.exit_code == 1
    assert "tiene un nombre reservado por la plantilla" in resultado.output


def test_cli_validar(pedidos: Path):
    bien = runner.invoke(app, ["servicio", "validar", str(pedidos)])
    assert bien.exit_code == 0, bien.output
    assert "pedidos/\n|-- prisma/" in bien.output
    assert "Estructura válida" in bien.output

    (pedidos / "src" / "puerta-trasera.ts").write_text("x", encoding="utf-8")
    mal = runner.invoke(app, ["servicio", "validar", str(pedidos), "--sin-arbol"])
    assert mal.exit_code == 1
    assert "Archivo inesperado: src/puerta-trasera.ts" in mal.output
