import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsIn, IsInt, IsOptional, IsString, IsUUID, Matches, Max, MaxLength, Min, MinLength } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, SIN_CONTROL } from '../comun/validacion';

/**
 * Datos para crear Foto. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearFotoDto {
  @ApiProperty({ description: 'URL donde se almacena la foto', minLength: 1, maxLength: 2048, pattern: PATRON_SIN_CONTROL })
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(2048)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  url!: string;

  @ApiProperty({ description: 'Referencia al producto al que pertenece la foto', format: 'uuid', maxLength: 36 })
  @IsUUID()
  productoId!: string;

  @ApiProperty({ description: 'Formato de la imagen', enum: ['jpg', 'png'] })
  @IsIn(['jpg', 'png'])
  tipo!: 'jpg' | 'png';

  @ApiPropertyOptional({ description: 'Posición de la foto dentro del conjunto (máximo 5 fotos por producto)', nullable: true, type: 'integer', format: 'int32', minimum: 1, maximum: 5 })
  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(5)
  orden?: number;
}
