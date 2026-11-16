"""Pruebas de la plantilla Copier del microservicio NestJS (parte 1: módulo, Prisma y DTO, #61).

Generan servicios en carpetas temporales y comprueban el resultado como texto. Que el servicio
generado compile (npm install, prisma generate y tsc) se comprueba aparte, porque necesita Node y
descargar las dependencias: ver templates/microservicio_nestjs/README.md.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.generation import (
    RUTA_PLANTILLA,
    ErrorPlantilla,
    generar_servicio,
    leer_especificacion,
)

runner = CliRunner()
EJEMPLO = RUTA_PLANTILLA / "ejemplos" / "pedidos.yml"


@pytest.fixture
def ejemplo() -> dict:
    return leer_especificacion(EJEMPLO)


def _generar(tmp_path: Path, datos: dict) -> Path:
    return generar_servicio(datos, tmp_path)


def _leer(carpeta: Path, ruta: str) -> str:
    return (carpeta / ruta).read_text(encoding="utf-8")


def _campo(datos: dict, entidad: int, campo: int) -> dict:
    return datos["entidades"][entidad]["campos"][campo]


# --- Lo que se genera ---------------------------------------------------------------------------


def test_genera_el_esqueleto_del_ejemplo(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)

    assert carpeta == tmp_path / "pedidos"
    archivos = {p.relative_to(carpeta).as_posix() for p in carpeta.rglob("*") if p.is_file()}
    assert archivos == {
        ".copier-answers.yml",
        ".env.example",
        ".gitignore",
        ".npmrc",
        ".prettierignore",
        ".prettierrc",
        "README.md",
        "nest-cli.json",
        "package.json",
        "prisma.config.ts",
        "prisma/schema.prisma",
        "src/comun/validacion.ts",
        "src/dto/actualizar-linea-pedido.dto.ts",
        "src/dto/actualizar-pedido.dto.ts",
        "src/dto/crear-linea-pedido.dto.ts",
        "src/dto/crear-pedido.dto.ts",
        "src/dto/linea-pedido-respuesta.dto.ts",
        "src/dto/pedido-respuesta.dto.ts",
        "src/main.ts",
        "src/pedidos.module.ts",
        "src/prisma.service.ts",
        "tsconfig.build.json",
        "tsconfig.json",
    }
    for archivo in archivos:
        texto = _leer(carpeta, archivo)
        assert "{{" not in texto and "{%" not in texto, f"{archivo} quedó sin renderizar"


def test_el_esquema_prisma_tiene_las_entidades_con_sus_tipos(tmp_path: Path, ejemplo: dict):
    esquema = _leer(_generar(tmp_path, ejemplo), "prisma/schema.prisma")

    assert "model Pedido {" in esquema and "model LineaPedido {" in esquema
    assert '@@map("pedido")' in esquema and '@@map("linea_pedido")' in esquema
    assert 'clienteId String @db.Uuid @map("cliente_id")' in esquema
    assert "estado PedidoEstado\n" in esquema
    assert "enum PedidoEstado {\n  pendiente\n  pagado" in esquema
    # Precisión calculada a partir de los límites: 99999999.99 -> 8 enteros + 2 decimales.
    assert "total Decimal @db.Decimal(10, 2)" in esquema
    assert 'precioUnitario Decimal @db.Decimal(8, 2) @map("precio_unitario")' in esquema
    assert 'direccionEnvio String @db.VarChar(300) @map("direccion_envio")' in esquema
    assert 'fechaEntrega DateTime? @db.Date @map("fecha_entrega")' in esquema
    assert "notas String? @db.VarChar(500)\n" in esquema
    assert "regalo Boolean?\n" in esquema
    # Campos que añade la plantilla a todas las entidades.
    assert esquema.count("id String @id @default(uuid()) @db.Uuid") == 2
    assert esquema.count('@updatedAt @map("actualizado_en")') == 2
    # Referencias a otros servicios: uuid con índice, sin relación.
    assert "@@index([clienteId])" in esquema and "@@index([productoId])" in esquema


def test_una_referencia_crea_la_relacion_en_las_dos_entidades(tmp_path: Path, ejemplo: dict):
    esquema = _leer(_generar(tmp_path, ejemplo), "prisma/schema.prisma")

    assert (
        'pedido Pedido @relation("LineaPedidoPedido", fields: [pedidoId], references: [id], '
        "onDelete: Restrict)" in esquema
    )
    assert 'lineaPedidoPorPedido LineaPedido[] @relation("LineaPedidoPedido")' in esquema
    assert "@@index([pedidoId])" in esquema


def test_el_dto_de_entrada_valida_cada_tipo(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)
    crear = _leer(carpeta, "src/dto/crear-pedido.dto.ts")
    linea = _leer(carpeta, "src/dto/crear-linea-pedido.dto.ts")

    assert "export class CrearPedidoDto {" in crear
    assert "@IsUUID()\n  clienteId!: string;" in crear
    assert (
        "@IsIn(['pendiente', 'pagado', 'enviado', 'entregado', 'cancelado'])\n"
        "  estado!: 'pendiente' | 'pagado' | 'enviado' | 'entregado' | 'cancelado';" in crear
    )
    assert (
        "@IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })\n"
        "  @Min(0)\n  @Max(99999999.99)\n  total!: number;" in crear
    )
    assert (
        "@Transform(limpiarTexto)\n  @IsString()\n  @MinLength(10)\n  @MaxLength(300)\n"
        "  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })\n  direccionEnvio!: string;"
        in crear
    )
    assert "@Transform(normalizarCorreo)\n  @IsEmail()\n  @MaxLength(254)" in crear
    assert "@ApiPropertyOptional({ format: 'date', maxLength: 10 })\n  @IsOptional()" in crear
    assert "fechaEntrega?: string;" in crear
    assert "@IsInt()\n  @Min(1)\n  @Max(100)\n  cantidad!: number;" in linea
    assert "@IsOptional()\n  @IsBoolean()\n  regalo?: boolean;" in linea


def test_cada_dto_importa_solo_lo_que_usa(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)
    for dto in ("crear-pedido", "crear-linea-pedido"):
        texto = _leer(carpeta, f"src/dto/{dto}.dto.ts")
        cuerpo = texto.split("export class", 1)[1]
        importados = re.findall(r"^import \{ (.+) \} from", texto, flags=re.M)
        for nombre in ", ".join(importados).split(", "):
            assert re.search(rf"\b{nombre}\b", cuerpo), f"{dto}: {nombre} importado y sin usar"

    linea = _leer(carpeta, "src/dto/crear-linea-pedido.dto.ts")
    assert "class-transformer" not in linea  # sin textos ni correos
    assert "../comun/validacion" not in linea


def test_actualizar_reutiliza_el_dto_de_crear(tmp_path: Path, ejemplo: dict):
    actualizar = _leer(_generar(tmp_path, ejemplo), "src/dto/actualizar-linea-pedido.dto.ts")

    assert "import { CrearLineaPedidoDto } from './crear-linea-pedido.dto';" in actualizar
    assert (
        "export class ActualizarLineaPedidoDto extends PartialType(CrearLineaPedidoDto) {}"
        in actualizar
    )


def test_cada_texto_de_la_respuesta_tiene_limite(tmp_path: Path, ejemplo: dict):
    """El Gate 2 (Spectral, OWASP API4) exige un límite en cada propiedad del contrato."""
    carpeta = _generar(tmp_path, ejemplo)
    for dto in ("pedido", "linea-pedido"):
        texto = _leer(carpeta, f"src/dto/{dto}-respuesta.dto.ts")
        propiedades = re.findall(r"@(ApiProperty\w*)\(\{ (.+) \}\)\n  (\w+)[!?]: (.+);", texto)
        assert propiedades
        for _, opciones, nombre, tipo in propiedades:
            if tipo == "string":
                assert "maxLength" in opciones, f"{dto}.{nombre} sin maxLength"
            elif tipo == "number":
                assert "minimum" in opciones and "maximum" in opciones, f"{dto}.{nombre}"
            elif "|" in tipo:
                assert "enum:" in opciones, f"{dto}.{nombre} sin enum"


def test_modulo_main_y_paquete_llevan_el_nombre_del_servicio(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)

    assert "export class PedidosModule {}" in _leer(carpeta, "src/pedidos.module.ts")
    main = _leer(carpeta, "src/main.ts")
    assert "import { PedidosModule } from './pedidos.module';" in main
    assert "whitelist: true" in main and "forbidNonWhitelisted: true" in main
    assert "process.env.PORT ?? 3002" in main
    paquete = _leer(carpeta, "package.json")
    assert '"name": "pedidos"' in paquete
    assert "DATABASE_URL=postgresql://pedidos:CAMBIAR@localhost:5432/pedidos_db" in _leer(
        carpeta, ".env.example"
    )


def test_un_servicio_con_guion_bajo(tmp_path: Path):
    datos = {
        "servicio": "historia_clinica",
        "entidades": [{"nombre": "nota", "campos": [{"nombre": "visible", "tipo": "booleano"}]}],
    }
    carpeta = _generar(tmp_path, datos)

    assert (carpeta / "src/historia-clinica.module.ts").is_file()
    assert "export class HistoriaClinicaModule {}" in _leer(
        carpeta, "src/historia-clinica.module.ts"
    )
    assert "historia_clinica_db" in _leer(carpeta, ".env.example")


def test_las_respuestas_guardan_la_ruta_relativa_de_la_plantilla(tmp_path: Path, ejemplo: dict):
    respuestas = yaml.safe_load(_leer(_generar(tmp_path, ejemplo), ".copier-answers.yml"))

    assert respuestas["_src_path"] == "templates/microservicio_nestjs"
    assert respuestas["servicio"] == "pedidos"
    # Los valores calculados no se guardan: se vuelven a calcular al actualizar.
    assert "modelo" not in respuestas and "servicio_clase" not in respuestas


# --- Textos libres: no pueden romper el código --------------------------------------------------


def test_las_descripciones_se_escapan(tmp_path: Path, ejemplo: dict):
    hostil = "Precio 'final' con \"comillas\", barra \\ y */ y ${process.exit(1)} y `x`"
    _campo(ejemplo, 1, 1)["descripcion"] = hostil
    carpeta = _generar(tmp_path, ejemplo)

    dto = _leer(carpeta, "src/dto/crear-linea-pedido.dto.ts")
    escapado = (
        "description: 'Precio \\'final\\' con \"comillas\", barra \\\\ y */ y "
        "${process.exit(1)} y `x`'"
    )
    assert escapado in dto
    # En el esquema va en un comentario de una sola línea.
    assert f"  /// {hostil}\n  productoId String" in _leer(carpeta, "prisma/schema.prisma")


# --- Validación de la especificación ------------------------------------------------------------


def _cambiar(cambio):
    """Aplica `cambio` a una copia del ejemplo."""

    def aplicar(datos: dict) -> dict:
        datos = copy.deepcopy(datos)
        cambio(datos)
        return datos

    return aplicar


CASOS_INVALIDOS = {
    "servicio con código": (
        _cambiar(lambda d: d.update(servicio="pedidos'; process.exit(1); //")),
        "servicio",
    ),
    "servicio en mayúsculas": (_cambiar(lambda d: d.update(servicio="Pedidos")), "servicio"),
    "base de datos con espacios": (
        _cambiar(lambda d: d.update(base_datos="pedidos db")),
        "base de datos",
    ),
    "puerto reservado": (_cambiar(lambda d: d.update(puerto=80)), "puerto"),
    "descripción con salto de línea": (
        _cambiar(lambda d: d.update(descripcion="uno\n} malicioso {")),
        "descripción",
    ),
    "sin entidades": (_cambiar(lambda d: d.update(entidades=[])), "lista de 1 a 20"),
    "entidades como texto": (_cambiar(lambda d: d.update(entidades="pedido")), "lista de 1 a 20"),
    "entidad con código": (
        _cambiar(lambda d: d["entidades"][0].update(nombre="pedido { }")),
        "snake_case",
    ),
    "entidades repetidas": (
        _cambiar(lambda d: d["entidades"][1].update(nombre="pedido")),
        "mismo nombre",
    ),
    "clave desconocida en la entidad": (
        _cambiar(lambda d: d["entidades"][0].update(tabla="x")),
        "claves desconocidas tabla",
    ),
    "entidad sin campos": (_cambiar(lambda d: d["entidades"][0].update(campos=[])), "1 a 50"),
    "campo con código": (
        _cambiar(lambda d: _campo(d, 0, 0).update(nombre="x!: any; constructor() { }")),
        "snake_case",
    ),
    "campo reservado": (_cambiar(lambda d: _campo(d, 0, 0).update(nombre="id")), "id"),
    "campos repetidos": (
        _cambiar(lambda d: _campo(d, 0, 1).update(nombre="cliente_id")),
        "campos con el mismo nombre",
    ),
    "clave mal escrita": (
        _cambiar(lambda d: _campo(d, 0, 6).update(requerida=False)),
        "claves desconocidas requerida",
    ),
    "tipo desconocido": (_cambiar(lambda d: _campo(d, 0, 0).update(tipo="json")), "tipo"),
    "requerido como texto": (
        _cambiar(lambda d: _campo(d, 0, 0).update(requerido="no")),
        "true o false",
    ),
    "límite como texto": (
        _cambiar(lambda d: _campo(d, 0, 2).update(max="1e9")),
        "deben ser números",
    ),
    "min mayor que max": (
        _cambiar(lambda d: _campo(d, 1, 2).update(min=10, max=1)),
        "min no puede ser mayor",
    ),
    "texto demasiado largo": (
        _cambiar(lambda d: _campo(d, 0, 3).update(max=20000)),
        "longitudes",
    ),
    "entero fuera de rango": (
        _cambiar(lambda d: _campo(d, 1, 2).update(max=2**40)),
        "-2147483648",
    ),
    "escala en un texto": (_cambiar(lambda d: _campo(d, 0, 3).update(escala=2)), "escala"),
    "límites en un booleano": (
        _cambiar(lambda d: _campo(d, 1, 4).update(max=1)),
        "solo valen para texto",
    ),
    "enumeración sin valores": (
        _cambiar(lambda d: _campo(d, 0, 1).update(valores=[])),
        "enumeración",
    ),
    "valor de enumeración con código": (
        _cambiar(lambda d: _campo(d, 0, 1).update(valores=["ok", "x'] }); //"])),
        "enumeración",
    ),
    "valores repetidos": (
        _cambiar(lambda d: _campo(d, 0, 1).update(valores=["ok", "ok"])),
        "enumeración",
    ),
    "valores en un texto": (
        _cambiar(lambda d: _campo(d, 0, 3).update(valores=["a"])),
        "valores solo vale",
    ),
    "referencia a otra entidad que no existe": (
        _cambiar(lambda d: _campo(d, 1, 0).update(entidad="cliente")),
        "referencia",
    ),
    "referencia sin _id": (
        _cambiar(lambda d: _campo(d, 1, 0).update(nombre="pedido")),
        "referencia",
    ),
    "entidad en un uuid": (
        _cambiar(lambda d: _campo(d, 0, 0).update(entidad="pedido")),
        "entidad solo vale",
    ),
    "descripción de campo multilínea": (
        _cambiar(lambda d: _campo(d, 0, 0).update(descripcion="a\n@IsOptional()")),
        "salto de línea",
    ),
}


@pytest.mark.parametrize("caso", CASOS_INVALIDOS)
def test_rechaza_una_especificacion_invalida_sin_escribir_nada(
    tmp_path: Path, ejemplo: dict, caso: str
):
    cambio, mensaje = CASOS_INVALIDOS[caso]
    with pytest.raises(ErrorPlantilla, match=re.escape(mensaje)):
        generar_servicio(cambio(ejemplo), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_no_sobrescribe_un_servicio_existente(tmp_path: Path, ejemplo: dict):
    existente = tmp_path / "pedidos" / "src" / "main.ts"
    existente.parent.mkdir(parents=True)
    existente.write_text("// a mano", encoding="utf-8")

    with pytest.raises(ErrorPlantilla, match="ya existe"):
        generar_servicio(ejemplo, tmp_path)
    assert existente.read_text(encoding="utf-8") == "// a mano"


def test_el_servicio_no_puede_salir_del_destino(tmp_path: Path, ejemplo: dict):
    ejemplo["servicio"] = "../fuera"
    with pytest.raises(ErrorPlantilla):
        generar_servicio(ejemplo, tmp_path / "destino")
    assert not (tmp_path / "fuera").exists()


def test_la_plantilla_no_ejecuta_nada_al_generar():
    """Sin tareas, migraciones ni extensiones: no hace falta `--trust` para generar."""
    configuracion = yaml.safe_load((RUTA_PLANTILLA / "copier.yml").read_text(encoding="utf-8"))
    for clave in ("_tasks", "_migrations", "_jinja_extensions", "_external_data"):
        assert clave not in configuracion


# --- Especificación y CLI -----------------------------------------------------------------------


def test_leer_especificacion_rechaza_lo_que_no_es_un_objeto(tmp_path: Path):
    ruta = tmp_path / "lista.yml"
    ruta.write_text("- uno\n- dos\n", encoding="utf-8")
    with pytest.raises(ErrorPlantilla, match="objeto"):
        leer_especificacion(ruta)


def test_cli_genera_el_servicio(tmp_path: Path):
    resultado = runner.invoke(
        app, ["servicio", "generar", str(EJEMPLO), "--destino", str(tmp_path)]
    )

    assert resultado.exit_code == 0, resultado.output
    assert "Servicio pedidos generado" in resultado.output
    assert "src/dto/crear-pedido.dto.ts" in resultado.output
    assert (tmp_path / "pedidos" / "prisma" / "schema.prisma").is_file()


def test_cli_explica_el_error_de_validacion(tmp_path: Path):
    especificacion = tmp_path / "mal.yml"
    especificacion.write_text(
        "servicio: pedidos\nentidades:\n  - nombre: pedido\n    campos:\n"
        "      - {nombre: total, tipo: dinero}\n",
        encoding="utf-8",
    )
    resultado = runner.invoke(
        app, ["servicio", "generar", str(especificacion), "--destino", str(tmp_path / "s")]
    )

    assert resultado.exit_code == 1
    assert "tipo desconocido" in resultado.output
    assert not (tmp_path / "s").exists()
