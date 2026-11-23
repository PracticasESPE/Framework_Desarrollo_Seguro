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
import { ActualizarAuditoriaLogDto } from './dto/actualizar-auditoria-log.dto';
import { CrearAuditoriaLogDto } from './dto/crear-auditoria-log.dto';
import { AuditoriaLogPaginaDto } from './dto/auditoria-log-pagina.dto';
import { AuditoriaLogRespuestaDto } from './dto/auditoria-log-respuesta.dto';
import type { AuditoriaLog } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** AuditoriaLog tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: AuditoriaLog): AuditoriaLogRespuestaDto {
  return {
    id: fila.id,
    adminId: fila.adminId,
    accion: fila.accion,
    entidad: fila.entidad,
    entidadId: fila.entidadId,
    detalleCambio: fila.detalleCambio,
    fechaHora: fila.fechaHora.toISOString(),
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de AuditoriaLog. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class AuditoriaLogService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearAuditoriaLogDto): Promise<AuditoriaLogRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.auditoriaLog.create({
        data: {
          adminId: datos.adminId,
          accion: datos.accion,
          entidad: datos.entidad,
          entidadId: datos.entidadId,
          detalleCambio: datos.detalleCambio,
          fechaHora: aFecha(datos.fechaHora),
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<AuditoriaLogPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.auditoriaLog.count(),
      this.prisma.auditoriaLog.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<AuditoriaLogRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarAuditoriaLogDto,
  ): Promise<AuditoriaLogRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.auditoriaLog.update({
        where: { id },
        data: {
          adminId: cambios.adminId,
          accion: cambios.accion,
          entidad: cambios.entidad,
          entidadId: cambios.entidadId,
          detalleCambio: cambios.detalleCambio,
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
      await this.prisma.auditoriaLog.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<AuditoriaLog> {
    const fila = await this.prisma.auditoriaLog.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de AuditoriaLog con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de AuditoriaLog con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de AuditoriaLog con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este AuditoriaLog: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio auditoria_log
  // Punto de extensión: reglas de negocio de AuditoriaLog. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearAuditoriaLogDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: AuditoriaLog,
    cambios: ActualizarAuditoriaLogDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: AuditoriaLog): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin auditoria_log
}
