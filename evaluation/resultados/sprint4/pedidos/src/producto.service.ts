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
import { ActualizarProductoDto } from './dto/actualizar-producto.dto';
import { CrearProductoDto } from './dto/crear-producto.dto';
import { ProductoPaginaDto } from './dto/producto-pagina.dto';
import { ProductoRespuestaDto } from './dto/producto-respuesta.dto';
import type { Producto } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** Producto tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: Producto): ProductoRespuestaDto {
  return {
    id: fila.id,
    sku: fila.sku,
    nombre: fila.nombre,
    descripcion: fila.descripcion ?? undefined,
    precio: fila.precio.toNumber(),
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de Producto. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class ProductoService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearProductoDto): Promise<ProductoRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.producto.create({
        data: {
          sku: datos.sku,
          nombre: datos.nombre,
          descripcion: datos.descripcion,
          precio: datos.precio,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<ProductoPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.producto.count(),
      this.prisma.producto.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<ProductoRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarProductoDto,
  ): Promise<ProductoRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.producto.update({
        where: { id },
        data: {
          sku: cambios.sku,
          nombre: cambios.nombre,
          descripcion: cambios.descripcion,
          precio: cambios.precio,
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
      await this.prisma.producto.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<Producto> {
    const fila = await this.prisma.producto.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de Producto con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de Producto con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de Producto con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este Producto: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio producto
  // Reglas de negocio de Producto generadas por el LLM (fase 3) y verificadas con tsc.
  // Se regeneran con «framework servicio logica»: no editar a mano.
  // Requisitos: RF-01, RF-13
  // Controles ASVS: ASVS-V5.1.4, ASVS-V4.1.3, ASVS-V7.4.1, ASVS-V5.3.4
  // Pendiente: Verificar que el producto no esté asociado a pedidos ya creados antes de eliminarlo.
  // Pendiente: Gestionar la actualización del precio para que no afecte a pedidos ya confirmados.

  protected async reglasAlCrear(datos: CrearProductoDto): Promise<void> {
    const existente = await this.prisma.producto.findUnique({ where: { sku: datos.sku } });
    if (existente) {
      throw new ConflictException('El SKU ya está en uso.');
    }
  }

  protected async reglasAlActualizar(actual: Producto, cambios: ActualizarProductoDto): Promise<void> {
    if (cambios.sku && cambios.sku !== actual.sku) {
      const existente = await this.prisma.producto.findUnique({ where: { sku: cambios.sku } });
      if (existente) {
        throw new ConflictException('El SKU ya está en uso.');
      }
    }
  }

  protected async reglasAlEliminar(actual: Producto): Promise<void> {
    const itemsEnCarrito = await this.prisma.carritoItem.count({ where: { productoId: actual.id } });
    if (itemsEnCarrito > 0) {
      throw new BadRequestException('No se puede eliminar el producto porque está en carritos de compra.');
    }
    const stock = await this.prisma.stock.findUnique({ where: { productoId: actual.id } });
    if (stock && stock.cantidad > 0) {
      throw new BadRequestException('No se puede eliminar el producto porque aún tiene stock disponible.');
    }
  }
  // @framework:logica-negocio:fin producto
}
