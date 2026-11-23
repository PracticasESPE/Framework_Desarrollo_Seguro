import {
  BadRequestException,
  ConflictException,
  NotFoundException,
} from '@nestjs/common';
import { Test } from '@nestjs/testing';
import type { CrearLineaPedidoDto } from './dto/crear-linea-pedido.dto';
import { PrismaService } from './prisma.service';
import { LineaPedidoService } from './linea-pedido.service';

// Pruebas unitarias de LineaPedidoService, generadas por la plantilla. Prisma se sustituye
// por un doble, así que no necesitan base de datos. Las reglas de negocio (el bloque que completa
// el LLM) se sustituyen en cada prueba: aquí se comprueba lo que genera la plantilla, el orden de
// las operaciones y la traducción de los errores de Prisma.

type Reglas = Record<
  'reglasAlCrear' | 'reglasAlActualizar' | 'reglasAlEliminar',
  (...argumentos: unknown[]) => Promise<void>
>;

// Prisma devuelve los decimales como objetos Decimal; el servicio solo usa toNumber().
const decimal = (valor: number) => ({ toNumber: () => valor });

const ID = '7d9f3c2a-1b4e-4f6a-8c5d-2e3f4a5b6c7d';

const entrada: CrearLineaPedidoDto = {
  pedidoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
  carritoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
  productoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
  cantidad: 1,
  precioUnitario: 0.0,
  subtotal: 0.0,
};

const fila = {
  id: ID,
  pedidoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
  carritoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
  productoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
  cantidad: 1,
  precioUnitario: decimal(0.0),
  subtotal: decimal(0.0),
  creadoEn: new Date('2026-01-15T12:00:00.000Z'),
  actualizadoEn: new Date('2026-01-16T12:00:00.000Z'),
};

const respuesta = {
  id: ID,
  pedidoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
  carritoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
  productoId: '0b7e4c1a-5d2f-4a8b-9c3d-1e2f3a4b5c6d',
  cantidad: 1,
  precioUnitario: 0.0,
  subtotal: 0.0,
  creadoEn: '2026-01-15T12:00:00.000Z',
  actualizadoEn: '2026-01-16T12:00:00.000Z',
};

const prisma = {
  $transaction: jest.fn(),
  lineaPedido: {
    count: jest.fn(),
    findMany: jest.fn(),
    findUnique: jest.fn(),
    create: jest.fn(),
    update: jest.fn(),
    delete: jest.fn(),
  },
};
const tabla = prisma.lineaPedido;

describe('LineaPedidoService', () => {
  let servicio: LineaPedidoService;
  let reglas: Reglas;

  beforeEach(async () => {
    jest.resetAllMocks();
    const modulo = await Test.createTestingModule({
      providers: [LineaPedidoService, { provide: PrismaService, useValue: prisma }],
    }).compile();
    servicio = modulo.get(LineaPedidoService);
    reglas = servicio as unknown as Reglas;
    jest.spyOn(reglas, 'reglasAlCrear').mockResolvedValue(undefined);
    jest.spyOn(reglas, 'reglasAlActualizar').mockResolvedValue(undefined);
    jest.spyOn(reglas, 'reglasAlEliminar').mockResolvedValue(undefined);
  });

  describe('crear', () => {
    it('aplica las reglas de negocio antes de escribir en la base', async () => {
      tabla.create.mockResolvedValue(fila);

      await expect(servicio.crear(entrada)).resolves.toEqual(respuesta);

      expect(reglas.reglasAlCrear).toHaveBeenCalledWith(entrada);
      expect(jest.mocked(reglas.reglasAlCrear).mock.invocationCallOrder[0]).toBeLessThan(
        tabla.create.mock.invocationCallOrder[0],
      );
    });

    it('no escribe en la base si una regla rechaza la operación', async () => {
      jest.mocked(reglas.reglasAlCrear).mockRejectedValue(new BadRequestException('regla'));

      await expect(servicio.crear(entrada)).rejects.toBeInstanceOf(BadRequestException);
      expect(tabla.create).not.toHaveBeenCalled();
    });

    it('responde 409 si un valor único ya existe (P2002)', async () => {
      tabla.create.mockRejectedValue({ code: 'P2002' });

      await expect(servicio.crear(entrada)).rejects.toBeInstanceOf(ConflictException);
    });

    it('responde 400 si una referencia no existe (P2003)', async () => {
      tabla.create.mockRejectedValue({ code: 'P2003' });

      await expect(servicio.crear(entrada)).rejects.toBeInstanceOf(BadRequestException);
    });

    it('no oculta un error desconocido: lo resuelve el filtro de errores como 500', async () => {
      const caida = new Error('conexión perdida');
      tabla.create.mockRejectedValue(caida);

      await expect(servicio.crear(entrada)).rejects.toBe(caida);
    });
  });

  describe('listar', () => {
    it('pagina con un orden estable', async () => {
      prisma.$transaction.mockImplementation((consultas: Promise<unknown>[]) =>
        Promise.all(consultas),
      );
      tabla.count.mockResolvedValue(41);
      tabla.findMany.mockResolvedValue([fila]);

      await expect(servicio.listar({ pagina: 3, tamano: 20 })).resolves.toEqual({
        elementos: [respuesta],
        total: 41,
        pagina: 3,
        tamano: 20,
      });
      expect(tabla.findMany).toHaveBeenCalledWith({
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: 40,
        take: 20,
      });
    });
  });

  describe('obtener', () => {
    it('devuelve el registro', async () => {
      tabla.findUnique.mockResolvedValue(fila);

      await expect(servicio.obtener(ID)).resolves.toEqual(respuesta);
      expect(tabla.findUnique).toHaveBeenCalledWith({ where: { id: ID } });
    });

    it('responde 404 si no existe', async () => {
      tabla.findUnique.mockResolvedValue(null);

      await expect(servicio.obtener(ID)).rejects.toBeInstanceOf(NotFoundException);
    });
  });

  describe('actualizar', () => {
    it('aplica las reglas con el registro actual antes de escribir', async () => {
      tabla.findUnique.mockResolvedValue(fila);
      tabla.update.mockResolvedValue(fila);

      await expect(servicio.actualizar(ID, entrada)).resolves.toEqual(respuesta);

      expect(reglas.reglasAlActualizar).toHaveBeenCalledWith(fila, entrada);
      expect(tabla.update).toHaveBeenCalledWith(
        expect.objectContaining({ where: { id: ID } }),
      );
    });

    it('responde 404 si el registro no existe, sin aplicar las reglas', async () => {
      tabla.findUnique.mockResolvedValue(null);

      await expect(servicio.actualizar(ID, entrada)).rejects.toBeInstanceOf(NotFoundException);
      expect(reglas.reglasAlActualizar).not.toHaveBeenCalled();
      expect(tabla.update).not.toHaveBeenCalled();
    });

    it('responde 404 si el registro desaparece al guardar (P2025)', async () => {
      tabla.findUnique.mockResolvedValue(fila);
      tabla.update.mockRejectedValue({ code: 'P2025' });

      await expect(servicio.actualizar(ID, entrada)).rejects.toBeInstanceOf(NotFoundException);
    });
  });

  describe('eliminar', () => {
    it('aplica las reglas con el registro actual antes de borrar', async () => {
      tabla.findUnique.mockResolvedValue(fila);
      tabla.delete.mockResolvedValue(fila);

      await expect(servicio.eliminar(ID)).resolves.toBeUndefined();

      expect(reglas.reglasAlEliminar).toHaveBeenCalledWith(fila);
      expect(tabla.delete).toHaveBeenCalledWith({ where: { id: ID } });
    });

    it('no borra si una regla lo impide', async () => {
      tabla.findUnique.mockResolvedValue(fila);
      jest.mocked(reglas.reglasAlEliminar).mockRejectedValue(new ConflictException('regla'));

      await expect(servicio.eliminar(ID)).rejects.toBeInstanceOf(ConflictException);
      expect(tabla.delete).not.toHaveBeenCalled();
    });

    it('responde 409 si otros registros dependen de este (P2003)', async () => {
      tabla.findUnique.mockResolvedValue(fila);
      tabla.delete.mockRejectedValue({ code: 'P2003' });

      await expect(servicio.eliminar(ID)).rejects.toBeInstanceOf(ConflictException);
    });
  });
});
