import { ApiProperty } from '@nestjs/swagger';

/**
 * VentaReporte tal como la devuelve la API. Los límites coinciden con CrearVentaReporteDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class VentaReporteRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ description: 'Fecha de inicio del rango del reporte', format: 'date', maxLength: 10 })
  fechaInicio!: string;

  @ApiProperty({ description: 'Fecha de fin del rango del reporte', format: 'date', maxLength: 10 })
  fechaFin!: string;

  @ApiProperty({ description: 'Importe total de ventas en el rango', type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  totalVentas!: number;

  @ApiProperty({ description: 'Cantidad total de ítems vendidos', type: 'integer', format: 'int32', minimum: 0, maximum: 2147483647 })
  totalItems!: number;

  @ApiProperty({ description: 'Momento en que se generó el reporte', format: 'date-time', maxLength: 30 })
  generadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
