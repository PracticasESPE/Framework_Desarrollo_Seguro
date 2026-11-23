import { ApiPropertyOptional } from '@nestjs/swagger';
import { IsInt, IsUUID, Max, Min, ValidateIf } from 'class-validator';
import { seEnvio } from '../comun/validacion';

/**
 * Cambios de Stock: los mismos campos y límites que CrearStockDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarStockDto {
  @ApiPropertyOptional({ description: 'identificador del producto en el servicio de catálogo', format: 'uuid', maxLength: 36 })
  @ValidateIf(seEnvio)
  @IsUUID()
  productoId?: string;

  @ApiPropertyOptional({ type: 'integer', format: 'int32', minimum: 0, maximum: 2147483647 })
  @ValidateIf(seEnvio)
  @IsInt()
  @Min(0)
  @Max(2147483647)
  cantidad?: number;
}
