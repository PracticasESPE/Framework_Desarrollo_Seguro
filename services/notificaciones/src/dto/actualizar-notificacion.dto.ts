import { ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsBoolean, IsEmail, IsIn, IsISO8601, IsUUID, MaxLength, ValidateIf } from 'class-validator';
import { normalizarCorreo, seEnvio } from '../comun/validacion';

/**
 * Cambios de Notificacion: los mismos campos y límites que CrearNotificacionDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarNotificacionDto {
  @ApiPropertyOptional({ description: 'Identificador del pedido (servicio pedidos)', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  pedidoId?: string;

  @ApiPropertyOptional({ description: 'Identificador del cliente (servicio usuarios)', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  clienteId?: string;

  @ApiPropertyOptional({ format: 'email', maxLength: 254 })
  @ValidateIf(seEnvio)
  @Transform(normalizarCorreo)
  @IsEmail()
  @MaxLength(254)
  clienteEmail?: string;

  @ApiPropertyOptional({ enum: ['pedido_aceptado', 'pedido_pagado', 'pedido_estado_cambiado'] })
  @ValidateIf(seEnvio)
  @IsIn(['pedido_aceptado', 'pedido_pagado', 'pedido_estado_cambiado'])
  tipo?: 'pedido_aceptado' | 'pedido_pagado' | 'pedido_estado_cambiado';

  @ApiPropertyOptional({ format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  plantillaCorreoId?: string;

  @ApiPropertyOptional({ type: 'boolean' })
  @ValidateIf(seEnvio)
  @IsBoolean()
  enviado?: boolean;

  @ApiPropertyOptional({ format: 'date-time', maxLength: 30 })
  @ValidateIf(seEnvio)
  @MaxLength(30)
  @IsISO8601({ strict: true, strictSeparator: true })
  fechaHora?: string;
}
