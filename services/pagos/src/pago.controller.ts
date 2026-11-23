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
  getSchemaPath,
} from '@nestjs/swagger';
import { ErrorRespuestaDto, ErrorValidacionDto } from './comun/error-respuesta.dto';
import { MAXIMO_POR_PAGINA, PaginacionDto } from './comun/paginacion.dto';
import { ActualizarPagoDto } from './dto/actualizar-pago.dto';
import { CrearPagoDto } from './dto/crear-pago.dto';
import { PagoPaginaDto } from './dto/pago-pagina.dto';
import { PagoRespuestaDto } from './dto/pago-respuesta.dto';
import { TOKEN_INVALIDO } from './seguridad/jwt-auth.guard';
import { LIMITE_DEL_CUERPO } from './seguridad/http';
import { PagoService } from './pago.service';

const PARAMETRO_ID: ApiParamOptions = {
  name: 'id',
  description: 'Identificador de Pago',
  schema: { type: 'string', format: 'uuid', maxLength: 36 },
};

const ID_INVALIDO = 'El id no es un UUID válido';
const NO_ENCONTRADO = 'No existe ningún registro de Pago con ese id';

const CUERPO_GRANDE = `El cuerpo supera el máximo de ${LIMITE_DEL_CUERPO}`;
const CUERPO_NO_JSON = 'El cuerpo debe enviarse como application/json';

/**
 * Rutas de Pago: /api/pagos/pago. Todas exigen un token de Keycloak
 * (guard global del módulo) y sus errores salen del filtro global, sin detalles internos.
 */
@ApiTags('Pago')
@ApiExtraModels(ErrorRespuestaDto, ErrorValidacionDto)
@ApiBearerAuth('bearer')
@ApiUnauthorizedResponse({ description: TOKEN_INVALIDO, type: ErrorRespuestaDto })
@ApiInternalServerErrorResponse({ description: 'Error interno, sin detalles', type: ErrorRespuestaDto })
@ApiServiceUnavailableResponse({ description: 'Keycloak no responde', type: ErrorRespuestaDto })
@Controller('pagos/pago')
export class PagoController {
  constructor(private readonly servicio: PagoService) {}

  @Post()
  @ApiOperation({
    summary: 'Crear Pago',
    description: 'Valida cada campo y devuelve el registro creado.',
  })
  @ApiCreatedResponse({ description: 'Registro creado', type: PagoRespuestaDto })
  @ApiBadRequestResponse({
    description: 'Datos inválidos: un mensaje por cada regla incumplida, o una referencia a otra entidad que no existe',
    schema: {
      oneOf: [
        { $ref: getSchemaPath(ErrorValidacionDto) },
        { $ref: getSchemaPath(ErrorRespuestaDto) },
      ],
    },
  })
  @ApiConflictResponse({
    description: 'Ya existe un registro con el mismo valor en externalPaymentId',
    type: ErrorRespuestaDto,
  })
  @ApiPayloadTooLargeResponse({ description: CUERPO_GRANDE, type: ErrorRespuestaDto })
  @ApiUnsupportedMediaTypeResponse({ description: CUERPO_NO_JSON, type: ErrorRespuestaDto })
  crear(@Body() datos: CrearPagoDto): Promise<PagoRespuestaDto> {
    return this.servicio.crear(datos);
  }

  @Get()
  @ApiOperation({
    summary: 'Listar Pago',
    description: `Una página de registros, del más antiguo al más reciente (máximo ${MAXIMO_POR_PAGINA} por página).`,
  })
  @ApiOkResponse({ description: 'Página de registros', type: PagoPaginaDto })
  @ApiBadRequestResponse({ description: 'pagina o tamano fuera de rango', type: ErrorValidacionDto })
  listar(@Query() paginacion: PaginacionDto): Promise<PagoPaginaDto> {
    return this.servicio.listar(paginacion);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Obtener Pago', description: 'El registro con ese id.' })
  @ApiParam(PARAMETRO_ID)
  @ApiOkResponse({ description: 'El registro', type: PagoRespuestaDto })
  @ApiBadRequestResponse({ description: ID_INVALIDO, type: ErrorRespuestaDto })
  @ApiNotFoundResponse({ description: NO_ENCONTRADO, type: ErrorRespuestaDto })
  obtener(
    @Param('id', new ParseUUIDPipe()) id: string,
  ): Promise<PagoRespuestaDto> {
    return this.servicio.obtener(id);
  }

  @Patch(':id')
  @ApiOperation({
    summary: 'Actualizar Pago',
    description: 'Cambia solo los campos que se envían; un campo opcional enviado como null se vacía.',
  })
  @ApiParam(PARAMETRO_ID)
  @ApiOkResponse({ description: 'El registro actualizado', type: PagoRespuestaDto })
  @ApiBadRequestResponse({
    description: 'Datos inválidos o id que no es un UUID, o una referencia a otra entidad que no existe',
    schema: {
      oneOf: [
        { $ref: getSchemaPath(ErrorValidacionDto) },
        { $ref: getSchemaPath(ErrorRespuestaDto) },
      ],
    },
  })
  @ApiNotFoundResponse({ description: NO_ENCONTRADO, type: ErrorRespuestaDto })
  @ApiConflictResponse({
    description: 'Ya existe un registro con el mismo valor en externalPaymentId',
    type: ErrorRespuestaDto,
  })
  @ApiPayloadTooLargeResponse({ description: CUERPO_GRANDE, type: ErrorRespuestaDto })
  @ApiUnsupportedMediaTypeResponse({ description: CUERPO_NO_JSON, type: ErrorRespuestaDto })
  actualizar(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Body() cambios: ActualizarPagoDto,
  ): Promise<PagoRespuestaDto> {
    return this.servicio.actualizar(id, cambios);
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Eliminar Pago', description: 'Borra el registro con ese id.' })
  @ApiParam(PARAMETRO_ID)
  @ApiNoContentResponse({ description: 'Registro eliminado' })
  @ApiBadRequestResponse({ description: ID_INVALIDO, type: ErrorRespuestaDto })
  @ApiNotFoundResponse({ description: NO_ENCONTRADO, type: ErrorRespuestaDto })
  @ApiConflictResponse({
    description: 'Otros registros (Transaccion) dependen de este',
    type: ErrorRespuestaDto,
  })
  eliminar(@Param('id', new ParseUUIDPipe()) id: string): Promise<void> {
    return this.servicio.eliminar(id);
  }
}
