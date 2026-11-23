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
import { ActualizarTransaccionDto } from './dto/actualizar-transaccion.dto';
import { CrearTransaccionDto } from './dto/crear-transaccion.dto';
import { TransaccionPaginaDto } from './dto/transaccion-pagina.dto';
import { TransaccionRespuestaDto } from './dto/transaccion-respuesta.dto';
import type { Transaccion } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** Transaccion tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: Transaccion): TransaccionRespuestaDto {
  return {
    id: fila.id,
    pagoId: fila.pagoId,
    tipo: fila.tipo,
    importe: fila.importe.toNumber(),
    fechaHora: fila.fechaHora.toISOString(),
    externalTransactionId: fila.externalTransactionId,
    estado: fila.estado,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de Transaccion. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class TransaccionService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearTransaccionDto): Promise<TransaccionRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.transaccion.create({
        data: {
          pagoId: datos.pagoId,
          tipo: datos.tipo,
          importe: datos.importe,
          fechaHora: aFecha(datos.fechaHora),
          externalTransactionId: datos.externalTransactionId,
          estado: datos.estado,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<TransaccionPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.transaccion.count(),
      this.prisma.transaccion.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<TransaccionRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarTransaccionDto,
  ): Promise<TransaccionRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.transaccion.update({
        where: { id },
        data: {
          pagoId: cambios.pagoId,
          tipo: cambios.tipo,
          importe: cambios.importe,
          fechaHora: aFecha(cambios.fechaHora),
          externalTransactionId: cambios.externalTransactionId,
          estado: cambios.estado,
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
      await this.prisma.transaccion.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<Transaccion> {
    const fila = await this.prisma.transaccion.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de Transaccion con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de Transaccion con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de Transaccion con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este Transaccion: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio transaccion
  // Punto de extensión: reglas de negocio de Transaccion. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearTransaccionDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: Transaccion,
    cambios: ActualizarTransaccionDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: Transaccion): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin transaccion
}
