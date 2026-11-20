"""Pruebas de la plantilla Copier del microservicio NestJS.

Parte 1 (#61): módulo, entidades Prisma y DTO. Parte 2 (#63): servicio, controlador y Swagger.
Parte 3 (#65): guard de Keycloak, ValidationPipe, Helmet y filtro de errores. Parte 4 (#67):
Dockerfile, pruebas de Jest y configuración por entorno.

Generan servicios en carpetas temporales y comprueban el resultado como texto. Que el servicio
generado compile (npm ci, prisma generate y tsc), que pasen sus pruebas de Jest, que sus controles
funcionen en ejecución (verificacion/probar-controles.mjs) y que su imagen se construya y arranque
como en producción (verificacion/probar-imagen.mjs) se comprueba en el job `plantilla` del CI,
porque necesita Node, PostgreSQL, Docker y descargar las dependencias: ver
templates/microservicio_nestjs/README.md.
"""

from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
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
        ".dockerignore",
        ".env.example",
        ".gitignore",
        ".npmrc",
        ".prettierignore",
        ".prettierrc",
        "Dockerfile",
        "README.md",
        "nest-cli.json",
        "package-lock.json",
        "package.json",
        "prisma.config.ts",
        "prisma/schema.prisma",
        "src/comun/conversion.ts",
        "src/comun/error-respuesta.dto.ts",
        "src/comun/errores-prisma.ts",
        "src/comun/paginacion.dto.ts",
        "src/comun/validacion.ts",
        "src/configuracion/entorno.spec.ts",
        "src/configuracion/entorno.ts",
        "src/dto/actualizar-linea-pedido.dto.ts",
        "src/dto/actualizar-pedido.dto.ts",
        "src/dto/crear-linea-pedido.dto.ts",
        "src/dto/crear-pedido.dto.ts",
        "src/dto/linea-pedido-pagina.dto.ts",
        "src/dto/linea-pedido-respuesta.dto.ts",
        "src/dto/pedido-pagina.dto.ts",
        "src/dto/pedido-respuesta.dto.ts",
        "src/linea-pedido.controller.ts",
        "src/linea-pedido.service.spec.ts",
        "src/linea-pedido.service.ts",
        "src/main.ts",
        "src/openapi/configuracion.ts",
        "src/openapi/generar-openapi.ts",
        "src/pedido.controller.ts",
        "src/pedido.service.spec.ts",
        "src/pedido.service.ts",
        "src/pedidos.module.ts",
        "src/prisma.service.ts",
        "src/seguridad/filtro-errores.ts",
        "src/seguridad/http.ts",
        "src/seguridad/jwt-auth.guard.ts",
        "src/seguridad/validacion-global.ts",
        "test/pedidos.e2e-spec.ts",
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
        "src/main.ts",
        "src/seguridad/filtro-errores.ts",
        "src/seguridad/http.ts",
        "src/seguridad/jwt-auth.guard.ts",
        "src/pedido.service.spec.ts",
        "src/linea-pedido.service.spec.ts",
        "test/pedidos.e2e-spec.ts",
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
    assert "    PrismaService,\n    PedidoService,\n    LineaPedidoService,\n" in modulo
    main = _leer(carpeta, "src/main.ts")
    assert "import { PedidosModule } from './pedidos.module';" in main
    assert "configurarSwagger(app);" in main
    assert "leerEntorno(process.env, 3002)" in main
    paquete = _leer(carpeta, "package.json")
    assert '"name": "pedidos"' in paquete
    assert '"openapi": "node dist/openapi/generar-openapi.js"' in paquete
    assert '"@nestjs/testing"' in paquete
    assert '"helmet": "^8.3.0"' in paquete
    assert '"jose": "5.10.0"' in paquete  # la de usuarios; jose 6 solo se publica como ESM
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
    assert "KEYCLOAK_AUDIENCE=historia_clinica-api" in _leer(carpeta, ".env.example")


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
    # El contrato del Gate 2 declara el servidor HTTPS; /docs llama a su propia dirección para
    # que «Try it out» funcione en local sin resolver pedidos.fw.local.
    assert ".addServer('https://pedidos.fw.local', 'Entorno local')" in configuracion
    assert (
        "SwaggerModule.setup('docs', app, { ...documento, servers: [servidor] });" in configuracion
    )
    assert "url: '/'" in configuracion
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
    # El árbol de archivos y el resultado de la validación de la estructura.
    assert "|   |-- dto/\n|   |   |-- actualizar-linea-pedido.dto.ts" in resultado.output
    assert "8 carpetas, 47 archivos" in resultado.output
    assert "Estructura validada; rutas: /api/pedidos/pedido, /api/pedidos/linea-pedido" in (
        resultado.output
    )
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


# --- Parte 3: controles transversales -----------------------------------------------------------


def test_los_controles_se_registran_en_el_modulo(tmp_path: Path, ejemplo: dict):
    """En el módulo y no en main.ts: así también se aplican en las pruebas y en el contrato."""
    modulo = _leer(_generar(tmp_path, ejemplo), "src/pedidos.module.ts")

    assert "{ provide: APP_GUARD, useClass: JwtAuthGuard }" in modulo
    assert "{ provide: APP_PIPE, useFactory: crearValidacionGlobal }" in modulo
    assert "{ provide: APP_FILTER, useClass: FiltroErrores }" in modulo


def test_main_falla_cerrado_y_aplica_los_controles_http(tmp_path: Path, ejemplo: dict):
    main = _leer(_generar(tmp_path, ejemplo), "src/main.ts")

    # Sin configuración válida (Keycloak, base de datos) no arranca: antes de crear la aplicación.
    assert main.index("leerEntorno(") < main.index("NestFactory.create")
    # Sin el lector por defecto (formularios): solo el JSON con límite de configurarHttp.
    assert "bodyParser: false" in main
    # Helmet antes de las rutas y de Swagger.
    assert main.index("configurarHttp(app);") < main.index("configurarSwagger(app);")
    assert "new ValidationPipe" not in main  # lo registra el módulo


def test_la_validacion_es_de_lista_blanca(tmp_path: Path, ejemplo: dict):
    validacion = _leer(_generar(tmp_path, ejemplo), "src/seguridad/validacion-global.ts")

    for opcion in ("whitelist: true", "forbidNonWhitelisted: true", "forbidUnknownValues: true"):
        assert opcion in validacion
    assert "validationError: { target: false, value: false }" in validacion


def test_el_guard_fija_algoritmo_emisor_y_audiencia(tmp_path: Path, ejemplo: dict):
    guard = _leer(_generar(tmp_path, ejemplo), "src/seguridad/jwt-auth.guard.ts")

    assert "algorithms: ['RS256']" in guard  # sin alg=none ni confusión HS256/RS256
    assert "issuer: opciones.emisor" in guard and "audience: opciones.audiencia" in guard
    assert "throw new UnauthorizedException(TOKEN_INVALIDO)" in guard
    assert "throw new ServiceUnavailableException(" in guard  # Keycloak caído: 503, no 401
    # Se registra el código del error, nunca el token.
    assert "Token rechazado: ${error.code}" in guard and "${token}" not in guard


def test_las_cabeceras_de_la_api_son_estrictas(tmp_path: Path, ejemplo: dict):
    http = _leer(_generar(tmp_path, ejemplo), "src/seguridad/http.ts")

    assert "import helmet from 'helmet';" in http
    assert """directives: { defaultSrc: ["'none'"], frameAncestors: ["'none'"] }""" in http
    assert http.count("frameguard: { action: 'deny' }") == 2
    assert "res.setHeader('Cache-Control', 'no-store');" in http
    assert "app.disable('x-powered-by');" in http
    assert "export const LIMITE_DEL_CUERPO = '100kb';" in http
    assert "app.useBodyParser('json', { limit: LIMITE_DEL_CUERPO });" in http
    # Los errores del lector de JSON no repiten el texto recibido.
    assert "new BadRequestException('El cuerpo no es un JSON válido')" in http


def test_el_filtro_de_errores_no_expone_detalles(tmp_path: Path, ejemplo: dict):
    filtro = _leer(_generar(tmp_path, ejemplo), "src/seguridad/filtro-errores.ts")

    assert "@Catch()\nexport class FiltroErrores implements ExceptionFilter" in filtro
    assert "const MENSAJE_INTERNO = 'Error interno del servidor';" in filtro
    assert "mensaje.startsWith('Cannot ')" in filtro  # el 404 del enrutador repite la ruta
    assert "respuesta.setHeader('WWW-Authenticate', 'Bearer');" in filtro


def test_el_contrato_declara_el_token_y_los_errores_comunes(tmp_path: Path, ejemplo: dict):
    """Lo exigen las reglas OWASP del Gate 2: read/write-restricted y las respuestas 401 y 500."""
    carpeta = _generar(tmp_path, ejemplo)
    configuracion = _leer(carpeta, "src/openapi/configuracion.ts")
    assert "scheme: 'bearer'" in configuracion and "bearerFormat: 'JWT'" in configuracion

    for archivo in ("src/pedido.controller.ts", "src/linea-pedido.controller.ts"):
        controlador = _leer(carpeta, archivo)
        cabecera = controlador.split("export class")[0]
        assert "@ApiBearerAuth('bearer')" in cabecera
        assert "@ApiUnauthorizedResponse(" in cabecera
        assert "@ApiInternalServerErrorResponse(" in cabecera
        assert "@ApiServiceUnavailableResponse(" in cabecera
        # Solo las operaciones con cuerpo (POST y PATCH) pueden dar 413 y 415.
        assert controlador.count("@ApiPayloadTooLargeResponse(") == 2
        assert controlador.count("@ApiUnsupportedMediaTypeResponse(") == 2


def test_ningun_archivo_de_la_plantilla_lo_ignora_git():
    """Un archivo ignorado existe en local pero falta en el CI (le pasó a .env.example.jinja)."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git no está disponible")
    raiz = RUTA_PLANTILLA.parents[1]
    archivos = [p.relative_to(raiz).as_posix() for p in RUTA_PLANTILLA.rglob("*") if p.is_file()]
    resultado = subprocess.run(  # noqa: S603 - argumentos fijos, sin shell
        [git, "check-ignore", "--no-index", "--stdin"],
        input="\n".join(archivos).encode("utf-8"),  # bytes: sin \r al final en Windows
        capture_output=True,
        cwd=raiz,
        check=False,
    )
    ignorados = resultado.stdout.decode("utf-8").split()
    assert ignorados == [], f"Archivos ignorados: {ignorados}"


# --- Parte 4: Dockerfile, pruebas y configuración por entorno ------------------------------------


def test_swagger_solo_fuera_de_produccion(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)
    main = _leer(carpeta, "src/main.ts")
    assert "if (entorno.documentacion) {\n    configurarSwagger(app);" in main
    assert "logger: entorno.registro" in main
    assert "app.enableShutdownHooks();" in main
    assert "app.listen(entorno.puerto)" in main

    entorno = _leer(carpeta, "src/configuracion/entorno.ts")
    # Sin NODE_ENV, producción: el entorno más restrictivo.
    assert "env.NODE_ENV?.trim() || 'production'" in entorno
    assert "documentacion: nombre !== 'production'" in entorno
    assert "const CLAVE_DE_EJEMPLO = 'cambiar';" in entorno
    # Los mensajes de error nombran la variable: ninguno interpola un valor del entorno.
    for linea in entorno.splitlines():
        if "problemas.push(" in linea:
            assert "${env" not in linea and "${base" not in linea, linea
    assert "NODE_ENV=development" in _leer(carpeta, ".env.example")


def test_el_dockerfile_es_multietapa_distroless_y_sin_root(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)
    dockerfile = _leer(carpeta, "Dockerfile")

    assert dockerfile.count("\nFROM ") == 3
    assert "FROM gcr.io/distroless/nodejs22-debian13:nonroot AS runtime" in dockerfile
    assert "USER 65532:65532" in dockerfile
    assert "ENV NODE_ENV=production \\\n    PORT=3002" in dockerfile
    assert "EXPOSE 3002" in dockerfile
    assert "HEALTHCHECK " in dockerfile and "process.env.PORT||3002" in dockerfile
    # npm ci con el lock, sin scripts; y sin las dependencias de desarrollo (devOptional incluidas).
    assert "COPY package.json package-lock.json .npmrc ./" in dockerfile
    assert "RUN npm ci --ignore-scripts" in dockerfile
    assert "npm ci --omit=dev --omit=optional --ignore-scripts" in dockerfile
    assert "rm -f dist/openapi/generar-openapi.*" in dockerfile
    # La imagen final solo copia lo compilado y las dependencias de producción.
    final = dockerfile.split("AS runtime", 1)[1]
    copias = re.findall(r"^COPY .*$", final, flags=re.M)
    assert copias == [
        "COPY --from=prod-deps --chown=65532:65532 /app/node_modules ./node_modules",
        "COPY --from=build --chown=65532:65532 /app/dist ./dist",
        "COPY --chown=65532:65532 package.json ./",
    ]
    ignorados = _leer(carpeta, ".dockerignore").splitlines()
    for patron in (".env", ".env.*", "node_modules", "test", "**/*.spec.ts", ".git"):
        assert patron in ignorados


def test_el_lock_corresponde_al_paquete_y_lleva_integridad(tmp_path: Path, ejemplo: dict):
    """npm ci falla si el lock no coincide con package.json: se comprueba antes de llegar al CI."""
    carpeta = _generar(tmp_path, ejemplo)
    paquete = json.loads(_leer(carpeta, "package.json"))
    lock = json.loads(_leer(carpeta, "package-lock.json"))

    assert lock["name"] == lock["packages"][""]["name"] == "pedidos"
    assert lock["lockfileVersion"] == 3
    raiz = lock["packages"][""]
    for clave in ("dependencies", "devDependencies"):
        assert raiz.get(clave) == paquete[clave], f"{clave} distinto en el lock"
    paquetes = {k: v for k, v in lock["packages"].items() if k}
    assert len(paquetes) > 500
    for nombre, datos in paquetes.items():
        assert datos.get("integrity", "").startswith("sha512-"), f"{nombre} sin integridad"
        assert datos["resolved"].startswith("https://registry.npmjs.org/"), nombre


def test_el_lock_de_la_plantilla_solo_varia_en_el_nombre():
    plantilla = (RUTA_PLANTILLA / "plantilla" / "package-lock.json.jinja").read_text("utf-8")
    assert plantilla.count("{{") == 2
    assert plantilla.count("{{ servicio | tojson }}") == 2
    assert "{%" not in plantilla and "{#" not in plantilla


def test_genera_las_pruebas_de_jest(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)
    paquete = json.loads(_leer(carpeta, "package.json"))
    assert paquete["scripts"]["test"] == "jest"
    assert paquete["scripts"]["test:cov"] == "jest --coverage"  # lo usa la fase 9
    for dependencia in ("jest", "ts-jest", "@types/jest", "supertest", "@types/supertest"):
        assert dependencia in paquete["devDependencies"]
    jest = paquete["jest"]
    assert jest["roots"] == ["<rootDir>/src", "<rootDir>/test"]
    assert re.search(jest["testRegex"], "test/pedidos.e2e-spec.ts")
    assert re.search(jest["testRegex"], "src/pedido.service.spec.ts")
    # El cliente de Prisma importa sus archivos con .js.
    assert jest["moduleNameMapper"] == {"^(\\.{1,2}/.*)\\.js$": "$1"}
    assert "!src/generated/**" in jest["collectCoverageFrom"]
    # Ni las pruebas ni el directorio test/ entran en la compilación de producción.
    compilacion = json.loads(_leer(carpeta, "tsconfig.build.json"))
    assert "test" in compilacion["exclude"] and "**/*spec.ts" in compilacion["exclude"]


def test_las_pruebas_unitarias_cubren_cada_entidad(tmp_path: Path, ejemplo: dict):
    carpeta = _generar(tmp_path, ejemplo)
    pedido = _leer(carpeta, "src/pedido.service.spec.ts")

    assert "describe('PedidoService', () => {" in pedido
    assert "const tabla = prisma.pedido;" in pedido
    # Un valor válido de cada tipo, en la entrada, en la fila de Prisma y en la respuesta.
    assert "estado: 'pendiente'," in pedido
    assert "total: decimal(0)," in pedido
    assert "direccionEnvio: 'Texto de prueba'," in pedido  # min 10, max 300
    assert "fechaEntrega: new Date('2026-01-15T00:00:00.000Z')," in pedido
    assert "fechaEntrega: '2026-01-15'," in pedido
    # Las reglas del LLM se sustituyen y se comprueba que van antes de escribir.
    assert "jest.spyOn(reglas, 'reglasAlCrear').mockResolvedValue(undefined);" in pedido
    assert "mock.invocationCallOrder[0]).toBeLessThan(" in pedido
    for codigo in ("P2002", "P2003", "P2025"):
        assert f"code: '{codigo}'" in pedido

    linea = _leer(carpeta, "src/linea-pedido.service.spec.ts")
    assert "const tabla = prisma.lineaPedido;" in linea
    assert "cantidad: 1," in linea and "precioUnitario: decimal(0.01)," in linea


def test_la_prueba_de_la_api_recorre_cada_entidad(tmp_path: Path, ejemplo: dict):
    e2e = _leer(_generar(tmp_path, ejemplo), "test/pedidos.e2e-spec.ts")

    assert "imports: [PedidosModule]" in e2e
    assert "configurarHttp(app);" in e2e and "app.setGlobalPrefix('api');" in e2e
    assert "const AUDIENCIA = 'pedidos-api';" in e2e
    assert "'sin firma (alg=none)'" in e2e
    for ruta in ("/api/pedidos/pedido", "/api/pedidos/linea-pedido"):
        assert f"const RUTA = '{ruta}';" in e2e
    assert e2e.count("it('crea un registro con un cuerpo válido (201)'") == 2
    assert e2e.count("'property esAdmin should not exist'") == 2


def test_el_ejemplo_de_todos_los_tipos_los_cubre(tmp_path: Path):
    """El CI compila este ejemplo: debe tener cada tipo, obligatorio y opcional donde importa."""
    datos = leer_especificacion(RUTA_PLANTILLA / "ejemplos" / "todos-los-tipos.yml")
    campos = [c for e in datos["entidades"] for c in e["campos"]]
    tipos = {c["tipo"] for c in campos}
    assert tipos == {
        "texto",
        "correo",
        "entero",
        "decimal",
        "booleano",
        "fecha",
        "fecha_hora",
        "uuid",
        "enumeracion",
        "referencia",
    }
    fechas = [c for c in campos if c["tipo"] in ("fecha", "fecha_hora")]
    assert {c.get("requerido", True) for c in fechas} == {True, False}
    carpeta = _generar(tmp_path, datos)
    assert (carpeta / "test" / "historia-clinica.e2e-spec.ts").is_file()
    assert (carpeta / "src" / "consulta-medica.service.spec.ts").is_file()


def test_una_fecha_obligatoria_se_actualiza_sin_null(tmp_path: Path):
    """Prisma no admite null en un campo obligatorio: aFecha no añade null a su tipo."""
    conversion = _leer(_generar(tmp_path, leer_especificacion(EJEMPLO)), "src/comun/conversion.ts")
    assert "export function aFecha(valor: string | undefined): Date | undefined;" in conversion


def test_sin_campos_obligatorios_no_genera_la_prueba_del_cuerpo_vacio(tmp_path: Path):
    datos = {
        "servicio": "notas",
        "entidades": [
            {"nombre": "nota", "campos": [{"nombre": "texto", "tipo": "texto", "requerido": False}]}
        ],
    }
    e2e = _leer(_generar(tmp_path, datos), "test/notas.e2e-spec.ts")
    assert "sin los campos obligatorios" not in e2e
    assert "decimal" not in e2e  # sin decimales no declara su ayuda
