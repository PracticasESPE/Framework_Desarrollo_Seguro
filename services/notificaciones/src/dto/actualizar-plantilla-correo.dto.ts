import { ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsBoolean, IsIn, IsString, Matches, MaxLength, MinLength, ValidateIf } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, seEnvio, SIN_CONTROL } from '../comun/validacion';

/**
 * Cambios de PlantillaCorreo: los mismos campos y límites que CrearPlantillaCorreoDto, todos
 * opcionales. Lo que no se envía no cambia; un campo opcional enviado como null se vacía, y uno
 * obligatorio no admite null.
 */
export class ActualizarPlantillaCorreoDto {
  @ApiPropertyOptional({ minLength: 1, maxLength: 100, pattern: PATRON_SIN_CONTROL })
  @ValidateIf(seEnvio)
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(100)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  nombre?: string;

  @ApiPropertyOptional({ minLength: 1, maxLength: 150, pattern: PATRON_SIN_CONTROL })
  @ValidateIf(seEnvio)
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(150)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  asunto?: string;

  @ApiPropertyOptional({ minLength: 1, maxLength: 2000, pattern: PATRON_SIN_CONTROL })
  @ValidateIf(seEnvio)
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(2000)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  cuerpo?: string;

  @ApiPropertyOptional({ enum: ['pedido_aceptado', 'pedido_pagado', 'pedido_estado_cambiado'] })
  @ValidateIf(seEnvio)
  @IsIn(['pedido_aceptado', 'pedido_pagado', 'pedido_estado_cambiado'])
  tipo?: 'pedido_aceptado' | 'pedido_pagado' | 'pedido_estado_cambiado';

  @ApiPropertyOptional({ type: 'boolean' })
  @ValidateIf(seEnvio)
  @IsBoolean()
  activo?: boolean;
}
