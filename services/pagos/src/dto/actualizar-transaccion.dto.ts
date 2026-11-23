import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsIn, IsISO8601, IsNumber, IsUUID, Max, MaxLength, Min, ValidateIf } from 'class-validator';
import { seEnvio } from '../comun/validacion';

/**
 * Cambios de Transaccion: los mismos campos y límites que CrearTransaccionDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarTransaccionDto {
  @ApiPropertyOptional({ format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  pagoId?: string;

  @ApiPropertyOptional({ enum: ['autorizacion', 'captura', 'reembolso'] })
  @ValidateIf(seEnvio)
  @IsIn(['autorizacion', 'captura', 'reembolso'])
  tipo?: 'autorizacion' | 'captura' | 'reembolso';

  @ApiPropertyOptional({ type: 'number', minimum: 0.0, maximum: 1000000.0 })
  @ValidateIf(seEnvio)
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(1000000.0)
  importe?: number;

  @ApiPropertyOptional({ format: 'date-time', maxLength: 30 })
  @ValidateIf(seEnvio)
  @MaxLength(30)
  @IsISO8601({ strict: true, strictSeparator: true })
  fechaHora?: string;

  @ApiPropertyOptional({ description: 'Identificador de la transacción en la pasarela externa', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  externalTransactionId?: string;

  @ApiPropertyOptional({ enum: ['pendiente', 'completado', 'fallido'] })
  @ValidateIf(seEnvio)
  @IsIn(['pendiente', 'completado', 'fallido'])
  estado?: 'pendiente' | 'completado' | 'fallido';
}
