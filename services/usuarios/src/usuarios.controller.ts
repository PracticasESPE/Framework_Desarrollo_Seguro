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
  ApiNotFoundResponse,
  ApiOkResponse,
  ApiOperation,
  ApiTags,
} from '@nestjs/swagger';
import { CrearUsuarioDto } from './dto/crear-usuario.dto';
import { UsuarioRespuestaDto } from './dto/usuario-respuesta.dto';
import { UsuariosService } from './usuarios.service';

@ApiTags('usuarios')
@Controller('usuarios')
export class UsuariosController {
  constructor(private readonly usuariosService: UsuariosService) {}

  @Post()
  @ApiOperation({ summary: 'Registrar un usuario' })
  @ApiCreatedResponse({ type: UsuarioRespuestaDto })
  @ApiBadRequestResponse({ description: 'Datos de entrada inválidos' })
  @ApiConflictResponse({ description: 'El correo ya está registrado' })
  crear(@Body() dto: CrearUsuarioDto): Promise<UsuarioRespuestaDto> {
    return this.usuariosService.crear(dto);
  }

  @Get()
  @ApiOperation({ summary: 'Listar usuarios' })
  @ApiOkResponse({ type: [UsuarioRespuestaDto] })
  listar(): Promise<UsuarioRespuestaDto[]> {
    return this.usuariosService.listar();
  }

  @Get(':id')
  @ApiOperation({ summary: 'Obtener un usuario por id' })
  @ApiOkResponse({ type: UsuarioRespuestaDto })
  @ApiBadRequestResponse({ description: 'El id no es un UUID válido' })
  @ApiNotFoundResponse({ description: 'Usuario no encontrado' })
  obtener(
    @Param('id', new ParseUUIDPipe()) id: string,
  ): Promise<UsuarioRespuestaDto> {
    return this.usuariosService.obtener(id);
  }
}
