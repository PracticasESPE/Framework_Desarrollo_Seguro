"""Pruebas de la plantilla Copier del microservicio NestJS.

Parte 1 (#61): módulo, entidades Prisma y DTO. Parte 2 (#63): servicio, controlador y Swagger.

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
        "src/comun/conversion.ts",
        "src/comun/error-respuesta.dto.ts",
        "src/comun/errores-prisma.ts",
        "src/comun/paginacion.dto.ts",
        "src/comun/validacion.ts",
        "src/dto/actualizar-linea-pedido.dto.ts",
        "src/dto/actualizar-pedido.dto.ts",
        "src/dto/crear-linea-pedido.dto.ts",
        "src/dto/crear-pedido.dto.ts",
        "src/dto/linea-pedido-pagina.dto.ts",
        "src/dto/linea-pedido-respuesta.dto.ts",
        "src/dto/pedido-pagina.dto.ts",
        "src/dto/pedido-respuesta.dto.ts",
        "src/linea-pedido.controller.ts",
        "src/linea-pedido.service.ts",
        "src/main.ts",
        "src/openapi/configuracion.ts",
        "src/openapi/generar-openapi.ts",
        "src/pedido.controller.ts",
        "src/pedido.service.ts",
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
    assert (
        "@ApiPropertyOptional({ nullable: true, format: 'date', maxLength: 10 })\n"
        "  @IsOptional()" in crear
    )
    assert "fechaEntrega?: string;" in crear
    assert "@IsInt()\n  @Min(1)\n  @Max(100)\n  cantidad!: number;" in linea
    assert "@IsOptional()\n  @IsBoolean()\n  regalo?: boolean;" in linea


def _importados(texto: str) -> list[str]:
    """Nombres de todas las importaciones con llaves, de una o de varias líneas."""
    nombres = []
    for bloque in re.findall(r"^import (?:type )?\{([^}]*)\} from", texto, flags=re.M):
        nombres += [n.strip() for n in bloque.split(",") if n.strip()]
    return nombres


@pytest.mark.parametrize(
    "archivo",
    [
        "src/dto/crear-pedido.dto.ts",
        "src/dto/crear-linea-pedido.dto.ts",
        "src/dto/actualizar-pedido.dto.ts",
        "src/dto/actualizar-linea-pedido.dto.ts",
        "src/dto/pedido-respuesta.dto.ts",
        "src/dto/linea-pedido-respuesta.dto.ts",
        "src/pedido.service.ts",
        "src/linea-pedido.service.ts",
        "src/pedido.controller.ts",
        "src/linea-pedido.controller.ts",
        "src/pedidos.module.ts",
    ],
)
def test_cada_archivo_importa_solo_lo_que_usa(tmp_path: Path, ejemplo: dict, archivo: str):
    texto = _leer(_generar(tmp_path, ejemplo), archivo)
    cuerpo = re.sub(r"^import [^;]+;", "", texto, flags=re.M)
    importados = _importados(texto)
    assert importados
    for nombre in importados:
        assert re.search(rf"\b{nombre}\b", cuerpo), f"{archivo}: {nombre} importado y sin usar"


def test_sin_textos_no_importa_sus_utilidades(tmp_path: Path, ejemplo: dict):
    linea = _leer(_generar(tmp_path, ejemplo), "src/dto/crear-linea-pedido.dto.ts")
    assert "class-transformer" not in linea  # sin textos ni correos
    assert "../comun/validacion" not in linea


def test_actualizar_no_admite_null_en_un_campo_obligatorio(tmp_path: Path, ejemplo: dict):
    """@IsOptional dejaría pasar null y la base respondería 500: se usa @ValidateIf(seEnvio)."""
    actualizar = _leer(_generar(tmp_path, ejemplo), "src/dto/actualizar-pedido.dto.ts")

    assert "export class ActualizarPedidoDto {" in actualizar
    assert "PartialType" not in actualizar
    # Obligatorio: se puede omitir, pero si viene (aunque sea null) se valida.
    assert "@ValidateIf(seEnvio)\n  @IsIn(" in actualizar
    assert "estado?: 'pendiente'" in actualizar
    # Opcional: null lo vacía.
    decorador_notas = actualizar.split("notas?:")[0].rsplit("@ApiPropertyOptional", 1)[1]
    assert "nullable: true" in decorador_notas
    assert "@IsOptional()\n  @Transform(limpiarTexto)" in actualizar
    # Mismos límites que al crear.
    assert "@MinLength(10)\n  @MaxLength(300)" in actualizar


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
                assert "format:" in opciones or "pattern:" in opciones, f"{dto}.{nombre}"
            elif tipo == "number":
                assert "minimum" in opciones and "maximum" in opciones, f"{dto}.{nombre}"
            elif "|" in tipo:
                assert "enum:" in opciones, f"{dto}.{nombre} sin enum"


def test_modulo_main_y_paquete_llevan_el_nombre_del_servicio(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)

    modulo = _leer(carpeta, "src/pedidos.module.ts")
    assert "export class PedidosModule {}" in modulo
    assert "controllers: [PedidoController, LineaPedidoController]" in modulo
    assert "providers: [PrismaService, PedidoService, LineaPedidoService]" in modulo
    main = _leer(carpeta, "src/main.ts")
    assert "import { PedidosModule } from './pedidos.module';" in main
    assert "whitelist: true" in main and "forbidNonWhitelisted: true" in main
    assert "configurarSwagger(app);" in main
    assert "process.env.PORT ?? 3002" in main
    paquete = _leer(carpeta, "package.json")
    assert '"name": "pedidos"' in paquete
    assert '"openapi": "node dist/openapi/generar-openapi.js"' in paquete
    assert '"@nestjs/testing"' in paquete
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
    assert "@Controller('historia-clinica/nota')" in _leer(carpeta, "src/nota.controller.ts")
    assert "historia_clinica_db" in _leer(carpeta, ".env.example")


# --- Parte 2: servicio, controlador y Swagger ---------------------------------------------------


def test_el_controlador_expone_el_crud_bajo_la_ruta_del_servicio(tmp_path: Path, ejemplo: dict):
    controlador = _leer(_generar(tmp_path, ejemplo), "src/linea-pedido.controller.ts")

    assert "@Controller('pedidos/linea-pedido')" in controlador
    assert "@ApiTags('LineaPedido')" in controlador
    for ruta in ("@Post()", "@Get()", "@Get(':id')", "@Patch(':id')", "@Delete(':id')"):
        assert ruta in controlador
    # El id siempre se valida como UUID antes de llegar al servicio.
    assert controlador.count("@Param('id', new ParseUUIDPipe()) id: string") == 3
    assert "@HttpCode(HttpStatus.NO_CONTENT)" in controlador
    assert "listar(@Query() paginacion: PaginacionDto)" in controlador
    assert "crear(@Body() datos: CrearLineaPedidoDto)" in controlador
    assert "@Body() cambios: ActualizarLineaPedidoDto" in controlador


def test_cada_operacion_documenta_sus_respuestas(tmp_path: Path, ejemplo: dict):
    controlador = _leer(_generar(tmp_path, ejemplo), "src/pedido.controller.ts")
    operaciones = re.split(r"\n  @(?=Post|Get|Patch|Delete)", controlador)[1:]
    assert len(operaciones) == 5
    for operacion in operaciones:
        assert "@ApiOperation({" in operacion and "summary:" in operacion
        assert "@ApiBadRequestResponse(" in operacion
        assert re.search(r"@Api(Ok|Created|NoContent)Response\(", operacion)
    # Las de un id documentan el 404 y su parámetro.
    assert controlador.count("@ApiNotFoundResponse(") == 3
    assert controlador.count("@ApiParam(PARAMETRO_ID)") == 3
    assert "schema: { type: 'string', format: 'uuid', maxLength: 36 }" in controlador


def test_el_409_solo_aparece_cuando_puede_ocurrir(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)
    pedido = _leer(carpeta, "src/pedido.controller.ts")
    linea = _leer(carpeta, "src/linea-pedido.controller.ts")

    # Pedido tiene líneas que lo referencian: no se puede borrar si las tiene.
    assert "Otros registros (LineaPedido) dependen de este" in pedido
    # Sin campos únicos ni entidades que dependan de ella, LineaPedido nunca da 409.
    assert "ApiConflictResponse" not in linea


def test_un_campo_unico_documenta_el_409_al_guardar(tmp_path: Path, ejemplo: dict):
    _campo(ejemplo, 0, 4)["unico"] = True  # correo_contacto
    controlador = _leer(_generar(tmp_path, ejemplo), "src/pedido.controller.ts")

    assert controlador.count("Ya existe un registro con el mismo valor en correoContacto") == 2


def test_una_referencia_documenta_los_dos_tipos_de_400(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)
    linea = _leer(carpeta, "src/linea-pedido.controller.ts")
    pedido = _leer(carpeta, "src/pedido.controller.ts")

    assert linea.count("{ $ref: getSchemaPath(ErrorValidacionDto) },") == 2  # crear y actualizar
    assert "getSchemaPath" not in pedido


def test_el_servicio_traduce_los_errores_de_prisma(tmp_path: Path, ejemplo: dict):
    servicio = _leer(_generar(tmp_path, ejemplo), "src/pedido.service.ts")

    assert "export class PedidoService {" in servicio
    assert "this.prisma.pedido.create({" in servicio
    assert servicio.count("throw this.traducirError(error,") == 3
    assert "esValorRepetido(error)" in servicio and "ConflictException" in servicio
    assert "esRegistroInexistente(error)" in servicio
    assert "esRelacionRota(error)" in servicio and "BadRequestException" in servicio
    # Paginación con orden estable.
    assert "orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }]" in servicio
    assert "skip: (pagina - 1) * tamano," in servicio


def test_el_servicio_convierte_cada_tipo_a_json(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)
    pedido = _leer(carpeta, "src/pedido.service.ts")
    linea = _leer(carpeta, "src/linea-pedido.service.ts")

    assert "total: fila.total.toNumber()," in pedido
    assert "fechaEntrega: fila.fechaEntrega?.toISOString().slice(0, 10)," in pedido
    assert "notas: fila.notas ?? undefined," in pedido
    assert "fechaEntrega: aFecha(datos.fechaEntrega)," in pedido
    assert "fechaEntrega: aFecha(cambios.fechaEntrega)," in pedido
    assert "regalo: fila.regalo ?? undefined," in linea
    assert "aFecha" not in linea  # sin fechas


def test_el_servicio_marca_el_punto_de_extension_para_el_llm(tmp_path: Path, ejemplo: dict):
    """El generador de lógica de negocio (#64) solo reescribe lo que hay entre las marcas."""
    servicio = _leer(_generar(tmp_path, ejemplo), "src/linea-pedido.service.ts")
    inicio = "// @framework:logica-negocio:inicio linea_pedido"
    fin = "// @framework:logica-negocio:fin linea_pedido"

    assert servicio.count(inicio) == 1 and servicio.count(fin) == 1
    bloque = servicio.split(inicio)[1].split(fin)[0]
    for metodo in ("reglasAlCrear(", "reglasAlActualizar(", "reglasAlEliminar("):
        assert f"protected {metodo}" in bloque
    # Fuera del bloque, cada operación llama a su regla antes de tocar la base.
    fuera = servicio.replace(bloque, "")
    assert "await this.reglasAlCrear(datos);" in fuera
    assert "await this.reglasAlActualizar(actual, cambios);" in fuera
    assert "await this.reglasAlEliminar(actual);" in fuera


def test_swagger_tiene_una_etiqueta_por_entidad(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)
    configuracion = _leer(carpeta, "src/openapi/configuracion.ts")

    assert ".setTitle('Servicio pedidos')" in configuracion
    assert ".setVersion('1.0.0')" in configuracion
    assert ".addTag('Pedido', 'Compra de un cliente con su dirección de envío')" in configuracion
    assert ".addTag('LineaPedido'," in configuracion
    assert "SwaggerModule.setup('docs', app, documento);" in configuracion
    generar = _leer(carpeta, "src/openapi/generar-openapi.ts")
    assert "Test.createTestingModule({ imports: [PedidosModule] })" in generar
    assert ".overrideProvider(PrismaService)" in generar


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
    "entidad reservada": (
        _cambiar(lambda d: d["entidades"][0].update(nombre="paginacion")),
        "reservado",
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
