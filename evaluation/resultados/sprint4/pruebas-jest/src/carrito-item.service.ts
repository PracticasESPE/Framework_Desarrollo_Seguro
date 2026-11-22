import {
  BadRequestException,
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import {
  esRegistroInexistente,
  esRelacionRota,
  esValorRepetido,
} from './comun/errores-prisma';
import { PaginacionDto } from './comun/paginacion.dto';
import { ActualizarCarritoItemDto } from './dto/actualizar-carrito-item.dto';
import { CrearCarritoItemDto } from './dto/crear-carrito-item.dto';
import { CarritoItemPaginaDto } from './dto/carrito-item-pagina.dto';
import { CarritoItemRespuestaDto } from './dto/carrito-item-respuesta.dto';
import type { CarritoItem } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** CarritoItem tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: CarritoItem): CarritoItemRespuestaDto {
  return {
    id: fila.id,
    carritoId: fila.carritoId,
    productoId: fila.productoId,
    cantidad: fila.cantidad,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de CarritoItem. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class CarritoItemService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearCarritoItemDto): Promise<CarritoItemRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.carritoItem.create({
        data: {
          carritoId: datos.carritoId,
          productoId: datos.productoId,
          cantidad: datos.cantidad,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<CarritoItemPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.carritoItem.count(),
      this.prisma.carritoItem.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<CarritoItemRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarCarritoItemDto,
  ): Promise<CarritoItemRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.carritoItem.update({
        where: { id },
        data: {
          carritoId: cambios.carritoId,
          productoId: cambios.productoId,
          cantidad: cambios.cantidad,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async eliminar(id: string): Promise<void> {
    const actual = await this.buscar(id);
    await this.reglasAlEliminar(actual);
    try {
      await this.prisma.carritoItem.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<CarritoItem> {
    const fila = await this.prisma.carritoItem.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de CarritoItem con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de CarritoItem con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de CarritoItem con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este CarritoItem: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio carrito_item
  // Reglas de negocio de CarritoItem generadas por el LLM (fase 3) y verificadas con tsc.
  // Se regeneran con «framework servicio logica»: no editar a mano.
  // Requisitos: RF-10, RF-12
  // Pendiente: Verificar que el carrito pertenece al cliente autenticado al crear o actualizar un ítem.

  protected async reglasAlCrear(datos: CrearCarritoItemDto): Promise<void> {
    const carrito = await this.prisma.carrito.findUnique({
      where: { id: datos.carritoId },
      select: { id: true },
    });
    if (!carrito) {
      throw new BadRequestException('El carrito especificado no existe.');
    }

    const producto = await this.prisma.producto.findUnique({
      where: { id: datos.productoId },
      select: { id: true },
    });
    if (!producto) {
      throw new BadRequestException('El producto especificado no existe.');
    }

    // Verificar stock disponible
    const stock = await this.prisma.stock.findUnique({
      where: { productoId: datos.productoId },
      select: { cantidad: true },
    });
    if (!stock || stock.cantidad < datos.cantidad) {
      throw new ConflictException('No hay suficiente stock del producto seleccionado.');
    }

    // Evitar duplicados en el mismo carrito
    const existente = await this.prisma.carritoItem.findFirst({
      where: {
        carritoId: datos.carritoId,
        productoId: datos.productoId,
      },
      select: { id: true },
    });
    if (existente) {
      throw new ConflictException('El producto ya está agregado al carrito.');
    }
  }

  protected async reglasAlActualizar(actual: CarritoItem, cambios: ActualizarCarritoItemDto): Promise<void> {
    if (cambios.carritoId) {
      const carrito = await this.prisma.carrito.findUnique({
        where: { id: cambios.carritoId },
        select: { id: true },
      });
      if (!carrito) {
        throw new BadRequestException('El carrito especificado no existe.');
      }
    }

    if (cambios.productoId) {
      const producto = await this.prisma.producto.findUnique({
        where: { id: cambios.productoId },
        select: { id: true },
      });
      if (!producto) {
        throw new BadRequestException('El producto especificado no existe.');
      }
    }

    // Verificar que no exista otro ítem con mismo carrito y producto
    if (cambios.carritoId || cambios.productoId) {
      const carritoId = cambios.carritoId ?? actual.carritoId;
      const productoId = cambios.productoId ?? actual.productoId;
      const otro = await this.prisma.carritoItem.findFirst({
        where: {
          carritoId,
          productoId,
          NOT: { id: actual.id },
        },
        select: { id: true },
      });
      if (otro) {
        throw new ConflictException('Ya existe otro ítem con el mismo producto en el carrito.');
      }
    }

    // Verificar stock si cambia cantidad o producto
    if (cambios.cantidad !== undefined) {
      const productoId = cambios.productoId ?? actual.productoId;
      const stock = await this.prisma.stock.findUnique({
        where: { productoId },
        select: { cantidad: true },
      });
      const disponible = (stock?.cantidad ?? 0) + actual.cantidad - cambios.cantidad;
      if (disponible < 0) {
        throw new ConflictException('No hay suficiente stock para la cantidad solicitada.');
      }
    }
  }

  protected reglasAlEliminar(actual: CarritoItem): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin carrito_item
}
