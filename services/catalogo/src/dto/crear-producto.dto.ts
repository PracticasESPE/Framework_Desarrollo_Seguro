import { ApiProperty } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsBoolean, IsInt, IsNumber, IsString, IsUUID, Matches, Max, MaxLength, Min, MinLength } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, SIN_CONTROL } from '../comun/validacion';

/**
 * Datos para crear Producto. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearProductoDto {
  @ApiProperty({ description: 'Nombre del producto', minLength: 1, maxLength: 100, pattern: PATRON_SIN_CONTROL })
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(100)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  nombre!: string;

  @ApiProperty({ description: 'Descripción detallada del producto', minLength: 1, maxLength: 1000, pattern: PATRON_SIN_CONTROL })
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(1000)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  descripcion!: string;

  @ApiProperty({ description: 'Precio del producto', type: 'number', minimum: 0.0, maximum: 999999.99 })
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(999999.99)
  precio!: number;

  @ApiProperty({ description: 'Cantidad de unidades disponibles en stock', type: 'integer', format: 'int32', minimum: 0, maximum: 1000000 })
  @IsInt()
  @Min(0)
  @Max(1000000)
  unidadesDisponibles!: number;

  @ApiProperty({ description: 'Referencia a la categoría del producto', format: 'uuid', maxLength: 36 })
  @IsUUID()
  categoriaId!: string;

  @ApiProperty({ description: 'Indica si el producto está retirado del catálogo', type: 'boolean' })
  @IsBoolean()
  retirado!: boolean;
}
