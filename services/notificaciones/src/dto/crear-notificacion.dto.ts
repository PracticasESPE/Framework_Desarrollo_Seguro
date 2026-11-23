import { ApiProperty } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsBoolean, IsEmail, IsIn, IsISO8601, IsUUID, MaxLength } from 'class-validator';
import { normalizarCorreo } from '../comun/validacion';

/**
 * Datos para crear Notificacion. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearNotificacionDto {
  @ApiProperty({ description: 'Identificador del pedido (servicio pedidos)', format: 'uuid', maxLength: 36 })
  @IsUUID()
  pedidoId!: string;

  @ApiProperty({ description: 'Identificador del cliente (servicio usuarios)', format: 'uuid', maxLength: 36 })
  @IsUUID()
  clienteId!: string;

  @ApiProperty({ format: 'email', maxLength: 254 })
  @Transform(normalizarCorreo)
  @IsEmail()
  @MaxLength(254)
  clienteEmail!: string;

  @ApiProperty({ enum: ['pedido_aceptado', 'pedido_pagado', 'pedido_estado_cambiado'] })
  @IsIn(['pedido_aceptado', 'pedido_pagado', 'pedido_estado_cambiado'])
  tipo!: 'pedido_aceptado' | 'pedido_pagado' | 'pedido_estado_cambiado';

  @ApiProperty({ format: 'uuid', maxLength: 36 })
  @IsUUID()
  plantillaCorreoId!: string;

  @ApiProperty({ type: 'boolean' })
  @IsBoolean()
  enviado!: boolean;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  @MaxLength(30)
  @IsISO8601({ strict: true, strictSeparator: true })
  fechaHora!: string;
}
