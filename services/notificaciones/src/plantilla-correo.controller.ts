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
import { ActualizarPlantillaCorreoDto } from './dto/actualizar-plantilla-correo.dto';
import { CrearPlantillaCorreoDto } from './dto/crear-plantilla-correo.dto';
import { PlantillaCorreoPaginaDto } from './dto/plantilla-correo-pagina.dto';
import { PlantillaCorreoRespuestaDto } from './dto/plantilla-correo-respuesta.dto';
import { TOKEN_INVALIDO } from './seguridad/jwt-auth.guard';
import { LIMITE_DEL_CUERPO } from './seguridad/http';
import { PlantillaCorreoService } from './plantilla-correo.service';

const PARAMETRO_ID: ApiParamOptions = {
  name: 'id',
  description: 'Identificador de PlantillaCorreo',
  schema: { type: 'string', format: 'uuid', maxLength: 36 },
};

const ID_INVALIDO = 'El id no es un UUID válido';
const NO_ENCONTRADO = 'No existe ningún registro de PlantillaCorreo con ese id';

const CUERPO_GRANDE = `El cuerpo supera el máximo de ${LIMITE_DEL_CUERPO}`;
const CUERPO_NO_JSON = 'El cuerpo debe enviarse como application/json';

/**
 * Rutas de PlantillaCorreo: /api/notificaciones/plantilla-correo. Todas exigen un token de Keycloak
 * (guard global del módulo) y sus errores salen del filtro global, sin detalles internos.
 */
@ApiTags('PlantillaCorreo')
@ApiExtraModels(ErrorRespuestaDto, ErrorValidacionDto)
@ApiBearerAuth('bearer')
@ApiUnauthorizedResponse({ description: TOKEN_INVALIDO, type: ErrorRespuestaDto })
@ApiInternalServerErrorResponse({ description: 'Error interno, sin detalles', type: ErrorRespuestaDto })
@ApiServiceUnavailableResponse({ description: 'Keycloak no responde', type: ErrorRespuestaDto })
@Controller('notificaciones/plantilla-correo')
export class PlantillaCorreoController {
  constructor(private readonly servicio: PlantillaCorreoService) {}

  @Post()
  @ApiOperation({
    summary: 'Crear PlantillaCorreo',
    description: 'Valida cada campo y devuelve el registro creado.',
  })
  @ApiCreatedResponse({ description: 'Registro creado', type: PlantillaCorreoRespuestaDto })
  @ApiBadRequestResponse({ description: 'Datos inválidos: un mensaje por cada regla incumplida', type: ErrorValidacionDto })
  @ApiPayloadTooLargeResponse({ description: CUERPO_GRANDE, type: ErrorRespuestaDto })
  @ApiUnsupportedMediaTypeResponse({ description: CUERPO_NO_JSON, type: ErrorRespuestaDto })
  crear(@Body() datos: CrearPlantillaCorreoDto): Promise<PlantillaCorreoRespuestaDto> {
    return this.servicio.crear(datos);
  }

  @Get()
  @ApiOperation({
    summary: 'Listar PlantillaCorreo',
    description: `Una página de registros, del más antiguo al más reciente (máximo ${MAXIMO_POR_PAGINA} por página).`,
  })
  @ApiOkResponse({ description: 'Página de registros', type: PlantillaCorreoPaginaDto })
  @ApiBadRequestResponse({ description: 'pagina o tamano fuera de rango', type: ErrorValidacionDto })
  listar(@Query() paginacion: PaginacionDto): Promise<PlantillaCorreoPaginaDto> {
    return this.servicio.listar(paginacion);
  }

  @Get(':id')
  @ApiOperation({ summary: 'Obtener PlantillaCorreo', description: 'El registro con ese id.' })
  @ApiParam(PARAMETRO_ID)
  @ApiOkResponse({ description: 'El registro', type: PlantillaCorreoRespuestaDto })
  @ApiBadRequestResponse({ description: ID_INVALIDO, type: ErrorRespuestaDto })
  @ApiNotFoundResponse({ description: NO_ENCONTRADO, type: ErrorRespuestaDto })
  obtener(
    @Param('id', new ParseUUIDPipe()) id: string,
  ): Promise<PlantillaCorreoRespuestaDto> {
    return this.servicio.obtener(id);
  }

  @Patch(':id')
  @ApiOperation({
    summary: 'Actualizar PlantillaCorreo',
    description: 'Cambia solo los campos que se envían; un campo opcional enviado como null se vacía.',
  })
  @ApiParam(PARAMETRO_ID)
  @ApiOkResponse({ description: 'El registro actualizado', type: PlantillaCorreoRespuestaDto })
  @ApiBadRequestResponse({ description: 'Datos inválidos o id que no es un UUID', type: ErrorValidacionDto })
  @ApiNotFoundResponse({ description: NO_ENCONTRADO, type: ErrorRespuestaDto })
  @ApiPayloadTooLargeResponse({ description: CUERPO_GRANDE, type: ErrorRespuestaDto })
  @ApiUnsupportedMediaTypeResponse({ description: CUERPO_NO_JSON, type: ErrorRespuestaDto })
  actualizar(
    @Param('id', new ParseUUIDPipe()) id: string,
    @Body() cambios: ActualizarPlantillaCorreoDto,
  ): Promise<PlantillaCorreoRespuestaDto> {
    return this.servicio.actualizar(id, cambios);
  }

  @Delete(':id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Eliminar PlantillaCorreo', description: 'Borra el registro con ese id.' })
  @ApiParam(PARAMETRO_ID)
  @ApiNoContentResponse({ description: 'Registro eliminado' })
  @ApiBadRequestResponse({ description: ID_INVALIDO, type: ErrorRespuestaDto })
  @ApiNotFoundResponse({ description: NO_ENCONTRADO, type: ErrorRespuestaDto })
  @ApiConflictResponse({
    description: 'Otros registros (Notificacion) dependen de este',
    type: ErrorRespuestaDto,
  })
  eliminar(@Param('id', new ParseUUIDPipe()) id: string): Promise<void> {
    return this.servicio.eliminar(id);
  }
}
