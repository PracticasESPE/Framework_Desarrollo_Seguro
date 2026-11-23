import { ApiProperty } from '@nestjs/swagger';
import { IsInt, IsISO8601, IsNumber, Matches, Max, MaxLength, Min } from 'class-validator';
import { FORMATO_FECHA, MENSAJE_FECHA } from '../comun/validacion';

/**
 * Datos para crear VentaReporte. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearVentaReporteDto {
  @ApiProperty({ description: 'Fecha de inicio del rango del reporte', format: 'date', maxLength: 10 })
  @Matches(FORMATO_FECHA, { message: MENSAJE_FECHA })
  @IsISO8601({ strict: true })
  fechaInicio!: string;

  @ApiProperty({ description: 'Fecha de fin del rango del reporte', format: 'date', maxLength: 10 })
  @Matches(FORMATO_FECHA, { message: MENSAJE_FECHA })
  @IsISO8601({ strict: true })
  fechaFin!: string;

  @ApiProperty({ description: 'Importe total de ventas en el rango', type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(9999999999.99)
  totalVentas!: number;

  @ApiProperty({ description: 'Cantidad total de ítems vendidos', type: 'integer', format: 'int32', minimum: 0, maximum: 2147483647 })
  @IsInt()
  @Min(0)
  @Max(2147483647)
  totalItems!: number;

  @ApiProperty({ description: 'Momento en que se generó el reporte', format: 'date-time', maxLength: 30 })
  @MaxLength(30)
  @IsISO8601({ strict: true, strictSeparator: true })
  generadoEn!: string;
}
