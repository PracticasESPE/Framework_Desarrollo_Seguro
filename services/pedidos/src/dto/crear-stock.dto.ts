import { ApiProperty } from '@nestjs/swagger';
import { IsInt, IsUUID, Max, Min } from 'class-validator';

/**
 * Datos para crear Stock. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearStockDto {
  @ApiProperty({ description: 'identificador del producto en el servicio de catálogo', format: 'uuid', maxLength: 36 })
  @IsUUID()
  productoId!: string;

  @ApiProperty({ type: 'integer', format: 'int32', minimum: 0, maximum: 2147483647 })
  @IsInt()
  @Min(0)
  @Max(2147483647)
  cantidad!: number;
}
