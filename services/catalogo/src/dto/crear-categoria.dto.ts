import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsOptional, IsString, Matches, MaxLength, MinLength } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, SIN_CONTROL } from '../comun/validacion';

/**
 * Datos para crear Categoria. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearCategoriaDto {
  @ApiProperty({ description: 'Nombre de la categoría', minLength: 1, maxLength: 100, pattern: PATRON_SIN_CONTROL })
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(100)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  nombre!: string;

  @ApiPropertyOptional({ description: 'Descripción de la categoría', nullable: true, minLength: 0, maxLength: 500, pattern: PATRON_SIN_CONTROL })
  @IsOptional()
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(0)
  @MaxLength(500)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  descripcion?: string;
}
