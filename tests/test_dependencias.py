"""Lista de dependencias permitidas y su verificación automática (#66, slopsquatting).

La evidencia de la tarea es test_rechaza_un_paquete_no_permitido.
"""

import json
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.generation import ErrorLogica, generar_servicio
from orchestrator.generation import logica as modulo_logica
from orchestrator.generation.dependencias import (
    RUTA_LISTA,
    ListaPermitida,
    cargar_lista,
    main,
    satisface,
    verificar_lock,
    verificar_package_json,
    verificar_servicio,
)

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLO = RAIZ / "templates" / "microservicio_nestjs" / "ejemplos" / "pedidos.yml"
REGISTRO = "https://registry.npmjs.org/"
runner = CliRunner()


@pytest.fixture(scope="module")
def lista() -> ListaPermitida:
    return cargar_lista()


@pytest.fixture(scope="module")
def plantilla(tmp_path_factory) -> Path:
    datos = yaml.safe_load(EJEMPLO.read_text(encoding="utf-8"))
    return generar_servicio(datos, tmp_path_factory.mktemp("plantilla"))


@pytest.fixture
def package(plantilla) -> dict:
    return json.loads((plantilla / "package.json").read_text(encoding="utf-8"))


def _motivos(problemas) -> list[str]:
    return [f"{p.paquete}: {p.motivo}" for p in problemas]


# --- La lista y la plantilla -------------------------------------------------------------------


def test_la_lista_permitida_es_valida(lista):
    assert lista.ecosistema == "npm" and lista.registro == REGISTRO
    assert "@nestjs/common" in lista.rangos("dependencias")
    assert "typescript" in lista.rangos("desarrollo")
    assert all(len(p.motivo) >= 5 for p in lista.dependencias + lista.desarrollo + lista.overrides)


def test_el_servicio_de_la_plantilla_cumple_la_lista(plantilla, lista):
    """Si la plantilla añade una dependencia sin añadirla a la lista, esta prueba falla."""
    assert verificar_servicio(plantilla, lista) == []


# --- Evidencia: un paquete que no está en la lista no pasa -------------------------------------


def test_rechaza_un_paquete_no_permitido(package, lista):
    """Un paquete alucinado por el LLM (aquí, «expresss», con una «s» de más) no se acepta."""
    package["dependencies"]["expresss"] = "^4.18.2"
    problemas = verificar_package_json(package, lista)
    assert _motivos(problemas) == ["expresss: no está en la lista de dependencias permitidas"]


def test_no_se_instala_un_paquete_no_permitido(plantilla, tmp_path, monkeypatch):
    """El generador comprueba la lista antes de npm install: el paquete nunca se descarga."""
    import shutil

    servicio = Path(shutil.copytree(plantilla, tmp_path / "pedidos"))
    package = json.loads((servicio / "package.json").read_text(encoding="utf-8"))
    package["dependencies"]["nestjs-utilidades-pro"] = "^1.0.0"
    (servicio / "package.json").write_text(json.dumps(package), encoding="utf-8")

    def npm(*args, **kwargs):
        pytest.fail("no debe ejecutar npm con una dependencia no permitida")

    monkeypatch.setattr(modulo_logica, "_ejecutar", npm)
    with pytest.raises(ErrorLogica, match="nestjs-utilidades-pro: no está en la lista"):
        modulo_logica.preparar(servicio)


# --- package.json ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "version",
    [
        "github:nestjs/common",
        "git+https://github.com/nestjs/nest.git",
        "https://ejemplo.com/common-11.0.1.tgz",
        "file:../common",
        "link:../common",
        "npm:nest-common-falso@11.0.1",
        "latest",
        "*",
        "nestjs/nest",
    ],
)
def test_rechaza_versiones_que_no_pasan_por_el_registro(package, lista, version):
    package["dependencies"]["@nestjs/common"] = version
    (problema,) = verificar_package_json(package, lista)
    assert problema.paquete == "@nestjs/common"
    assert "no se descarga del registro o no fija la versión" in problema.motivo


def test_versiones_dentro_y_fuera_del_rango(package, lista):
    package["dependencies"]["helmet"] = "8.4.1"  # exacta dentro de ^8.3.0
    package["dependencies"]["rxjs"] = "^7.9.0"  # otro rango, aunque sea más estrecho
    package["dependencies"]["jose"] = "5.10.1"  # jose está fijada en 5.10.0
    assert set(_motivos(verificar_package_json(package, lista))) == {
        "rxjs: la versión «^7.9.0» no es la permitida («^7.8.1»)",
        "jose: la versión «5.10.1» no es la permitida («5.10.0»)",
    }


def test_cada_paquete_en_su_seccion(package, lista):
    package["devDependencies"]["helmet"] = "^8.3.0"
    package["overrides"]["lodash"] = "^4.17.21"
    package["overrides"]["multer"] = {"busboy": "^1.6.0"}
    assert set(_motivos(verificar_package_json(package, lista))) == {
        "helmet: no está en la lista de dependencias permitidas; "
        "solo está permitido en dependencias",
        "lodash: no está en la lista de dependencias permitidas",
        "multer: la versión debe ser un texto (sin objetos anidados)",
    }


def test_sin_scripts_de_instalacion_ni_secciones_extra(package, lista):
    package["scripts"]["postinstall"] = "node instalar.js"
    package["scripts"]["prepare"] = "husky install"
    package["optionalDependencies"] = {"fsevents": "^2.3.3"}
    problemas = verificar_package_json(package, lista)
    assert [(p.seccion, p.paquete) for p in problemas] == [
        ("optionalDependencies", None),
        ("scripts", "postinstall"),
        ("scripts", "prepare"),
    ]


# --- package-lock.json -------------------------------------------------------------------------


def _lock(**paquetes) -> dict:
    base = {
        "": {"dependencies": {"helmet": "^8.3.0"}, "devDependencies": {"typescript": "^5.7.3"}},
        "node_modules/helmet": {
            "version": "8.3.0",
            "resolved": f"{REGISTRO}helmet/-/helmet-8.3.0.tgz",
            "integrity": "sha512-abc",
        },
        "node_modules/typescript": {
            "version": "5.9.2",
            "resolved": f"{REGISTRO}typescript/-/typescript-5.9.2.tgz",
            "integrity": "sha512-def",
        },
    }
    return {"lockfileVersion": 3, "packages": base | paquetes}


def test_un_lock_correcto_no_tiene_problemas(lista):
    assert verificar_lock(_lock(), lista) == []


def test_el_lock_detecta_origen_integridad_enlaces_y_versiones(lista):
    datos = _lock(
        **{
            "node_modules/helmet": {
                "version": "9.0.0",
                "resolved": f"{REGISTRO}helmet/-/helmet-9.0.0.tgz",
                "integrity": "sha512-x",
            },
            "node_modules/a/node_modules/b": {
                "version": "1.0.0",
                "resolved": "https://registro-falso.example/b/-/b-1.0.0.tgz",
                "integrity": "sha1-viejo",
            },
            "node_modules/local": {"link": True, "resolved": "../local"},
        }
    )
    assert _motivos(verificar_lock(datos, lista)) == [
        "helmet: la versión instalada 9.0.0 no está en el rango permitido «^8.3.0»",
        "b: se descarga de fuera del registro permitido (registro-falso.example)",
        "b: no tiene huella de integridad sha512",
        "local: se enlaza desde el disco en lugar de descargarse del registro",
    ]


def test_un_lock_antiguo_no_se_acepta(lista):
    (problema,) = verificar_lock({"lockfileVersion": 1, "dependencies": {}}, lista)
    assert "lockfileVersion 2 o 3" in problema.motivo


# --- Rangos de versiones -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("version", "rango", "esperado"),
    [
        ("11.4.2", "^11.0.1", True),
        ("12.0.0", "^11.0.1", False),
        ("11.0.0", "^11.0.1", False),
        ("0.5.9", "^0.5.1", True),
        ("0.6.0", "^0.5.1", False),
        ("0.0.4", "^0.0.3", False),
        ("10.9.9", "~10.9.2", True),
        ("10.10.0", "~10.9.2", False),
        ("5.10.0", "5.10.0", True),
        ("5.10.1", "5.10.0", False),
        ("2.1.0", ">=2.0.0 <3.0.0", True),
        ("3.0.0", ">=2.0.0 <3.0.0", False),
        ("1.5.0", "^1.0.0 || ^2.0.0", True),
        ("12.0.0-beta.1", "^11.0.1", False),
        ("11.1.0-rc.1", "^11.0.1", False),  # una preliminar solo si el rango la nombra
        ("no-es-version", "^1.0.0", False),
    ],
)
def test_rangos_de_npm(version, rango, esperado):
    assert satisface(version, rango) is esperado


@pytest.mark.parametrize(
    ("paquete", "mensaje"),
    [
        ({"paquete": "Express", "version": "^4.0.0", "motivo": "motivo"}, "nombre de paquete"),
        ({"paquete": "express", "version": "latest", "motivo": "motivo"}, "rango de versiones"),
        ({"paquete": "express", "version": "github:x/y", "motivo": "motivo"}, "rango de versiones"),
        ({"paquete": "express", "version": "^4.0.0", "motivo": "x"}, "at least 5"),
    ],
)
def test_la_lista_rechaza_entradas_invalidas(paquete, mensaje):
    with pytest.raises(ValueError, match=mensaje):
        ListaPermitida.model_validate(
            {
                "version": "1",
                "ecosistema": "npm",
                "registro": REGISTRO,
                "dependencias": [paquete],
                "desarrollo": [],
            }
        )


def test_la_lista_rechaza_repetidos():
    paquete = {"paquete": "helmet", "version": "^8.3.0", "motivo": "cabeceras"}
    with pytest.raises(ValueError, match="repetidos en dependencias"):
        ListaPermitida.model_validate(
            {
                "version": "1",
                "ecosistema": "npm",
                "registro": REGISTRO,
                "dependencias": [paquete, paquete],
                "desarrollo": [],
            }
        )


# --- Comando y script --------------------------------------------------------------------------


def test_comando_dependencias(plantilla, tmp_path):
    resultado = runner.invoke(app, ["servicio", "dependencias", str(plantilla)])
    assert resultado.exit_code == 0, resultado.output
    assert "todas las dependencias están en la lista permitida" in resultado.output

    package = json.loads((plantilla / "package.json").read_text(encoding="utf-8"))
    package["dependencies"]["expresss"] = "^4.18.2"
    (tmp_path / "package.json").write_text(json.dumps(package), encoding="utf-8")
    resultado = runner.invoke(app, ["servicio", "dependencias", str(tmp_path)])
    assert resultado.exit_code == 1
    assert "expresss: no está en la lista de dependencias permitidas" in resultado.output


def test_script_para_el_ci(plantilla, tmp_path, capsys):
    assert main([str(plantilla)]) == 0
    # La plantilla genera también el package-lock.json, que se revisa con el package.json.
    salida = capsys.readouterr().out
    assert "package.json y package-lock.json cumplen la lista de dependencias permitidas" in salida
    assert main([str(tmp_path)]) == 2  # sin package.json
    assert main([]) == 2


def test_la_lista_esta_en_la_base_de_conocimiento():
    assert RUTA_LISTA == RAIZ / "knowledge_base" / "dependencias_permitidas.yaml"
