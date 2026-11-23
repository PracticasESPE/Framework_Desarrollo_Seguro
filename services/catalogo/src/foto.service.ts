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
import { ActualizarFotoDto } from './dto/actualizar-foto.dto';
import { CrearFotoDto } from './dto/crear-foto.dto';
import { FotoPaginaDto } from './dto/foto-pagina.dto';
import { FotoRespuestaDto } from './dto/foto-respuesta.dto';
import type { Foto } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** Foto tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: Foto): FotoRespuestaDto {
  return {
    id: fila.id,
    url: fila.url,
    productoId: fila.productoId,
    tipo: fila.tipo,
    orden: fila.orden ?? undefined,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de Foto. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class FotoService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearFotoDto): Promise<FotoRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.foto.create({
        data: {
          url: datos.url,
          productoId: datos.productoId,
          tipo: datos.tipo,
          orden: datos.orden,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<FotoPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.foto.count(),
      this.prisma.foto.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<FotoRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarFotoDto,
  ): Promise<FotoRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.foto.update({
        where: { id },
        data: {
          url: cambios.url,
          productoId: cambios.productoId,
          tipo: cambios.tipo,
          orden: cambios.orden,
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
      await this.prisma.foto.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<Foto> {
    const fila = await this.prisma.foto.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de Foto con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de Foto con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de Foto con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este Foto: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio foto
  // Punto de extensión: reglas de negocio de Foto. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearFotoDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: Foto,
    cambios: ActualizarFotoDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: Foto): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin foto
}
