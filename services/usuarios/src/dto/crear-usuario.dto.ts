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
  @ApiProperty({ example: 'Ana Pérez', minLength: 2, maxLength: 100 })
  @Transform(limpiar)
  @IsString()
  @IsNotEmpty()
  @MinLength(2)
  @MaxLength(100)
  nombre!: string;

  @ApiProperty({ example: 'ana.perez@example.com', maxLength: 254 })
  @Transform(({ value }: { value: unknown }) =>
    typeof value === 'string' ? value.trim().toLowerCase() : value,
  )
  @IsEmail()
  @MaxLength(254)
  correo!: string;

  @ApiPropertyOptional({
    example: '+593991234567',
    description: 'Teléfono de 7 a 15 dígitos, con + opcional al inicio',
  })
  @IsOptional()
  @Matches(/^\+?[0-9]{7,15}$/, {
    message:
      'telefono debe tener entre 7 y 15 dígitos, con + opcional al inicio',
  })
  telefono?: string;
}
