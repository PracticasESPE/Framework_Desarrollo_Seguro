import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Transform } from 'class-transformer';
import {
  IsEmail,
  IsNotEmpty,
  IsOptional,
  IsString,
  Matches,
  MaxLength,
  MinLength,
} from 'class-validator';

const limpiar = ({ value }: { value: unknown }): unknown =>
  typeof value === 'string' ? value.trim() : value;

export class CrearUsuarioDto {
  @ApiProperty({
    example: 'Ana Pérez',
    minLength: 2,
    maxLength: 100,
    // Mismo conjunto que /\P{Cc}/u, sin propiedades Unicode: el contrato lo leen otros motores.
    pattern: '^[^\\u0000-\\u001F\\u007F-\\u009F]+$',
  })
  @Transform(limpiar)
  @IsString()
  @IsNotEmpty()
  @MinLength(2)
  @MaxLength(100)
  // Sin caracteres de control: PostgreSQL rechaza el byte 0x00 y daría un error 500 (hallazgo de ZAP).
  @Matches(/^\P{Cc}+$/u, {
    message: 'nombre no puede contener caracteres de control',
  })
  nombre!: string;

  @ApiProperty({
    example: 'ana.perez@example.com',
    format: 'email',
    maxLength: 254,
  })
  @Transform(({ value }: { value: unknown }) =>
    typeof value === 'string' ? value.trim().toLowerCase() : value,
  )
  @IsEmail()
  @MaxLength(254)
  correo!: string;

  @ApiPropertyOptional({
    example: '+593991234567',
    description: 'Teléfono de 7 a 15 dígitos, con + opcional al inicio',
    pattern: '^\\+?[0-9]{7,15}$',
    maxLength: 16,
  })
  @IsOptional()
  @Matches(/^\+?[0-9]{7,15}$/, {
    message:
      'telefono debe tener entre 7 y 15 dígitos, con + opcional al inicio',
  })
  telefono?: string;
}
