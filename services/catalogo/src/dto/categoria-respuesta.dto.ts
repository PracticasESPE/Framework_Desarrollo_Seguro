import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { PATRON_SIN_CONTROL } from '../comun/validacion';

/**
 * Categoria tal como la devuelve la API. Los límites coinciden con CrearCategoriaDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class CategoriaRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ description: 'Nombre de la categoría', maxLength: 100, pattern: PATRON_SIN_CONTROL })
  nombre!: string;

  @ApiPropertyOptional({ description: 'Descripción de la categoría', maxLength: 500, pattern: PATRON_SIN_CONTROL })
  descripcion?: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
