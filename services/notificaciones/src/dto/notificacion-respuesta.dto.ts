import { ApiProperty } from '@nestjs/swagger';

/**
 * Notificacion tal como la devuelve la API. Los límites coinciden con CrearNotificacionDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class NotificacionRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ description: 'Identificador del pedido (servicio pedidos)', format: 'uuid', maxLength: 36 })
  pedidoId!: string;

  @ApiProperty({ description: 'Identificador del cliente (servicio usuarios)', format: 'uuid', maxLength: 36 })
  clienteId!: string;

  @ApiProperty({ format: 'email', maxLength: 254 })
  clienteEmail!: string;

  @ApiProperty({ enum: ['pedido_aceptado', 'pedido_pagado', 'pedido_estado_cambiado'] })
  tipo!: 'pedido_aceptado' | 'pedido_pagado' | 'pedido_estado_cambiado';

  @ApiProperty({ format: 'uuid', maxLength: 36 })
  plantillaCorreoId!: string;

  @ApiProperty({ type: 'boolean' })
  enviado!: boolean;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  fechaHora!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
