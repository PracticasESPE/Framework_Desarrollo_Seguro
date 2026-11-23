import { ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsIn, IsNumber, IsOptional, IsString, IsUUID, Matches, Max, MaxLength, Min, MinLength, ValidateIf } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, seEnvio, SIN_CONTROL } from '../comun/validacion';

/**
 * Cambios de Pago: los mismos campos y límites que CrearPagoDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarPagoDto {
  @ApiPropertyOptional({ type: 'number', minimum: 0.0, maximum: 1000000.0 })
  @ValidateIf(seEnvio)
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(1000000.0)
  importe?: number;

  @ApiPropertyOptional({ minLength: 3, maxLength: 3, pattern: PATRON_SIN_CONTROL })
  @ValidateIf(seEnvio)
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(3)
  @MaxLength(3)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  moneda?: string;

  @ApiPropertyOptional({ enum: ['pendiente', 'aprobado', 'rechazado', 'error'] })
  @ValidateIf(seEnvio)
  @IsIn(['pendiente', 'aprobado', 'rechazado', 'error'])
  estado?: 'pendiente' | 'aprobado' | 'rechazado' | 'error';

  @ApiPropertyOptional({ description: 'Identificador del pago en la pasarela externa', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  externalPaymentId?: string;

  @ApiPropertyOptional({ description: 'Identificador del pedido en el servicio de pedidos', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  pedidoId?: string;

  @ApiPropertyOptional({ nullable: true, format: 'uuid', maxLength: 36 })
  @IsOptional()
  @IsUUID()
  transaccionId?: string;
}
