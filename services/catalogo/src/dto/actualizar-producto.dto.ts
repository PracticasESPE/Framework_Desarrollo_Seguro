import { ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsBoolean, IsInt, IsNumber, IsString, IsUUID, Matches, Max, MaxLength, Min, MinLength, ValidateIf } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, seEnvio, SIN_CONTROL } from '../comun/validacion';

/**
 * Cambios de Producto: los mismos campos y límites que CrearProductoDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarProductoDto {
  @ApiPropertyOptional({ description: 'Nombre del producto', minLength: 1, maxLength: 100, pattern: PATRON_SIN_CONTROL })
  @ValidateIf(seEnvio)
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(100)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  nombre?: string;

  @ApiPropertyOptional({ description: 'Descripción detallada del producto', minLength: 1, maxLength: 1000, pattern: PATRON_SIN_CONTROL })
  @ValidateIf(seEnvio)
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(1000)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  descripcion?: string;

  @ApiPropertyOptional({ description: 'Precio del producto', type: 'number', minimum: 0.0, maximum: 999999.99 })
  @ValidateIf(seEnvio)
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(999999.99)
  precio?: number;

  @ApiPropertyOptional({ description: 'Cantidad de unidades disponibles en stock', type: 'integer', format: 'int32', minimum: 0, maximum: 1000000 })
  @ValidateIf(seEnvio)
  @IsInt()
  @Min(0)
  @Max(1000000)
  unidadesDisponibles?: number;

  @ApiPropertyOptional({ description: 'Referencia a la categoría del producto', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  categoriaId?: string;

  @ApiPropertyOptional({ description: 'Indica si el producto está retirado del catálogo', type: 'boolean' })
  @ValidateIf(seEnvio)
  @IsBoolean()
  retirado?: boolean;
}
