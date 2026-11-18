import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';

// Los límites coinciden con CrearUsuarioDto y con prisma/schema.prisma (Gate 2: OWASP API4).
export class UsuarioRespuestaDto {
  @ApiProperty({
    format: 'uuid',
    maxLength: 36,
    example: '3f2b8c1e-9d4a-4c7e-8a55-1b2c3d4e5f60',
  })
  id!: string;

  @ApiProperty({ example: 'Ana Pérez', maxLength: 100 })
  nombre!: string;

  @ApiProperty({
    example: 'ana.perez@example.com',
    format: 'email',
    maxLength: 254,
  })
  correo!: string;

  @ApiPropertyOptional({
    example: '+593991234567',
    pattern: '^\\+?[0-9]{7,15}$',
    maxLength: 16,
  })
  telefono?: string;

  @ApiProperty({
    format: 'date-time',
    maxLength: 30,
    example: '2026-10-21T15:30:00.000Z',
  })
  creadoEn!: string;
}
