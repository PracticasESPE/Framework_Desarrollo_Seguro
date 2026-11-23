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
import { ActualizarVentaReporteDto } from './dto/actualizar-venta-reporte.dto';
import { CrearVentaReporteDto } from './dto/crear-venta-reporte.dto';
import { VentaReportePaginaDto } from './dto/venta-reporte-pagina.dto';
import { VentaReporteRespuestaDto } from './dto/venta-reporte-respuesta.dto';
import type { VentaReporte } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** VentaReporte tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: VentaReporte): VentaReporteRespuestaDto {
  return {
    id: fila.id,
    fechaInicio: fila.fechaInicio.toISOString().slice(0, 10),
    fechaFin: fila.fechaFin.toISOString().slice(0, 10),
    totalVentas: fila.totalVentas.toNumber(),
    totalItems: fila.totalItems,
    generadoEn: fila.generadoEn.toISOString(),
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de VentaReporte. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class VentaReporteService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearVentaReporteDto): Promise<VentaReporteRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.ventaReporte.create({
        data: {
          fechaInicio: aFecha(datos.fechaInicio),
          fechaFin: aFecha(datos.fechaFin),
          totalVentas: datos.totalVentas,
          totalItems: datos.totalItems,
          generadoEn: aFecha(datos.generadoEn),
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<VentaReportePaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.ventaReporte.count(),
      this.prisma.ventaReporte.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<VentaReporteRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarVentaReporteDto,
  ): Promise<VentaReporteRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.ventaReporte.update({
        where: { id },
        data: {
          fechaInicio: aFecha(cambios.fechaInicio),
          fechaFin: aFecha(cambios.fechaFin),
          totalVentas: cambios.totalVentas,
          totalItems: cambios.totalItems,
          generadoEn: aFecha(cambios.generadoEn),
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
      await this.prisma.ventaReporte.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<VentaReporte> {
    const fila = await this.prisma.ventaReporte.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de VentaReporte con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de VentaReporte con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de VentaReporte con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este VentaReporte: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio venta_reporte
  // Punto de extensión: reglas de negocio de VentaReporte. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearVentaReporteDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: VentaReporte,
    cambios: ActualizarVentaReporteDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: VentaReporte): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin venta_reporte
}
