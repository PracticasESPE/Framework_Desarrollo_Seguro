import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsInt, IsISO8601, IsNumber, Matches, Max, MaxLength, Min, ValidateIf } from 'class-validator';
import { FORMATO_FECHA, MENSAJE_FECHA, seEnvio } from '../comun/validacion';

/**
 * Cambios de VentaReporte: los mismos campos y límites que CrearVentaReporteDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarVentaReporteDto {
  @ApiPropertyOptional({ description: 'Fecha de inicio del rango del reporte', format: 'date', maxLength: 10 })
  @ValidateIf(seEnvio)
  @Matches(FORMATO_FECHA, { message: MENSAJE_FECHA })
  @IsISO8601({ strict: true })
  fechaInicio?: string;

  @ApiPropertyOptional({ description: 'Fecha de fin del rango del reporte', format: 'date', maxLength: 10 })
  @ValidateIf(seEnvio)
  @Matches(FORMATO_FECHA, { message: MENSAJE_FECHA })
  @IsISO8601({ strict: true })
  fechaFin?: string;

  @ApiPropertyOptional({ description: 'Importe total de ventas en el rango', type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  @ValidateIf(seEnvio)
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(9999999999.99)
  totalVentas?: number;

  @ApiPropertyOptional({ description: 'Cantidad total de ítems vendidos', type: 'integer', format: 'int32', minimum: 0, maximum: 2147483647 })
  @ValidateIf(seEnvio)
  @IsInt()
  @Min(0)
  @Max(2147483647)
  totalItems?: number;

  @ApiPropertyOptional({ description: 'Momento en que se generó el reporte', format: 'date-time', maxLength: 30 })
  @ValidateIf(seEnvio)
  @MaxLength(30)
  @IsISO8601({ strict: true, strictSeparator: true })
  generadoEn?: string;
}
