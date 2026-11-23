import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsIn, IsNumber, IsOptional, IsUUID, Max, Min } from 'class-validator';

/**
 * Datos para crear Pedido. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearPedidoDto {
  @ApiProperty({ description: 'identificador del cliente en Keycloak', format: 'uuid', maxLength: 36 })
  @IsUUID()
  clienteId!: string;

  @ApiProperty({ enum: ['pendiente', 'confirmado', 'pagado', 'en_preparacion', 'enviado', 'entregado', 'cancelado', 'expirado'] })
  @IsIn(['pendiente', 'confirmado', 'pagado', 'en_preparacion', 'enviado', 'entregado', 'cancelado', 'expirado'])
  estado!: 'pendiente' | 'confirmado' | 'pagado' | 'en_preparacion' | 'enviado' | 'entregado' | 'cancelado' | 'expirado';

  @ApiProperty({ type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(9999999999.99)
  total!: number;

  @ApiPropertyOptional({ description: 'identificador del pago en la pasarela de pagos', nullable: true, format: 'uuid', maxLength: 36 })
  @IsOptional()
  @IsUUID()
  pagoId?: string;
}
