import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsInt, IsNumber, IsOptional, IsUUID, Max, Min } from 'class-validator';

/**
 * Datos para crear LineaPedido. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearLineaPedidoDto {
  @ApiPropertyOptional({ description: 'referencia al pedido al que pertenece la línea', nullable: true, format: 'uuid', maxLength: 36 })
  @IsOptional()
  @IsUUID()
  pedidoId?: string;

  @ApiPropertyOptional({ description: 'referencia al carrito cuando la línea está en fase de carrito', nullable: true, format: 'uuid', maxLength: 36 })
  @IsOptional()
  @IsUUID()
  carritoId?: string;

  @ApiProperty({ description: 'identificador del producto en el servicio de catálogo', format: 'uuid', maxLength: 36 })
  @IsUUID()
  productoId!: string;

  @ApiProperty({ type: 'integer', format: 'int32', minimum: 1, maximum: 10 })
  @IsInt()
  @Min(1)
  @Max(10)
  cantidad!: number;

  @ApiProperty({ type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(9999999999.99)
  precioUnitario!: number;

  @ApiProperty({ type: 'number', minimum: 0.0, maximum: 9999999999.99 })
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(9999999999.99)
  subtotal!: number;
}
