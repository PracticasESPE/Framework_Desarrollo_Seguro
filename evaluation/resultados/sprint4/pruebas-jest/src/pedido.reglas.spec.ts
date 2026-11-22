/* eslint-disable @typescript-eslint/no-unused-vars */
// Pruebas de las reglas de negocio de Pedido, generadas por el LLM (fase 3) y verificadas con
// Jest. El motor escribe este encabezado; el LLM, el cuerpo de cada caso. Se regeneran con
// «framework servicio pruebas»: no editar a mano.
import {
  BadRequestException,
  ConflictException,
  NotFoundException,
} from '@nestjs/common';
import { Test } from '@nestjs/testing';
import type { ActualizarPedidoDto } from './dto/actualizar-pedido.dto';
import type { CrearPedidoDto } from './dto/crear-pedido.dto';
import type { Pedido } from './generated/prisma/client';
import { PrismaService } from './prisma.service';
import { PedidoService } from './pedido.service';

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
  reglasAlCrear(datos: CrearPedidoDto): Promise<void>;
  reglasAlActualizar(actual: Pedido, cambios: ActualizarPedidoDto): Promise<void>;
  reglasAlEliminar(actual: Pedido): Promise<void>;
};

describe('Reglas de negocio de Pedido (generadas)', () => {
  let reglas: Reglas;

  beforeEach(async () => {
    jest.resetAllMocks();
    const modulo = await Test.createTestingModule({
      providers: [PedidoService, { provide: PrismaService, useValue: prisma }],
    }).compile();
    reglas = modulo.get(PedidoService) as unknown as Reglas;
  });

  it('01. Acepta un pedido cuando el carrito tiene ítems, hay stock suficiente y el total coincide (RF-11)', async () => {
    prisma.carrito.findFirst.mockResolvedValue({ id: 'c1', clienteId: 'cli1' } as any);
    prisma.carritoItem.findMany.mockResolvedValue([
      {
        productoId: 'p1',
        cantidad: 2,
        producto: { precio: decimal(10), nombre: 'Prod1' },
      },
    ] as any);
    prisma.stock.findUnique.mockResolvedValue({ productoId: 'p1', cantidad: 5 } as any);
    prisma.stock.update.mockResolvedValue(undefined as any);
    await expect(
      reglas.reglasAlCrear({
        clienteId: 'cli1',
        direccionId: 'dir1',
        total: 20,
        estadoId: 'est1',
        fechaExpiracion: undefined,
        tokenPagoId: null,
        cancelado: false,
      } as CrearPedidoDto),
    ).resolves.toBeUndefined();
    expect(prisma.stock.update).toHaveBeenCalledWith({
      where: { productoId: 'p1' },
      data: { cantidad: 3 },
    });
  });

  it('02. Rechaza la creación si el carrito no existe', async () => {
    prisma.carrito.findFirst.mockResolvedValue(null);
    await expect(
      reglas.reglasAlCrear({
        clienteId: 'cli1',
        direccionId: 'dir1',
        total: 0,
        estadoId: 'est1',
        fechaExpiracion: undefined,
        tokenPagoId: null,
        cancelado: false,
      } as CrearPedidoDto),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it('03. Rechaza la creación si el carrito está vacío', async () => {
    prisma.carrito.findFirst.mockResolvedValue({ id: 'c1', clienteId: 'cli1' } as any);
    prisma.carritoItem.findMany.mockResolvedValue([] as any);
    await expect(
      reglas.reglasAlCrear({
        clienteId: 'cli1',
        direccionId: 'dir1',
        total: 0,
        estadoId: 'est1',
        fechaExpiracion: undefined,
        tokenPagoId: null,
        cancelado: false,
      } as CrearPedidoDto),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it('04. Rechaza la creación cuando no hay stock suficiente para un producto (RF-12)', async () => {
    prisma.carrito.findFirst.mockResolvedValue({ id: 'c1', clienteId: 'cli1' } as any);
    prisma.carritoItem.findMany.mockResolvedValue([
      {
        productoId: 'p1',
        cantidad: 3,
        producto: { precio: decimal(5), nombre: 'Prod1' },
      },
    ] as any);
    prisma.stock.findUnique.mockResolvedValue({ productoId: 'p1', cantidad: 2 } as any);
    await expect(
      reglas.reglasAlCrear({
        clienteId: 'cli1',
        direccionId: 'dir1',
        total: 15,
        estadoId: 'est1',
        fechaExpiracion: undefined,
        tokenPagoId: null,
        cancelado: false,
      } as CrearPedidoDto),
    ).rejects.toBeInstanceOf(ConflictException);
  });

  it('05. Rechaza la creación si el total enviado no coincide con el cálculo del servidor (RF-11)', async () => {
    prisma.carrito.findFirst.mockResolvedValue({ id: 'c1', clienteId: 'cli1' } as any);
    prisma.carritoItem.findMany.mockResolvedValue([
      {
        productoId: 'p1',
        cantidad: 1,
        producto: { precio: decimal(10), nombre: 'Prod1' },
      },
    ] as any);
    prisma.stock.findUnique.mockResolvedValue({ productoId: 'p1', cantidad: 10 } as any);
    prisma.stock.update.mockResolvedValue(undefined as any);
    await expect(
      reglas.reglasAlCrear({
        clienteId: 'cli1',
        direccionId: 'dir1',
        total: 5, // total incorrecto
        estadoId: 'est1',
        fechaExpiracion: undefined,
        tokenPagoId: null,
        cancelado: false,
      } as CrearPedidoDto),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it('06. Rechaza la cancelación si el estado del pedido no se encuentra (RF-20)', async () => {
    prisma.estadoPedido.findUnique.mockResolvedValue(null);
    await expect(
      reglas.reglasAlActualizar(
        {
          id: 'ped1',
          clienteId: 'cli1',
          direccionId: 'dir1',
          total: decimal(20),
          estadoId: 'est1',
          fechaExpiracion: new Date(),
          tokenPagoId: null,
          cancelado: false,
        } as unknown as Pedido,
        { cancelado: true } as ActualizarPedidoDto,
      ),
    ).rejects.toBeInstanceOf(NotFoundException);
  });

  it('07. Rechaza la cancelación si el pedido ya está enviado o entregado (RF-20)', async () => {
    prisma.estadoPedido.findUnique.mockResolvedValue({ id: 'est1', nombre: 'Enviado' } as any);
    await expect(
      reglas.reglasAlActualizar(
        {
          id: 'ped1',
          clienteId: 'cli1',
          direccionId: 'dir1',
          total: decimal(20),
          estadoId: 'est1',
          fechaExpiracion: new Date(),
          tokenPagoId: null,
          cancelado: false,
        } as unknown as Pedido,
        { cancelado: true } as ActualizarPedidoDto,
      ),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it('08. Permite cancelar un pedido que está en estado pendiente (RF-20)', async () => {
    prisma.estadoPedido.findUnique.mockResolvedValue({ id: 'est1', nombre: 'Pendiente' } as any);
    await expect(
      reglas.reglasAlActualizar(
        {
          id: 'ped1',
          clienteId: 'cli1',
          direccionId: 'dir1',
          total: decimal(20),
          estadoId: 'est1',
          fechaExpiracion: new Date(),
          tokenPagoId: null,
          cancelado: false,
        } as unknown as Pedido,
        { cancelado: true } as ActualizarPedidoDto,
      ),
    ).resolves.toBeUndefined();
  });
});
