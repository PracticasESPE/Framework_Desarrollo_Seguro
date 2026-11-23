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
import { ActualizarPagoDto } from './dto/actualizar-pago.dto';
import { CrearPagoDto } from './dto/crear-pago.dto';
import { PagoPaginaDto } from './dto/pago-pagina.dto';
import { PagoRespuestaDto } from './dto/pago-respuesta.dto';
import type { Pago } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** Pago tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: Pago): PagoRespuestaDto {
  return {
    id: fila.id,
    importe: fila.importe.toNumber(),
    moneda: fila.moneda,
    estado: fila.estado,
    externalPaymentId: fila.externalPaymentId,
    pedidoId: fila.pedidoId,
    transaccionId: fila.transaccionId ?? undefined,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de Pago. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class PagoService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearPagoDto): Promise<PagoRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.pago.create({
        data: {
          importe: datos.importe,
          moneda: datos.moneda,
          estado: datos.estado,
          externalPaymentId: datos.externalPaymentId,
          pedidoId: datos.pedidoId,
          transaccionId: datos.transaccionId,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<PagoPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.pago.count(),
      this.prisma.pago.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<PagoRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarPagoDto,
  ): Promise<PagoRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.pago.update({
        where: { id },
        data: {
          importe: cambios.importe,
          moneda: cambios.moneda,
          estado: cambios.estado,
          externalPaymentId: cambios.externalPaymentId,
          pedidoId: cambios.pedidoId,
          transaccionId: cambios.transaccionId,
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
      await this.prisma.pago.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<Pago> {
    const fila = await this.prisma.pago.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de Pago con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de Pago con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de Pago con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este Pago: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio pago
  // Punto de extensión: reglas de negocio de Pago. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearPagoDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: Pago,
    cambios: ActualizarPagoDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: Pago): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin pago
}
