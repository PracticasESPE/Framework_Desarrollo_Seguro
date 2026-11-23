import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsUUID, ValidateIf } from 'class-validator';
import { seEnvio } from '../comun/validacion';

/**
 * Cambios de Carrito: los mismos campos y límites que CrearCarritoDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarCarritoDto {
  @ApiPropertyOptional({ description: 'identificador del cliente en Keycloak', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  clienteId?: string;
}
