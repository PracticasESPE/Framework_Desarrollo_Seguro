import { plainToInstance } from 'class-transformer';
import { validate } from 'class-validator';
import { CrearUsuarioDto } from './crear-usuario.dto';

async function erroresDe(datos: object): Promise<string[]> {
  const errores = await validate(plainToInstance(CrearUsuarioDto, datos));
  return errores.map((e) => e.property);
}

describe('CrearUsuarioDto', () => {
  it('acepta datos válidos', async () => {
    expect(
      await erroresDe({ nombre: 'Ana Pérez', correo: 'ana@example.com' }),
    ).toEqual([]);
  });

  it('acepta un teléfono opcional válido', async () => {
    expect(
      await erroresDe({
        nombre: 'Ana Pérez',
        correo: 'ana@example.com',
        telefono: '+593991234567',
      }),
    ).toEqual([]);
  });

  it('rechaza un correo con formato inválido', async () => {
    expect(
      await erroresDe({ nombre: 'Ana Pérez', correo: 'no-es-correo' }),
    ).toContain('correo');
  });

  it('rechaza un nombre demasiado corto', async () => {
    expect(
      await erroresDe({ nombre: 'A', correo: 'ana@example.com' }),
    ).toContain('nombre');
  });

  it('rechaza un nombre de más de 100 caracteres', async () => {
    expect(
      await erroresDe({ nombre: 'a'.repeat(101), correo: 'ana@example.com' }),
    ).toContain('nombre');
  });

  it('rechaza un teléfono con letras', async () => {
    expect(
      await erroresDe({
        nombre: 'Ana Pérez',
        correo: 'ana@example.com',
        telefono: 'abc1234567',
      }),
    ).toContain('telefono');
  });

  it('normaliza espacios y mayúsculas', () => {
    const dto = plainToInstance(CrearUsuarioDto, {
      nombre: '  Ana Pérez  ',
      correo: '  ANA@Example.com ',
    });
    expect(dto.nombre).toBe('Ana Pérez');
    expect(dto.correo).toBe('ana@example.com');
  });
});
