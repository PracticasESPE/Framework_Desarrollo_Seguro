import {
  Body,
  Controller,
  Get,
  Param,
  ParseUUIDPipe,
  Post,
} from '@nestjs/common';
import {
  ApiBadRequestResponse,
  ApiConflictResponse,
  ApiCreatedResponse,
  ApiExtraModels,
  ApiNotFoundResponse,
  ApiOkResponse,
  ApiOperation,
  ApiParam,
  ApiTags,
  getSchemaPath,
} from '@nestjs/swagger';
import { CrearUsuarioDto } from './dto/crear-usuario.dto';
import { UsuarioRespuestaDto } from './dto/usuario-respuesta.dto';
import { MAXIMO_POR_LISTADO, UsuariosService } from './usuarios.service';

@ApiTags('usuarios')
@ApiExtraModels(UsuarioRespuestaDto)
@Controller('usuarios')
export class UsuariosController {
  constructor(private readonly usuariosService: UsuariosService) {}

  @Post()
  @ApiOperation({
    summary: 'Registrar un usuario',
    description: 'Crea un usuario nuevo. El correo no puede estar repetido.',
  })
  @ApiCreatedResponse({ type: UsuarioRespuestaDto })
  @ApiBadRequestResponse({ description: 'Datos de entrada inválidos' })
  @ApiConflictResponse({ description: 'El correo ya está registrado' })
  crear(@Body() dto: CrearUsuarioDto): Promise<UsuarioRespuestaDto> {
    return this.usuariosService.crear(dto);
  }

  @Get()
  @ApiOperation({
    summary: 'Listar usuarios',
    description: `Devuelve como máximo ${MAXIMO_POR_LISTADO} usuarios, del más antiguo al más reciente.`,
  })
  @ApiOkResponse({
    description: `Lista de usuarios (máximo ${MAXIMO_POR_LISTADO})`,
    schema: {
      type: 'array',
      maxItems: MAXIMO_POR_LISTADO,
      items: { $ref: getSchemaPath(UsuarioRespuestaDto) },
    },
  })
  listar(): Promise<UsuarioRespuestaDto[]> {
    return this.usuariosService.listar();
  }

  @Get(':id')
  @ApiOperation({
    summary: 'Obtener un usuario por id',
    description: 'Devuelve el usuario con el identificador indicado.',
  })
  @ApiParam({
    name: 'id',
    description: 'Identificador del usuario',
    schema: { type: 'string', format: 'uuid', maxLength: 36 },
  })
  @ApiOkResponse({ type: UsuarioRespuestaDto })
  @ApiBadRequestResponse({ description: 'El id no es un UUID válido' })
  @ApiNotFoundResponse({ description: 'Usuario no encontrado' })
  obtener(
    @Param('id', new ParseUUIDPipe()) id: string,
  ): Promise<UsuarioRespuestaDto> {
    return this.usuariosService.obtener(id);
  }
}
