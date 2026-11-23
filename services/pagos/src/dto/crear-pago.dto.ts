import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsIn, IsNumber, IsOptional, IsString, IsUUID, Matches, Max, MaxLength, Min, MinLength } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, SIN_CONTROL } from '../comun/validacion';

/**
 * Datos para crear Pago. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearPagoDto {
  @ApiProperty({ type: 'number', minimum: 0.0, maximum: 1000000.0 })
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(1000000.0)
  importe!: number;

  @ApiProperty({ minLength: 3, maxLength: 3, pattern: PATRON_SIN_CONTROL })
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(3)
  @MaxLength(3)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  moneda!: string;

  @ApiProperty({ enum: ['pendiente', 'aprobado', 'rechazado', 'error'] })
  @IsIn(['pendiente', 'aprobado', 'rechazado', 'error'])
  estado!: 'pendiente' | 'aprobado' | 'rechazado' | 'error';

  @ApiProperty({ description: 'Identificador del pago en la pasarela externa', format: 'uuid', maxLength: 36 })
  @IsUUID()
  externalPaymentId!: string;

  @ApiProperty({ description: 'Identificador del pedido en el servicio de pedidos', format: 'uuid', maxLength: 36 })
  @IsUUID()
  pedidoId!: string;

  @ApiPropertyOptional({ nullable: true, format: 'uuid', maxLength: 36 })
  @IsOptional()
  @IsUUID()
  transaccionId?: string;
}
