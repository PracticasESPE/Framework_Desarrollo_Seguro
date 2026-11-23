import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { PATRON_SIN_CONTROL } from '../comun/validacion';

/**
 * Foto tal como la devuelve la API. Los límites coinciden con CrearFotoDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class FotoRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ description: 'URL donde se almacena la foto', maxLength: 2048, pattern: PATRON_SIN_CONTROL })
  url!: string;

  @ApiProperty({ description: 'Referencia al producto al que pertenece la foto', format: 'uuid', maxLength: 36 })
  productoId!: string;

  @ApiProperty({ description: 'Formato de la imagen', enum: ['jpg', 'png'] })
  tipo!: 'jpg' | 'png';

  @ApiPropertyOptional({ description: 'Posición de la foto dentro del conjunto (máximo 5 fotos por producto)', type: 'integer', format: 'int32', minimum: 1, maximum: 5 })
  orden?: number;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
