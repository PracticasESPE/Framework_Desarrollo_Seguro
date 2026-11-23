import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsInt, IsNumber, IsOptional, IsUUID, Max, Min, ValidateIf } from 'class-validator';
import { seEnvio } from '../comun/validacion';

/**
 * Cambios de LineaPedido: los mismos campos y límites que CrearLineaPedidoDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarLineaPedidoDto {
  @ApiPropertyOptional({ description: 'referencia al pedido al que pertenece la línea', nullable: true, format: 'uuid', maxLength: 36 })
  @IsOptional()
  @IsUUID()
  pedidoId?: string;

  @ApiPropertyOptional({ description: 'referencia al carrito cuando la línea está en fase de carrito', nullable: true, format: 'uuid', maxLength: 36 })
  @IsOptional()
  @IsUUID()
  carritoId?: string;

  @ApiPropertyOptional({ description: 'identificador del producto en el servicio de catálogo', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  productoId?: string;

  @ApiPropertyOptional({ type: 'integer', format: 'int32', minimum: 1, maximum: 10 })
  @ValidateIf(seEnvio)
  @IsInt()
  @Min(1)
  @Max(10)
  cantidad?: number;

  @ApiPropertyOptional({ type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  @ValidateIf(seEnvio)
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(9999999999.99)
  precioUnitario?: number;

  @ApiPropertyOptional({ type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  @ValidateIf(seEnvio)
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(9999999999.99)
  subtotal?: number;
}
