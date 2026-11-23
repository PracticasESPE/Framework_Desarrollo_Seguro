import { ApiProperty } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsIn, IsISO8601, IsString, IsUUID, Matches, MaxLength, MinLength } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, SIN_CONTROL } from '../comun/validacion';

/**
 * Datos para crear AuditoriaLog. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearAuditoriaLogDto {
  @ApiProperty({ description: 'Identificador del administrador en Keycloak', format: 'uuid', maxLength: 36 })
  @IsUUID()
  adminId!: string;

  @ApiProperty({ description: 'Tipo de acción realizada', enum: ['crear', 'actualizar', 'eliminar'] })
  @IsIn(['crear', 'actualizar', 'eliminar'])
  accion!: 'crear' | 'actualizar' | 'eliminar';

  @ApiProperty({ description: 'Tipo de entidad afectada', enum: ['producto', 'pedido'] })
  @IsIn(['producto', 'pedido'])
  entidad!: 'producto' | 'pedido';

  @ApiProperty({ description: 'Identificador del producto o pedido en su servicio', format: 'uuid', maxLength: 36 })
  @IsUUID()
  entidadId!: string;

  @ApiProperty({ description: 'Descripción de los cambios realizados', minLength: 1, maxLength: 1000, pattern: PATRON_SIN_CONTROL })
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(1000)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  detalleCambio!: string;

  @ApiProperty({ description: 'Momento en que se realizó la acción', format: 'date-time', maxLength: 30 })
  @MaxLength(30)
  @IsISO8601({ strict: true, strictSeparator: true })
  fechaHora!: string;
}
