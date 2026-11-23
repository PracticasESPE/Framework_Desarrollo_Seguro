import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsIn, IsNumber, IsOptional, IsUUID, Max, Min, ValidateIf } from 'class-validator';
import { seEnvio } from '../comun/validacion';

/**
 * Cambios de Pedido: los mismos campos y límites que CrearPedidoDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarPedidoDto {
  @ApiPropertyOptional({ description: 'identificador del cliente en Keycloak', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  clienteId?: string;

  @ApiPropertyOptional({ enum: ['pendiente', 'confirmado', 'pagado', 'en_preparacion', 'enviado', 'entregado', 'cancelado', 'expirado'] })
  @ValidateIf(seEnvio)
  @IsIn(['pendiente', 'confirmado', 'pagado', 'en_preparacion', 'enviado', 'entregado', 'cancelado', 'expirado'])
  estado?: 'pendiente' | 'confirmado' | 'pagado' | 'en_preparacion' | 'enviado' | 'entregado' | 'cancelado' | 'expirado';

  @ApiPropertyOptional({ type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  @ValidateIf(seEnvio)
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(9999999999.99)
  total?: number;

  @ApiPropertyOptional({ description: 'identificador del pago en la pasarela de pagos', nullable: true, format: 'uuid', maxLength: 36 })
  @IsOptional()
  @IsUUID()
  pagoId?: string;
}
