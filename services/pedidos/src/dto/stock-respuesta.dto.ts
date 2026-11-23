import { ApiProperty } from '@nestjs/swagger';

/**
 * Stock tal como la devuelve la API. Los límites coinciden con CrearStockDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class StockRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ description: 'identificador del producto en el servicio de catálogo', format: 'uuid', maxLength: 36 })
  productoId!: string;

  @ApiProperty({ type: 'integer', format: 'int32', minimum: 0, maximum: 2147483647 })
  cantidad!: number;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
