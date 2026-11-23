import { ApiProperty } from '@nestjs/swagger';
import { IsIn, IsISO8601, IsNumber, IsUUID, Max, MaxLength, Min } from 'class-validator';

/**
 * Datos para crear Transaccion. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearTransaccionDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  @IsUUID()
  pagoId!: string;

  @ApiProperty({ enum: ['autorizacion', 'captura', 'reembolso'] })
  @IsIn(['autorizacion', 'captura', 'reembolso'])
  tipo!: 'autorizacion' | 'captura' | 'reembolso';

  @ApiProperty({ type: 'number', minimum: 0.0, maximum: 1000000.0 })
  @IsNumber({ maxDecimalPlaces: 2, allowNaN: false, allowInfinity: false })
  @Min(0.0)
  @Max(1000000.0)
  importe!: number;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  @MaxLength(30)
  @IsISO8601({ strict: true, strictSeparator: true })
  fechaHora!: string;

  @ApiProperty({ description: 'Identificador de la transacción en la pasarela externa', format: 'uuid', maxLength: 36 })
  @IsUUID()
  externalTransactionId!: string;

  @ApiProperty({ enum: ['pendiente', 'completado', 'fallido'] })
  @IsIn(['pendiente', 'completado', 'fallido'])
  estado!: 'pendiente' | 'completado' | 'fallido';
}
