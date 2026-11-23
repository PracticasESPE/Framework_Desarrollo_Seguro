import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

/**
 * LineaPedido tal como la devuelve la API. Los límites coinciden con CrearLineaPedidoDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class LineaPedidoRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiPropertyOptional({ description: 'referencia al pedido al que pertenece la línea', format: 'uuid', maxLength: 36 })
  pedidoId?: string;

  @ApiPropertyOptional({ description: 'referencia al carrito cuando la línea está en fase de carrito', format: 'uuid', maxLength: 36 })
  carritoId?: string;

  @ApiProperty({ description: 'identificador del producto en el servicio de catálogo', format: 'uuid', maxLength: 36 })
  productoId!: string;

  @ApiProperty({ type: 'integer', format: 'int32', minimum: 1, maximum: 10 })
  cantidad!: number;

  @ApiProperty({ type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  precioUnitario!: number;

  @ApiProperty({ type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  subtotal!: number;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
