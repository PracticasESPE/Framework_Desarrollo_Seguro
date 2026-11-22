/* eslint-disable @typescript-eslint/no-unused-vars */
// Pruebas de las reglas de negocio de Stock, generadas por el LLM (fase 3) y verificadas con
// Jest. El motor escribe este encabezado; el LLM, el cuerpo de cada caso. Se regeneran con
// «framework servicio pruebas»: no editar a mano.
import {
  BadRequestException,
  ConflictException,
  NotFoundException,
} from '@nestjs/common';
import { Test } from '@nestjs/testing';
import type { ActualizarStockDto } from './dto/actualizar-stock.dto';
import type { CrearStockDto } from './dto/crear-stock.dto';
import type { Stock } from './generated/prisma/client';
import { PrismaService } from './prisma.service';
import { StockService } from './stock.service';

// Prisma devuelve los decimales como objetos Decimal; las reglas usan toNumber().
const decimal = (valor: number) => ({ toNumber: () => valor, valueOf: () => valor });

const prisma = {
  $transaction: jest.fn(),
  carrito: { findUnique: jest.fn(), findFirst: jest.fn(), findMany: jest.fn(), count: jest.fn(), aggregate: jest.fn(), create: jest.fn(), update: jest.fn(), updateMany: jest.fn(), upsert: jest.fn(), delete: jest.fn(), deleteMany: jest.fn() },
  carritoItem: { findUnique: jest.fn(), findFirst: jest.fn(), findMany: jest.fn(), count: jest.fn(), aggregate: jest.fn(), create: jest.fn(), update: jest.fn(), updateMany: jest.fn(), upsert: jest.fn(), delete: jest.fn(), deleteMany: jest.fn() },
  producto: { findUnique: jest.fn(), findFirst: jest.fn(), findMany: jest.fn(), count: jest.fn(), aggregate: jest.fn(), create: jest.fn(), update: jest.fn(), updateMany: jest.fn(), upsert: jest.fn(), delete: jest.fn(), deleteMany: jest.fn() },
  stock: { findUnique: jest.fn(), findFirst: jest.fn(), findMany: jest.fn(), count: jest.fn(), aggregate: jest.fn(), create: jest.fn(), update: jest.fn(), updateMany: jest.fn(), upsert: jest.fn(), delete: jest.fn(), deleteMany: jest.fn() },
  direccion: { findUnique: jest.fn(), findFirst: jest.fn(), findMany: jest.fn(), count: jest.fn(), aggregate: jest.fn(), create: jest.fn(), update: jest.fn(), updateMany: jest.fn(), upsert: jest.fn(), delete: jest.fn(), deleteMany: jest.fn() },
  estadoPedido: { findUnique: jest.fn(), findFirst: jest.fn(), findMany: jest.fn(), count: jest.fn(), aggregate: jest.fn(), create: jest.fn(), update: jest.fn(), updateMany: jest.fn(), upsert: jest.fn(), delete: jest.fn(), deleteMany: jest.fn() },
  pedido: { findUnique: jest.fn(), findFirst: jest.fn(), findMany: jest.fn(), count: jest.fn(), aggregate: jest.fn(), create: jest.fn(), update: jest.fn(), updateMany: jest.fn(), upsert: jest.fn(), delete: jest.fn(), deleteMany: jest.fn() },
};

type Reglas = {
  reglasAlCrear(datos: CrearStockDto): Promise<void>;
  reglasAlActualizar(actual: Stock, cambios: ActualizarStockDto): Promise<void>;
  reglasAlEliminar(actual: Stock): Promise<void>;
};

describe('Reglas de negocio de Stock (generadas)', () => {
  let reglas: Reglas;

  beforeEach(async () => {
    jest.resetAllMocks();
    const modulo = await Test.createTestingModule({
      providers: [StockService, { provide: PrismaService, useValue: prisma }],
    }).compile();
    reglas = modulo.get(StockService) as unknown as Reglas;
  });

  it('01. rechaza la creación si el producto no existe', async () => {
    prisma.producto.findUnique.mockResolvedValue(null);
    prisma.stock.findUnique.mockResolvedValue(null);
    const datos = { productoId: 'prod-1', cantidad: 10 } as CrearStockDto;
    await expect(reglas.reglasAlCrear(datos)).rejects.toBeInstanceOf(NotFoundException);
    expect(prisma.producto.findUnique).toHaveBeenCalledWith({ where: { id: datos.productoId } });
  });

  it('02. rechaza la creación si ya existe stock para el producto', async () => {
    prisma.producto.findUnique.mockResolvedValue({ id: 'prod-1' } as any);
    prisma.stock.findUnique.mockResolvedValue({ productoId: 'prod-1' } as any);
    const datos = { productoId: 'prod-1', cantidad: 5 } as CrearStockDto;
    await expect(reglas.reglasAlCrear(datos)).rejects.toBeInstanceOf(ConflictException);
    expect(prisma.stock.findUnique).toHaveBeenCalledWith({ where: { productoId: datos.productoId } });
  });

  it('03. permite crear stock cuando el producto existe y no hay registro previo', async () => {
    prisma.producto.findUnique.mockResolvedValue({ id: 'prod-1' } as any);
    prisma.stock.findUnique.mockResolvedValue(null);
    const datos = { productoId: 'prod-1', cantidad: 7 } as CrearStockDto;
    await expect(reglas.reglasAlCrear(datos)).resolves.toBeUndefined();
  });

  it('04. rechaza la actualización si se cambia a un producto inexistente', async () => {
    prisma.producto.findUnique.mockResolvedValue(null);
    prisma.stock.findUnique.mockResolvedValue(null);
    const actual = { productoId: 'prod-old', cantidad: 5 } as Stock;
    const cambios = { productoId: 'prod-new' } as ActualizarStockDto;
    await expect(reglas.reglasAlActualizar(actual, cambios)).rejects.toBeInstanceOf(NotFoundException);
    expect(prisma.producto.findUnique).toHaveBeenCalledWith({ where: { id: 'prod-new' } });
  });

  it('05. rechaza la actualización si el nuevo producto ya tiene stock registrado', async () => {
    prisma.producto.findUnique.mockResolvedValue({ id: 'prod-new' } as any);
    prisma.stock.findUnique.mockResolvedValue({ productoId: 'prod-new' } as any);
    const actual = { productoId: 'prod-old', cantidad: 5 } as Stock;
    const cambios = { productoId: 'prod-new' } as ActualizarStockDto;
    await expect(reglas.reglasAlActualizar(actual, cambios)).rejects.toBeInstanceOf(ConflictException);
    expect(prisma.stock.findUnique).toHaveBeenCalledWith({ where: { productoId: 'prod-new' } });
  });

  it('06. permite actualizar a un nuevo producto cuando no existe stock previo', async () => {
    prisma.producto.findUnique.mockResolvedValue({ id: 'prod-new' } as any);
    prisma.stock.findUnique.mockResolvedValue(null);
    const actual = { productoId: 'prod-old', cantidad: 5 } as Stock;
    const cambios = { productoId: 'prod-new' } as ActualizarStockDto;
    await expect(reglas.reglasAlActualizar(actual, cambios)).resolves.toBeUndefined();
  });

  it('07. rechaza la actualización si la nueva cantidad es negativa', async () => {
    const actual = { productoId: 'prod-1', cantidad: 5 } as Stock;
    const cambios = { cantidad: -3 } as ActualizarStockDto;
    await expect(reglas.reglasAlActualizar(actual, cambios)).rejects.toBeInstanceOf(BadRequestException);
  });

  it('08. permite actualizar la cantidad cuando es cero o positiva', async () => {
    const actual = { productoId: 'prod-1', cantidad: 5 } as Stock;
    const cambios = { cantidad: 3 } as ActualizarStockDto;
    await expect(reglas.reglasAlActualizar(actual, cambios)).resolves.toBeUndefined();
  });

  it('09. rechaza la eliminación si el stock tiene unidades disponibles', async () => {
    const actual = { productoId: 'prod-1', cantidad: 2 } as Stock;
    await expect(reglas.reglasAlEliminar(actual)).rejects.toBeInstanceOf(ConflictException);
  });

  it('10. permite eliminar el registro de stock cuando la cantidad es cero', async () => {
    const actual = { productoId: 'prod-1', cantidad: 0 } as Stock;
    await expect(reglas.reglasAlEliminar(actual)).resolves.toBeUndefined();
  });
});
