import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { PATRON_SIN_CONTROL } from '../comun/validacion';

/**
 * Pago tal como la devuelve la API. Los límites coinciden con CrearPagoDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class PagoRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ type: 'number', minimum: 0.0, maximum: 1000000.0 })
  importe!: number;

  @ApiProperty({ maxLength: 3, pattern: PATRON_SIN_CONTROL })
  moneda!: string;

  @ApiProperty({ enum: ['pendiente', 'aprobado', 'rechazado', 'error'] })
  estado!: 'pendiente' | 'aprobado' | 'rechazado' | 'error';

  @ApiProperty({ description: 'Identificador del pago en la pasarela externa', format: 'uuid', maxLength: 36 })
  externalPaymentId!: string;

  @ApiProperty({ description: 'Identificador del pedido en el servicio de pedidos', format: 'uuid', maxLength: 36 })
  pedidoId!: string;

  @ApiPropertyOptional({ format: 'uuid', maxLength: 36 })
  transaccionId?: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
