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
  // Punto de extensión: reglas de negocio de Stock. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearStockDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: Stock,
    cambios: ActualizarStockDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: Stock): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin stock
}
