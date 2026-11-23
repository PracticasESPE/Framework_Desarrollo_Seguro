import { ApiProperty } from '@nestjs/swagger';

/**
 * Transaccion tal como la devuelve la API. Los límites coinciden con CrearTransaccionDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class TransaccionRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ format: 'uuid', maxLength: 36 })
  pagoId!: string;

  @ApiProperty({ enum: ['autorizacion', 'captura', 'reembolso'] })
  tipo!: 'autorizacion' | 'captura' | 'reembolso';

  @ApiProperty({ type: 'number', minimum: 0.0, maximum: 1000000.0 })
  importe!: number;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  fechaHora!: string;

  @ApiProperty({ description: 'Identificador de la transacción en la pasarela externa', format: 'uuid', maxLength: 36 })
  externalTransactionId!: string;

  @ApiProperty({ enum: ['pendiente', 'completado', 'fallido'] })
  estado!: 'pendiente' | 'completado' | 'fallido';

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
