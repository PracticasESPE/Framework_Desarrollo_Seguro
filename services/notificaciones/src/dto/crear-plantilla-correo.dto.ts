import { ApiProperty } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import { IsBoolean, IsIn, IsString, Matches, MaxLength, MinLength } from 'class-validator';
import { limpiarTexto, MENSAJE_SIN_CONTROL, PATRON_SIN_CONTROL, SIN_CONTROL } from '../comun/validacion';

/**
 * Datos para crear PlantillaCorreo. Generado por la plantilla: cada campo tiene su tipo y sus
 * límites, los mismos que prisma/schema.prisma y que el contrato OpenAPI.
 */
export class CrearPlantillaCorreoDto {
  @ApiProperty({ minLength: 1, maxLength: 100, pattern: PATRON_SIN_CONTROL })
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(100)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  nombre!: string;

  @ApiProperty({ minLength: 1, maxLength: 150, pattern: PATRON_SIN_CONTROL })
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(150)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  asunto!: string;

  @ApiProperty({ minLength: 1, maxLength: 2000, pattern: PATRON_SIN_CONTROL })
  @Transform(limpiarTexto)
  @IsString()
  @MinLength(1)
  @MaxLength(2000)
  @Matches(SIN_CONTROL, { message: MENSAJE_SIN_CONTROL })
  cuerpo!: string;

  @ApiProperty({ enum: ['pedido_aceptado', 'pedido_pagado', 'pedido_estado_cambiado'] })
  @IsIn(['pedido_aceptado', 'pedido_pagado', 'pedido_estado_cambiado'])
  tipo!: 'pedido_aceptado' | 'pedido_pagado' | 'pedido_estado_cambiado';

  @ApiProperty({ type: 'boolean' })
  @IsBoolean()
  activo!: boolean;
}
