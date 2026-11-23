import { ApiProperty } from '@nestjs/swagger';

/**
 * Carrito tal como la devuelve la API. Los límites coinciden con CrearCarritoDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class CarritoRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ description: 'identificador del cliente en Keycloak', format: 'uuid', maxLength: 36 })
  clienteId!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
