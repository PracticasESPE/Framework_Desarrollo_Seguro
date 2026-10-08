import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

export class UsuarioRespuestaDto {
  @ApiProperty({
    format: 'uuid',
    example: '3f2b8c1e-9d4a-4c7e-8a55-1b2c3d4e5f60',
  })
  id!: string;

  @ApiProperty({ example: 'Ana Pérez' })
  nombre!: string;

  @ApiProperty({ example: 'ana.perez@example.com' })
  correo!: string;

  @ApiPropertyOptional({ example: '+593991234567' })
  telefono?: string;

  @ApiProperty({ format: 'date-time' })
  creadoEn!: string;
}
