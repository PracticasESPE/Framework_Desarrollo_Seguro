import { ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsIn, IsISO8601, IsString, IsUUID, Matches, MaxLength, MinLength, ValidateIf } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, seEnvio, SIN_CONTROL } from '../comun/validacion';

/**
 * Cambios de AuditoriaLog: los mismos campos y límites que CrearAuditoriaLogDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarAuditoriaLogDto {
  @ApiPropertyOptional({ description: 'Identificador del administrador en Keycloak', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  adminId?: string;

  @ApiPropertyOptional({ description: 'Tipo de acción realizada', enum: ['crear', 'actualizar', 'eliminar'] })
  @ValidateIf(seEnvio)
  @IsIn(['crear', 'actualizar', 'eliminar'])
  accion?: 'crear' | 'actualizar' | 'eliminar';

  @ApiPropertyOptional({ description: 'Tipo de entidad afectada', enum: ['producto', 'pedido'] })
  @ValidateIf(seEnvio)
  @IsIn(['producto', 'pedido'])
  entidad?: 'producto' | 'pedido';

  @ApiPropertyOptional({ description: 'Identificador del producto o pedido en su servicio', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  entidadId?: string;

  @ApiPropertyOptional({ description: 'Descripción de los cambios realizados', minLength: 1, maxLength: 1000, pattern: PATRON_SIN_CONTROL })
  @ValidateIf(seEnvio)
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(1000)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  detalleCambio?: string;

  @ApiPropertyOptional({ description: 'Momento en que se realizó la acción', format: 'date-time', maxLength: 30 })
  @ValidateIf(seEnvio)
  @MaxLength(30)
  @IsISO8601({ strict: true, strictSeparator: true })
  fechaHora?: string;
}
