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
import { ActualizarEstadoPedidoDto } from './dto/actualizar-estado-pedido.dto';
import { CrearEstadoPedidoDto } from './dto/crear-estado-pedido.dto';
import { EstadoPedidoPaginaDto } from './dto/estado-pedido-pagina.dto';
import { EstadoPedidoRespuestaDto } from './dto/estado-pedido-respuesta.dto';
import type { EstadoPedido } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** EstadoPedido tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: EstadoPedido): EstadoPedidoRespuestaDto {
  return {
    id: fila.id,
    nombre: fila.nombre,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de EstadoPedido. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class EstadoPedidoService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearEstadoPedidoDto): Promise<EstadoPedidoRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.estadoPedido.create({
        data: {
          nombre: datos.nombre,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<EstadoPedidoPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.estadoPedido.count(),
      this.prisma.estadoPedido.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<EstadoPedidoRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarEstadoPedidoDto,
  ): Promise<EstadoPedidoRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.estadoPedido.update({
        where: { id },
        data: {
          nombre: cambios.nombre,
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
      await this.prisma.estadoPedido.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<EstadoPedido> {
    const fila = await this.prisma.estadoPedido.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de EstadoPedido con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de EstadoPedido con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de EstadoPedido con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este EstadoPedido: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio estado_pedido
  // Reglas de negocio de EstadoPedido generadas por el LLM (fase 3) y verificadas con tsc.
  // Se regeneran con «framework servicio logica»: no editar a mano.
  // Controles ASVS: ASVS-V5.3.4, ASVS-V5.1.4

  protected async reglasAlCrear(datos: CrearEstadoPedidoDto): Promise<void> {
    const existente = await this.prisma.estadoPedido.findFirst({
      where: { nombre: datos.nombre },
      select: { id: true }
    });
    if (existente) {
      throw new ConflictException('Ya existe un estado con ese nombre.');
    }
  }

  protected async reglasAlActualizar(actual: EstadoPedido, cambios: ActualizarEstadoPedidoDto): Promise<void> {
    if (cambios.nombre && cambios.nombre !== actual.nombre) {
      const duplicado = await this.prisma.estadoPedido.findFirst({
        where: { nombre: cambios.nombre },
        select: { id: true }
      });
      if (duplicado) {
        throw new ConflictException('Ya existe otro estado con ese nombre.');
      }
      const usado = await this.prisma.pedido.findFirst({
        where: { estadoId: actual.id },
        select: { id: true }
      });
      if (usado) {
        throw new BadRequestException('No se puede modificar el nombre de un estado que está asociado a pedidos.');
      }
    }
  }

  protected async reglasAlEliminar(actual: EstadoPedido): Promise<void> {
    const usado = await this.prisma.pedido.findFirst({
      where: { estadoId: actual.id },
      select: { id: true }
    });
    if (usado) {
      throw new ConflictException('No se puede eliminar un estado que está asociado a pedidos.');
    }
  }
  // @framework:logica-negocio:fin estado_pedido
}
