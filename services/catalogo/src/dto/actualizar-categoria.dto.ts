import { ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsOptional, IsString, Matches, MaxLength, MinLength, ValidateIf } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, seEnvio, SIN_CONTROL } from '../comun/validacion';

/**
 * Cambios de Categoria: los mismos campos y límites que CrearCategoriaDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarCategoriaDto {
  @ApiPropertyOptional({ description: 'Nombre de la categoría', minLength: 1, maxLength: 100, pattern: PATRON_SIN_CONTROL })
  @ValidateIf(seEnvio)
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(100)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  nombre?: string;

  @ApiPropertyOptional({ description: 'Descripción de la categoría', nullable: true, minLength: 0, maxLength: 500, pattern: PATRON_SIN_CONTROL })
  @IsOptional()
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(0)
  @MaxLength(500)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  descripcion?: string;
}
