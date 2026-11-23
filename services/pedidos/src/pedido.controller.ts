import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  ParseUUIDPipe,
  Patch,
  Post,
  Query,
} from '@nestjs/common';
import {
  ApiBadRequestResponse,
  ApiBearerAuth,
  ApiConflictResponse,
  ApiCreatedResponse,
  ApiExtraModels,
  ApiInternalServerErrorResponse,
  ApiNoContentResponse,
  ApiNotFoundResponse,
  ApiOkResponse,
  ApiOperation,
  ApiParam,
  ApiParamOptions,
  ApiPayloadTooLargeResponse,
  ApiServiceUnavailableResponse,
  ApiTags,
  ApiUnauthorizedResponse,
  ApiUnsupportedMediaTypeResponse,
} from '@nestjs/swagger';
import { ErrorRespuestaDto, ErrorValidacionDto } from './comun/error-respuesta.dto';
import { MAXIMO_POR_PAGINA, PaginacionDto } from './comun/paginacion.dto';
import { ActualizarPedidoDto } from './dto/actualizar-pedido.dto';
import { CrearPedidoDto } from './dto/crear-pedido.dto';
import { PedidoPaginaDto } from './dto/pedido-pagina.dto';
import { PedidoRespuestaDto } from './dto/pedido-respuesta.dto';
import { TOKEN_INVALIDO } from './seguridad/jwt-auth.guard';
import { LIMITE_DEL_CUERPO } from './seguridad/http';
import { PedidoService } from './pedido.service';

const PARAMETRO_ID: ApiParamOptions = {
  name: 'id',
  description: 'Identificador de Pedido',
  schema: { type: 'string', format: 'uuid', maxLength: 36 },
};

const ID_INVALIDO = 'El id no es un UUID válido';
const NO_ENCONTRADO = 'No existe ningún registro de Pedido con ese id';

const CUERPO_GRANDE = `El cuerpo supera el máximo de ${LIMITE_DEL_CUERPO}`;
const CUERPO_NO_JSON = 'El cuerpo debe enviarse como application/json';

/**
 * Rutas de Pedido: /api/pedidos/pedido. Todas exigen un token de Keycloak
 * (guard global del módulo) y sus errores salen del filtro global, sin detalles internos.
 */
@ApiTags('Pedido')
@ApiExtraModels(ErrorRespuestaDto, ErrorValidacionDto)
@ApiBearerAuth('bearer')
@ApiUnauthorizedResponse({ description: TOKEN_INVALIDO, type: ErrorRespuestaDto })
@ApiInternalServerErrorResponse({ description: 'Error interno, sin detalles', type: ErrorRespuestaDto })
@ApiServiceUnavailableResponse({ description: 'Keycloak no responde', type: ErrorRespuestaDto })
@Controller('pedidos/pedido')
export class PedidoController {
  constructor(private readonly servicio: PedidoService) {}

  @Post()
  @ApiOperation({
    summary: 'Crear Pedido',
    description: 'Representa un pedido realizado por un cliente. Valida cada campo y devuelve el registro creado.',
  })
  @ApiCreatedResponse({ description: 'Registro creado', type: PedidoRespuestaDto })
  @ApiBadRequestResponse({ description: 'Datos inválidos: un mensaje por cada regla incumplida', type: ErrorValidacionDto })
  @ApiPayloadTooLargeResponse({ description: CUERPO_GRANDE, type: ErrorRespuestaDto })
  @ApiUnsupportedMediaTypeResponse({ description: CUERPO_NO_JSON, type: ErrorRespuestaDto })
  crear(@Body() datos: CrearPedidoDto): Promise<PedidoRespuestaDto> {
    return this.servicio.crear(datos);
  }

  @Get()
  @ApiOperation({
    summary: 'Listar Pedido',
    description: `Una página de registros, del más antiguo al más reciente (máximo ${MAXIMO_POR_PAGINA} por página).`,
  })
  @ApiOkResponse({ description: 'Página de registros', type: PedidoPaginaDto })
  @ApiBadRequestResponse({ description: 'pagina o tamano fuera de rango', type: ErrorValidacionDto })
  listar(@Query() paginacion: PaginacionDto): Promise<PedidoPaginaDto> {
    return this.servicio.listar(paginacion);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Obtener Pedido', description: 'El registro con ese id.' })
  @ApiParam(PARAMETRO_ID)
  @ApiOkResponse({ description: 'El registro', type: PedidoRespuestaDto })
  @ApiBadRequestResponse({ description: ID_INVALIDO, type: ErrorRespuestaDto })
  @ApiNotFoundResponse({ description: NO_ENCONTRADO, type: ErrorRespuestaDto })
  obtener(
    @Param('id', new ParseUUIDPipe()) id: string,
  ): Promise<PedidoRespuestaDto> {
    return this.servicio.obtener(id);
  }

  @Patch(':id')
  @ApiOperation({
    summary: 'Actualizar Pedido',
    description: 'Cambia solo los campos que se envían; un campo opcional enviado como null se vacía.',
  })
  @ApiParam(PARAMETRO_ID)
  @ApiOkResponse({ description: 'El registro actualizado', type: PedidoRespuestaDto })
  @ApiBadRequestResponse({ description: 'Datos inválidos o id que no es un UUID', type: ErrorValidacionDto })
  @ApiNotFoundResponse({ description: NO_ENCONTRADO, type: ErrorRespuestaDto })
  @ApiPayloadTooLargeResponse({ description: CUERPO_GRANDE, type: ErrorRespuestaDto })
  @ApiUnsupportedMediaTypeResponse({ description: CUERPO_NO_JSON, type: ErrorRespuestaDto })
  actualizar(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Body() cambios: ActualizarPedidoDto,
  ): Promise<PedidoRespuestaDto> {
    return this.servicio.actualizar(id, cambios);
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Eliminar Pedido', description: 'Borra el registro con ese id.' })
  @ApiParam(PARAMETRO_ID)
  @ApiNoContentResponse({ description: 'Registro eliminado' })
  @ApiBadRequestResponse({ description: ID_INVALIDO, type: ErrorRespuestaDto })
  @ApiNotFoundResponse({ description: NO_ENCONTRADO, type: ErrorRespuestaDto })
  @ApiConflictResponse({
    description: 'Otros registros (LineaPedido) dependen de este',
    type: ErrorRespuestaDto,
  })
  eliminar(@Param('id', new ParseUUIDPipe()) id: string): Promise<void> {
    return this.servicio.eliminar(id);
  }
}
