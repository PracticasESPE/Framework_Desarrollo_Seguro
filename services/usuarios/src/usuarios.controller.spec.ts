import { Test } from '@nestjs/testing';
import { UsuariosController } from './usuarios.controller';
import { UsuariosService } from './usuarios.service';

const servicioMock = {
  crear: jest.fn(),
  listar: jest.fn(),
  obtener: jest.fn(),
};

const usuario = {
  id: '3f2b8c1e-9d4a-4c7e-8a55-1b2c3d4e5f60',
  nombre: 'Ana Pérez',
  correo: 'ana@example.com',
  creadoEn: '2026-10-07T12:00:00.000Z',
};

describe('UsuariosController', () => {
  let controlador: UsuariosController;

  beforeEach(async () => {
    jest.resetAllMocks();
    const modulo = await Test.createTestingModule({
      controllers: [UsuariosController],
      providers: [{ provide: UsuariosService, useValue: servicioMock }],
    }).compile();
    controlador = modulo.get(UsuariosController);
  });

  it('crear delega en el servicio y devuelve su resultado', async () => {
    servicioMock.crear.mockResolvedValue(usuario);
    const dto = { nombre: 'Ana Pérez', correo: 'ana@example.com' };

    await expect(controlador.crear(dto)).resolves.toEqual(usuario);
    expect(servicioMock.crear).toHaveBeenCalledWith(dto);
  });

  it('listar devuelve los usuarios del servicio', async () => {
    servicioMock.listar.mockResolvedValue([usuario]);

    await expect(controlador.listar()).resolves.toEqual([usuario]);
  });

  it('obtener pasa el id al servicio', async () => {
    servicioMock.obtener.mockResolvedValue(usuario);

    await expect(controlador.obtener(usuario.id)).resolves.toEqual(usuario);
    expect(servicioMock.obtener).toHaveBeenCalledWith(usuario.id);
  });
});
