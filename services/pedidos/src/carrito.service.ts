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
import { ActualizarCarritoDto } from './dto/actualizar-carrito.dto';
import { CrearCarritoDto } from './dto/crear-carrito.dto';
import { CarritoPaginaDto } from './dto/carrito-pagina.dto';
import { CarritoRespuestaDto } from './dto/carrito-respuesta.dto';
import type { Carrito } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** Carrito tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: Carrito): CarritoRespuestaDto {
  return {
    id: fila.id,
    clienteId: fila.clienteId,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de Carrito. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class CarritoService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearCarritoDto): Promise<CarritoRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.carrito.create({
        data: {
          clienteId: datos.clienteId,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<CarritoPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.carrito.count(),
      this.prisma.carrito.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<CarritoRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarCarritoDto,
  ): Promise<CarritoRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.carrito.update({
        where: { id },
        data: {
          clienteId: cambios.clienteId,
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
      await this.prisma.carrito.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<Carrito> {
    const fila = await this.prisma.carrito.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de Carrito con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de Carrito con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de Carrito con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este Carrito: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio carrito
  // Punto de extensión: reglas de negocio de Carrito. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearCarritoDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: Carrito,
    cambios: ActualizarCarritoDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: Carrito): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin carrito
}
