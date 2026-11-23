import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

/**
 * Pedido tal como la devuelve la API. Los límites coinciden con CrearPedidoDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class PedidoRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ description: 'identificador del cliente en Keycloak', format: 'uuid', maxLength: 36 })
  clienteId!: string;

  @ApiProperty({ enum: ['pendiente', 'confirmado', 'pagado', 'en_preparacion', 'enviado', 'entregado', 'cancelado', 'expirado'] })
  estado!: 'pendiente' | 'confirmado' | 'pagado' | 'en_preparacion' | 'enviado' | 'entregado' | 'cancelado' | 'expirado';

  @ApiProperty({ type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  total!: number;

  @ApiPropertyOptional({ description: 'identificador del pago en la pasarela de pagos', format: 'uuid', maxLength: 36 })
  pagoId?: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
