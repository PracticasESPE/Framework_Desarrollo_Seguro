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
import { ActualizarStockDto } from './dto/actualizar-stock.dto';
import { CrearStockDto } from './dto/crear-stock.dto';
import { StockPaginaDto } from './dto/stock-pagina.dto';
import { StockRespuestaDto } from './dto/stock-respuesta.dto';
import type { Stock } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** Stock tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: Stock): StockRespuestaDto {
  return {
    id: fila.id,
    productoId: fila.productoId,
    cantidad: fila.cantidad,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de Stock. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class StockService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearStockDto): Promise<StockRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.stock.create({
        data: {
          productoId: datos.productoId,
          cantidad: datos.cantidad,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<StockPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.stock.count(),
      this.prisma.stock.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<StockRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarStockDto,
  ): Promise<StockRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.stock.update({
        where: { id },
        data: {
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
      await this.prisma.stock.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<Stock> {
    const fila = await this.prisma.stock.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de Stock con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de Stock con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de Stock con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este Stock: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio stock
  // Reglas de negocio de Stock generadas por el LLM (fase 3) y verificadas con tsc.
  // Se regeneran con «framework servicio logica»: no editar a mano.
  // Requisitos: RF-13, RF-12

  protected async reglasAlCrear(datos: CrearStockDto): Promise<void> {
    const producto = await this.prisma.producto.findUnique({ where: { id: datos.productoId } });
    if (!producto) {
      throw new NotFoundException('Producto no encontrado.');
    }
    const stockExistente = await this.prisma.stock.findUnique({ where: { productoId: datos.productoId } });
    if (stockExistente) {
      throw new ConflictException('Ya existe registro de stock para este producto.');
    }
  }

  protected async reglasAlActualizar(actual: Stock, cambios: ActualizarStockDto): Promise<void> {
    if (cambios.productoId && cambios.productoId !== actual.productoId) {
      const producto = await this.prisma.producto.findUnique({ where: { id: cambios.productoId } });
      if (!producto) {
        throw new NotFoundException('Producto no encontrado.');
      }
      const otroStock = await this.prisma.stock.findUnique({ where: { productoId: cambios.productoId } });
      if (otroStock) {
        throw new ConflictException('Ya existe registro de stock para el nuevo producto.');
      }
    }
    if (cambios.cantidad !== undefined) {
      if (cambios.cantidad < 0) {
        throw new BadRequestException('La cantidad de stock no puede ser negativa.');
      }
    }
  }

  protected async reglasAlEliminar(actual: Stock): Promise<void> {
    if (actual.cantidad > 0) {
      throw new ConflictException('No se puede eliminar un registro de stock que tenga unidades disponibles. Reduzca la cantidad a cero antes de eliminar.');
    }
  }
  // @framework:logica-negocio:fin stock
}
