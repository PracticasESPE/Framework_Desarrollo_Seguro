import { ApiProperty } from '@nestjs/swagger';
import { PATRON_SIN_CONTROL } from '../comun/validacion';

/**
 * PlantillaCorreo tal como la devuelve la API. Los límites coinciden con CrearPlantillaCorreoDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class PlantillaCorreoRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ maxLength: 100, pattern: PATRON_SIN_CONTROL })
  nombre!: string;

  @ApiProperty({ maxLength: 150, pattern: PATRON_SIN_CONTROL })
  asunto!: string;

  @ApiProperty({ maxLength: 2000, pattern: PATRON_SIN_CONTROL })
  cuerpo!: string;

  @ApiProperty({ enum: ['pedido_aceptado', 'pedido_pagado', 'pedido_estado_cambiado'] })
  tipo!: 'pedido_aceptado' | 'pedido_pagado' | 'pedido_estado_cambiado';

  @ApiProperty({ type: 'boolean' })
  activo!: boolean;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
