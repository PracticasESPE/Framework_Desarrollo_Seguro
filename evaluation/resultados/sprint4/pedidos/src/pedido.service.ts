import {
  BadRequestException,
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { aFecha } from './comun/conversion';
import {
  esRegistroInexistente,
  esRelacionRota,
  esValorRepetido,
} from './comun/errores-prisma';
import { PaginacionDto } from './comun/paginacion.dto';
import { ActualizarPedidoDto } from './dto/actualizar-pedido.dto';
import { CrearPedidoDto } from './dto/crear-pedido.dto';
import { PedidoPaginaDto } from './dto/pedido-pagina.dto';
import { PedidoRespuestaDto } from './dto/pedido-respuesta.dto';
import type { Pedido } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** Pedido tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: Pedido): PedidoRespuestaDto {
  return {
    id: fila.id,
    clienteId: fila.clienteId,
    direccionId: fila.direccionId,
    total: fila.total.toNumber(),
    estadoId: fila.estadoId,
    fechaExpiracion: fila.fechaExpiracion?.toISOString(),
    tokenPagoId: fila.tokenPagoId ?? undefined,
    cancelado: fila.cancelado,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de Pedido. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class PedidoService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearPedidoDto): Promise<PedidoRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.pedido.create({
        data: {
          clienteId: datos.clienteId,
          direccionId: datos.direccionId,
          total: datos.total,
          estadoId: datos.estadoId,
          fechaExpiracion: aFecha(datos.fechaExpiracion),
          tokenPagoId: datos.tokenPagoId,
          cancelado: datos.cancelado,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<PedidoPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.pedido.count(),
      this.prisma.pedido.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<PedidoRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarPedidoDto,
  ): Promise<PedidoRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.pedido.update({
        where: { id },
        data: {
          clienteId: cambios.clienteId,
          direccionId: cambios.direccionId,
          total: cambios.total,
          estadoId: cambios.estadoId,
          fechaExpiracion: aFecha(cambios.fechaExpiracion),
          tokenPagoId: cambios.tokenPagoId,
          cancelado: cambios.cancelado,
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
      await this.prisma.pedido.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<Pedido> {
    const fila = await this.prisma.pedido.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de Pedido con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de Pedido con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de Pedido con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este Pedido: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio pedido
  // Reglas de negocio de Pedido generadas por el LLM (fase 3) y verificadas con tsc.
  // Se regeneran con «framework servicio logica»: no editar a mano.
  // Requisitos: RF-11, RF-12, RF-13, RF-16, RF-20
  // Controles ASVS: ASVS-V5.1.4, ASVS-V5.1.3, ASVS-V4.1.3, ASVS-V4.1.5, ASVS-V7.4.1, ASVS-V4.2.1
  // Pendiente: Devolver el stock de los productos cuando se cancela un pedido (se necesita acceder a los ítems del pedido, que no están disponibles en este método)
  // Pendiente: Implementar la cancelación automática al expirar los 30 minutos (requiere proceso programado fuera de estos métodos)

  protected async reglasAlCrear(datos: CrearPedidoDto): Promise<void> {
    const carrito = await this.prisma.carrito.findFirst({
      where: { clienteId: datos.clienteId },
    });
    if (!carrito) {
      throw new BadRequestException('El carrito está vacío');
    }
    const items = await this.prisma.carritoItem.findMany({
      where: { carritoId: carrito.id },
      include: { producto: true },
    });
    if (items.length === 0) {
      throw new BadRequestException('El carrito está vacío');
    }
    let totalCalculado = 0;
    for (const item of items) {
      const precio = item.producto.precio.toNumber();
      totalCalculado += precio * item.cantidad;
      const stock = await this.prisma.stock.findUnique({
        where: { productoId: item.productoId },
      });
      if (!stock || stock.cantidad < item.cantidad) {
        throw new ConflictException(
          `El producto ${item.producto.nombre} no tiene stock suficiente`,
        );
      }
      await this.prisma.stock.update({
        where: { productoId: item.productoId },
        data: { cantidad: stock.cantidad - item.cantidad },
      });
    }
    if (Math.abs(totalCalculado - datos.total) > 0.01) {
      throw new BadRequestException('El total del pedido no coincide con el cálculo del servidor');
    }
    if (!datos.fechaExpiracion) {
      const fecha = new Date(Date.now() + 30 * 60 * 1000);
      datos.fechaExpiracion = fecha.toISOString();
    }
  }

  protected async reglasAlActualizar(actual: Pedido, cambios: ActualizarPedidoDto): Promise<void> {
    if (cambios.cancelado === true && actual.cancelado === false) {
      const estado = await this.prisma.estadoPedido.findUnique({
        where: { id: actual.estadoId },
      });
      if (!estado) {
        throw new NotFoundException('Estado del pedido no encontrado');
      }
      const estadosNoCancelables = ['enviado', 'entregado'];
      if (estadosNoCancelables.includes(estado.nombre.toLowerCase())) {
        throw new BadRequestException('No se puede cancelar un pedido que ya ha sido enviado');
      }
      // Pendiente: devolver stock de los productos del pedido cancelado
    }
  }

  protected reglasAlEliminar(actual: Pedido): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin pedido
}
