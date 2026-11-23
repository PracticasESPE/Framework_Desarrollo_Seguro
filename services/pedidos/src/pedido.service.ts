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
    estado: fila.estado,
    total: fila.total.toNumber(),
    pagoId: fila.pagoId ?? undefined,
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
          estado: datos.estado,
          total: datos.total,
          pagoId: datos.pagoId,
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
          estado: cambios.estado,
          total: cambios.total,
          pagoId: cambios.pagoId,
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
  // Punto de extensión: reglas de negocio de Pedido. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearPedidoDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: Pedido,
    cambios: ActualizarPedidoDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: Pedido): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin pedido
}
