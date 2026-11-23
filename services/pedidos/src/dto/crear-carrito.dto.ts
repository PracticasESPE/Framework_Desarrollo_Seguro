import { ApiProperty } from '@nestjs/swagger';
import { IsUUID } from 'class-validator';

/**
 * Datos para crear Carrito. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearCarritoDto {
  @ApiProperty({ description: 'identificador del cliente en Keycloak', format: 'uuid', maxLength: 36 })
  @IsUUID()
  clienteId!: string;
}
