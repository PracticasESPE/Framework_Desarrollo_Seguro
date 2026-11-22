/* eslint-disable @typescript-eslint/no-unused-vars */
// Pruebas de las reglas de negocio de CarritoItem, generadas por el LLM (fase 3) y verificadas con
// Jest. El motor escribe este encabezado; el LLM, el cuerpo de cada caso. Se regeneran con
// «framework servicio pruebas»: no editar a mano.
import {
  BadRequestException,
  ConflictException,
  NotFoundException,
} from '@nestjs/common';
import { Test } from '@nestjs/testing';
import type { ActualizarCarritoItemDto } from './dto/actualizar-carrito-item.dto';
import type { CrearCarritoItemDto } from './dto/crear-carrito-item.dto';
import type { CarritoItem } from './generated/prisma/client';
import { PrismaService } from './prisma.service';
import { CarritoItemService } from './carrito-item.service';

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
  reglasAlCrear(datos: CrearCarritoItemDto): Promise<void>;
  reglasAlActualizar(actual: CarritoItem, cambios: ActualizarCarritoItemDto): Promise<void>;
  reglasAlEliminar(actual: CarritoItem): Promise<void>;
};

describe('Reglas de negocio de CarritoItem (generadas)', () => {
  let reglas: Reglas;

  beforeEach(async () => {
    jest.resetAllMocks();
    const modulo = await Test.createTestingModule({
      providers: [CarritoItemService, { provide: PrismaService, useValue: prisma }],
    }).compile();
    reglas = modulo.get(CarritoItemService) as unknown as Reglas;
  });

  it('01. crea un ítem de carrito cuando existen carrito, producto, stock suficiente y no hay duplicado (RF-10)', async () => {
    prisma.carrito.findUnique.mockResolvedValue({ id: 'c1' } as any);
    prisma.producto.findUnique.mockResolvedValue({ id: 'p1' } as any);
    prisma.stock.findUnique.mockResolvedValue({ cantidad: 10 } as any);
    prisma.carritoItem.findFirst.mockResolvedValue(null);
    await expect(reglas.reglasAlCrear({
      carritoId: 'c1',
      productoId: 'p1',
      cantidad: 3,
    } as CrearCarritoItemDto)).resolves.toBeUndefined();
  });

  it('02. rechaza la creación cuando el carrito especificado no existe (RF-10)', async () => {
    prisma.carrito.findUnique.mockResolvedValue(null);
    await expect(reglas.reglasAlCrear({
      carritoId: 'cX',
      productoId: 'p1',
      cantidad: 1,
    } as CrearCarritoItemDto)).rejects.toBeInstanceOf(BadRequestException);
  });

  it('03. rechaza la creación cuando el producto especificado no existe (RF-10)', async () => {
    prisma.carrito.findUnique.mockResolvedValue({ id: 'c1' } as any);
    prisma.producto.findUnique.mockResolvedValue(null);
    await expect(reglas.reglasAlCrear({
      carritoId: 'c1',
      productoId: 'pX',
      cantidad: 1,
    } as CrearCarritoItemDto)).rejects.toBeInstanceOf(BadRequestException);
  });

  it('04. rechaza la creación cuando no hay stock suficiente para la cantidad solicitada (RF-12)', async () => {
    prisma.carrito.findUnique.mockResolvedValue({ id: 'c1' } as any);
    prisma.producto.findUnique.mockResolvedValue({ id: 'p1' } as any);
    prisma.stock.findUnique.mockResolvedValue({ cantidad: 2 } as any);
    prisma.carritoItem.findFirst.mockResolvedValue(null);
    await expect(reglas.reglasAlCrear({
      carritoId: 'c1',
      productoId: 'p1',
      cantidad: 5,
    } as CrearCarritoItemDto)).rejects.toBeInstanceOf(ConflictException);
  });

  it('05. rechaza la creación cuando el producto ya está agregado al carrito (duplicado) (RF-10)', async () => {
    prisma.carrito.findUnique.mockResolvedValue({ id: 'c1' } as any);
    prisma.producto.findUnique.mockResolvedValue({ id: 'p1' } as any);
    prisma.stock.findUnique.mockResolvedValue({ cantidad: 10 } as any);
    prisma.carritoItem.findFirst.mockResolvedValue({ id: 'ci1' } as any);
    await expect(reglas.reglasAlCrear({
      carritoId: 'c1',
      productoId: 'p1',
      cantidad: 1,
    } as CrearCarritoItemDto)).rejects.toBeInstanceOf(ConflictException);
  });

  it('06. actualiza la cantidad de un ítem cuando hay stock suficiente y no existen conflictos (RF-10)', async () => {
    const actual = { id: 'ci1', carritoId: 'c1', productoId: 'p1', cantidad: 2 } as CarritoItem;
    prisma.carritoItem.findFirst.mockResolvedValue(null);
    prisma.stock.findUnique.mockResolvedValue({ cantidad: 5 } as any);
    await expect(reglas.reglasAlActualizar(actual, { cantidad: 3 } as ActualizarCarritoItemDto)).resolves.toBeUndefined();
  });

  it('07. rechaza la actualización cuando el nuevo carritoId no existe (RF-10)', async () => {
    const actual = { id: 'ci1', carritoId: 'c1', productoId: 'p1', cantidad: 1 } as CarritoItem;
    prisma.carrito.findUnique.mockResolvedValue(null);
    await expect(reglas.reglasAlActualizar(actual, { carritoId: 'cX' } as ActualizarCarritoItemDto)).rejects.toBeInstanceOf(BadRequestException);
  });

  it('08. rechaza la actualización cuando el nuevo productoId no existe (RF-10)', async () => {
    const actual = { id: 'ci1', carritoId: 'c1', productoId: 'p1', cantidad: 1 } as CarritoItem;
    prisma.carrito.findUnique.mockResolvedValue({ id: 'c1' } as any);
    prisma.producto.findUnique.mockResolvedValue(null);
    await expect(reglas.reglasAlActualizar(actual, { productoId: 'pX' } as ActualizarCarritoItemDto)).rejects.toBeInstanceOf(BadRequestException);
  });

  it('09. rechaza la actualización cuando otro ítem con mismo carrito y producto ya existe (RF-10)', async () => {
    const actual = { id: 'ci1', carritoId: 'c1', productoId: 'p1', cantidad: 1 } as CarritoItem;
    prisma.carrito.findUnique.mockResolvedValue({ id: 'c1' } as any);
    prisma.producto.findUnique.mockResolvedValue({ id: 'p2' } as any);
    prisma.carritoItem.findFirst.mockResolvedValue({ id: 'ci2' } as any);
    await expect(reglas.reglasAlActualizar(actual, { productoId: 'p2' } as ActualizarCarritoItemDto)).rejects.toBeInstanceOf(ConflictException);
  });

  it('10. rechaza la actualización de cantidad cuando no hay stock suficiente (RF-12)', async () => {
    const actual = { id: 'ci1', carritoId: 'c1', productoId: 'p1', cantidad: 2 } as CarritoItem;
    prisma.carritoItem.findFirst.mockResolvedValue(null);
    prisma.stock.findUnique.mockResolvedValue({ cantidad: 0 } as any);
    await expect(reglas.reglasAlActualizar(actual, { cantidad: 5 } as ActualizarCarritoItemDto)).rejects.toBeInstanceOf(ConflictException);
  });
});
