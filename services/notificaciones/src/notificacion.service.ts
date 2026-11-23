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
import { ActualizarNotificacionDto } from './dto/actualizar-notificacion.dto';
import { CrearNotificacionDto } from './dto/crear-notificacion.dto';
import { NotificacionPaginaDto } from './dto/notificacion-pagina.dto';
import { NotificacionRespuestaDto } from './dto/notificacion-respuesta.dto';
import type { Notificacion } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** Notificacion tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: Notificacion): NotificacionRespuestaDto {
  return {
    id: fila.id,
    pedidoId: fila.pedidoId,
    clienteId: fila.clienteId,
    clienteEmail: fila.clienteEmail,
    tipo: fila.tipo,
    plantillaCorreoId: fila.plantillaCorreoId,
    enviado: fila.enviado,
    fechaHora: fila.fechaHora.toISOString(),
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de Notificacion. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class NotificacionService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearNotificacionDto): Promise<NotificacionRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.notificacion.create({
        data: {
          pedidoId: datos.pedidoId,
          clienteId: datos.clienteId,
          clienteEmail: datos.clienteEmail,
          tipo: datos.tipo,
          plantillaCorreoId: datos.plantillaCorreoId,
          enviado: datos.enviado,
          fechaHora: aFecha(datos.fechaHora),
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<NotificacionPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.notificacion.count(),
      this.prisma.notificacion.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<NotificacionRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarNotificacionDto,
  ): Promise<NotificacionRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.notificacion.update({
        where: { id },
        data: {
          pedidoId: cambios.pedidoId,
          clienteId: cambios.clienteId,
          clienteEmail: cambios.clienteEmail,
          tipo: cambios.tipo,
          plantillaCorreoId: cambios.plantillaCorreoId,
          enviado: cambios.enviado,
          fechaHora: aFecha(cambios.fechaHora),
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
      await this.prisma.notificacion.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<Notificacion> {
    const fila = await this.prisma.notificacion.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de Notificacion con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de Notificacion con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de Notificacion con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este Notificacion: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio notificacion
  // Punto de extensión: reglas de negocio de Notificacion. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearNotificacionDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: Notificacion,
    cambios: ActualizarNotificacionDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: Notificacion): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin notificacion
}
