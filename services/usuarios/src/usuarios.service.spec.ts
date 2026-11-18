import { ConflictException, NotFoundException } from '@nestjs/common';
import { Test } from '@nestjs/testing';
import { PrismaService } from './prisma.service';
import { UsuariosService } from './usuarios.service';

const prismaMock = {
  usuario: {
    create: jest.fn(),
    findMany: jest.fn(),
    findUnique: jest.fn(),
  },
};

const fila = {
  id: '3f2b8c1e-9d4a-4c7e-8a55-1b2c3d4e5f60',
  nombre: 'Ana Pérez',
  correo: 'ana@example.com',
  telefono: null,
  creadoEn: new Date('2026-10-07T12:00:00.000Z'),
};

describe('UsuariosService', () => {
  let servicio: UsuariosService;

  beforeEach(async () => {
    jest.resetAllMocks();
    const modulo = await Test.createTestingModule({
      providers: [
        UsuariosService,
        { provide: PrismaService, useValue: prismaMock },
      ],
    }).compile();
    servicio = modulo.get(UsuariosService);
  });

  it('crea un usuario y devuelve la fecha en formato ISO', async () => {
    prismaMock.usuario.create.mockResolvedValue(fila);

    const resultado = await servicio.crear({
      nombre: 'Ana Pérez',
      correo: 'ana@example.com',
    });

    expect(resultado).toEqual({
      id: fila.id,
      nombre: 'Ana Pérez',
      correo: 'ana@example.com',
      creadoEn: '2026-10-07T12:00:00.000Z',
    });
    expect(prismaMock.usuario.create).toHaveBeenCalledTimes(1);
  });

  it('lanza ConflictException si el correo ya existe', async () => {
    prismaMock.usuario.create.mockRejectedValue({ code: 'P2002' });

    await expect(
      servicio.crear({ nombre: 'Ana Pérez', correo: 'ana@example.com' }),
    ).rejects.toBeInstanceOf(ConflictException);
  });

  it('propaga los errores inesperados sin convertirlos', async () => {
    const error = new Error('fallo de conexión');
    prismaMock.usuario.create.mockRejectedValue(error);

    await expect(
      servicio.crear({ nombre: 'Ana Pérez', correo: 'ana@example.com' }),
    ).rejects.toBe(error);
  });

  it('lista los usuarios con un máximo de 100', async () => {
    prismaMock.usuario.findMany.mockResolvedValue([fila]);

    const resultado = await servicio.listar();

    expect(resultado).toHaveLength(1);
    expect(prismaMock.usuario.findMany).toHaveBeenCalledWith(
      expect.objectContaining({ take: 100 }),
    );
  });

  it('obtiene un usuario por id', async () => {
    prismaMock.usuario.findUnique.mockResolvedValue(fila);

    const resultado = await servicio.obtener(fila.id);

    expect(resultado.id).toBe(fila.id);
  });

  it('lanza NotFoundException si el usuario no existe', async () => {
    prismaMock.usuario.findUnique.mockResolvedValue(null);

    await expect(servicio.obtener(fila.id)).rejects.toBeInstanceOf(
      NotFoundException,
    );
  });
});
