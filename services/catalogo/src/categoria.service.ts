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
import { ActualizarCategoriaDto } from './dto/actualizar-categoria.dto';
import { CrearCategoriaDto } from './dto/crear-categoria.dto';
import { CategoriaPaginaDto } from './dto/categoria-pagina.dto';
import { CategoriaRespuestaDto } from './dto/categoria-respuesta.dto';
import type { Categoria } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** Categoria tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: Categoria): CategoriaRespuestaDto {
  return {
    id: fila.id,
    nombre: fila.nombre,
    descripcion: fila.descripcion ?? undefined,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de Categoria. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class CategoriaService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearCategoriaDto): Promise<CategoriaRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.categoria.create({
        data: {
          nombre: datos.nombre,
          descripcion: datos.descripcion,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<CategoriaPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.categoria.count(),
      this.prisma.categoria.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<CategoriaRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarCategoriaDto,
  ): Promise<CategoriaRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.categoria.update({
        where: { id },
        data: {
          nombre: cambios.nombre,
          descripcion: cambios.descripcion,
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
      await this.prisma.categoria.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<Categoria> {
    const fila = await this.prisma.categoria.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de Categoria con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de Categoria con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de Categoria con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este Categoria: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio categoria
  // Punto de extensión: reglas de negocio de Categoria. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearCategoriaDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: Categoria,
    cambios: ActualizarCategoriaDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: Categoria): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin categoria
}
