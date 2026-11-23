import { ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsIn, IsInt, IsOptional, IsString, IsUUID, Matches, Max, MaxLength, Min, MinLength, ValidateIf } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, seEnvio, SIN_CONTROL } from '../comun/validacion';

/**
 * Cambios de Foto: los mismos campos y límites que CrearFotoDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarFotoDto {
  @ApiPropertyOptional({ description: 'URL donde se almacena la foto', minLength: 1, maxLength: 2048, pattern: PATRON_SIN_CONTROL })
  @ValidateIf(seEnvio)
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(2048)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  url?: string;

  @ApiPropertyOptional({ description: 'Referencia al producto al que pertenece la foto', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  productoId?: string;

  @ApiPropertyOptional({ description: 'Formato de la imagen', enum: ['jpg', 'png'] })
  @ValidateIf(seEnvio)
  @IsIn(['jpg', 'png'])
  tipo?: 'jpg' | 'png';

  @ApiPropertyOptional({ description: 'Posición de la foto dentro del conjunto (máximo 5 fotos por producto)', nullable: true, type: 'integer', format: 'int32', minimum: 1, maximum: 5 })
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(5)
  orden?: number;
}
