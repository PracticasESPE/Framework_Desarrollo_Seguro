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
import { ActualizarLineaPedidoDto } from './dto/actualizar-linea-pedido.dto';
import { CrearLineaPedidoDto } from './dto/crear-linea-pedido.dto';
import { LineaPedidoPaginaDto } from './dto/linea-pedido-pagina.dto';
import { LineaPedidoRespuestaDto } from './dto/linea-pedido-respuesta.dto';
import type { LineaPedido } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** LineaPedido tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: LineaPedido): LineaPedidoRespuestaDto {
  return {
    id: fila.id,
    pedidoId: fila.pedidoId ?? undefined,
    carritoId: fila.carritoId ?? undefined,
    productoId: fila.productoId,
    cantidad: fila.cantidad,
    precioUnitario: fila.precioUnitario.toNumber(),
    subtotal: fila.subtotal.toNumber(),
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de LineaPedido. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class LineaPedidoService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearLineaPedidoDto): Promise<LineaPedidoRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.lineaPedido.create({
        data: {
          pedidoId: datos.pedidoId,
          carritoId: datos.carritoId,
          productoId: datos.productoId,
          cantidad: datos.cantidad,
          precioUnitario: datos.precioUnitario,
          subtotal: datos.subtotal,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<LineaPedidoPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.lineaPedido.count(),
      this.prisma.lineaPedido.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<LineaPedidoRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarLineaPedidoDto,
  ): Promise<LineaPedidoRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.lineaPedido.update({
        where: { id },
        data: {
          pedidoId: cambios.pedidoId,
          carritoId: cambios.carritoId,
          productoId: cambios.productoId,
          cantidad: cambios.cantidad,
          precioUnitario: cambios.precioUnitario,
          subtotal: cambios.subtotal,
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
      await this.prisma.lineaPedido.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<LineaPedido> {
    const fila = await this.prisma.lineaPedido.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de LineaPedido con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de LineaPedido con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de LineaPedido con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este LineaPedido: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio linea_pedido
  // Punto de extensión: reglas de negocio de LineaPedido. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearLineaPedidoDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: LineaPedido,
    cambios: ActualizarLineaPedidoDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: LineaPedido): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin linea_pedido
}
