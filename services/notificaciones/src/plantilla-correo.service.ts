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
import { ActualizarPlantillaCorreoDto } from './dto/actualizar-plantilla-correo.dto';
import { CrearPlantillaCorreoDto } from './dto/crear-plantilla-correo.dto';
import { PlantillaCorreoPaginaDto } from './dto/plantilla-correo-pagina.dto';
import { PlantillaCorreoRespuestaDto } from './dto/plantilla-correo-respuesta.dto';
import type { PlantillaCorreo } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** PlantillaCorreo tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: PlantillaCorreo): PlantillaCorreoRespuestaDto {
  return {
    id: fila.id,
    nombre: fila.nombre,
    asunto: fila.asunto,
    cuerpo: fila.cuerpo,
    tipo: fila.tipo,
    activo: fila.activo,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de PlantillaCorreo. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class PlantillaCorreoService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearPlantillaCorreoDto): Promise<PlantillaCorreoRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.plantillaCorreo.create({
        data: {
          nombre: datos.nombre,
          asunto: datos.asunto,
          cuerpo: datos.cuerpo,
          tipo: datos.tipo,
          activo: datos.activo,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<PlantillaCorreoPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.plantillaCorreo.count(),
      this.prisma.plantillaCorreo.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<PlantillaCorreoRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarPlantillaCorreoDto,
  ): Promise<PlantillaCorreoRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.plantillaCorreo.update({
        where: { id },
        data: {
          nombre: cambios.nombre,
          asunto: cambios.asunto,
          cuerpo: cambios.cuerpo,
          tipo: cambios.tipo,
          activo: cambios.activo,
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
      await this.prisma.plantillaCorreo.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<PlantillaCorreo> {
    const fila = await this.prisma.plantillaCorreo.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de PlantillaCorreo con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de PlantillaCorreo con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de PlantillaCorreo con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este PlantillaCorreo: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio plantilla_correo
  // Punto de extensión: reglas de negocio de PlantillaCorreo. Lo completa el LLM (fase 3, #64);
  // el resto del archivo lo genera la plantilla y no se modifica. Cada método recibe datos ya
  // validados por el DTO y lanza BadRequestException, ConflictException o NotFoundException (ya
  // importadas) si la operación incumple una regla. Puede consultar la base con this.prisma. Sin
  // reglas, la operación sigue tal cual.

  protected reglasAlCrear(datos: CrearPlantillaCorreoDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected reglasAlActualizar(
    actual: PlantillaCorreo,
    cambios: ActualizarPlantillaCorreoDto,
  ): Promise<void> {
    void actual;
    void cambios;
    return Promise.resolve();
  }

  protected reglasAlEliminar(actual: PlantillaCorreo): Promise<void> {
    void actual;
    return Promise.resolve();
  }
  // @framework:logica-negocio:fin plantilla_correo
}
