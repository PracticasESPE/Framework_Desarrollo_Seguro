import { ApiProperty } from '@nestjs/swagger';
import { PATRON_SIN_CONTROL } from '../comun/validacion';

/**
 * AuditoriaLog tal como la devuelve la API. Los límites coinciden con CrearAuditoriaLogDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class AuditoriaLogRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ description: 'Identificador del administrador en Keycloak', format: 'uuid', maxLength: 36 })
  adminId!: string;

  @ApiProperty({ description: 'Tipo de acción realizada', enum: ['crear', 'actualizar', 'eliminar'] })
  accion!: 'crear' | 'actualizar' | 'eliminar';

  @ApiProperty({ description: 'Tipo de entidad afectada', enum: ['producto', 'pedido'] })
  entidad!: 'producto' | 'pedido';

  @ApiProperty({ description: 'Identificador del producto o pedido en su servicio', format: 'uuid', maxLength: 36 })
  entidadId!: string;

  @ApiProperty({ description: 'Descripción de los cambios realizados', maxLength: 1000, pattern: PATRON_SIN_CONTROL })
  detalleCambio!: string;

  @ApiProperty({ description: 'Momento en que se realizó la acción', format: 'date-time', maxLength: 30 })
  fechaHora!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
