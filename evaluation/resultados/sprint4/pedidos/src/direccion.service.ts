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
import { ActualizarDireccionDto } from './dto/actualizar-direccion.dto';
import { CrearDireccionDto } from './dto/crear-direccion.dto';
import { DireccionPaginaDto } from './dto/direccion-pagina.dto';
import { DireccionRespuestaDto } from './dto/direccion-respuesta.dto';
import type { Direccion } from './generated/prisma/client';
import { PrismaService } from './prisma.service';

/** Direccion tal como la devuelve la API: sin null y con fechas y decimales en JSON. */
function aRespuesta(fila: Direccion): DireccionRespuestaDto {
  return {
    id: fila.id,
    clienteId: fila.clienteId,
    nombreRecibe: fila.nombreRecibe,
    calle: fila.calle,
    ciudad: fila.ciudad,
    codigoPostal: fila.codigoPostal,
    pais: fila.pais,
    creadoEn: fila.creadoEn.toISOString(),
    actualizadoEn: fila.actualizadoEn.toISOString(),
  };
}

/**
 * Operaciones de Direccion. El acceso a la base y el manejo de errores los genera la
 * plantilla; las reglas de negocio van en el bloque marcado al final de la clase.
 */
@Injectable()
export class DireccionService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(datos: CrearDireccionDto): Promise<DireccionRespuestaDto> {
    await this.reglasAlCrear(datos);
    try {
      const fila = await this.prisma.direccion.create({
        data: {
          clienteId: datos.clienteId,
          nombreRecibe: datos.nombreRecibe,
          calle: datos.calle,
          ciudad: datos.ciudad,
          codigoPostal: datos.codigoPostal,
          pais: datos.pais,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      throw this.traducirError(error, 'guardar');
    }
  }

  async listar({ pagina, tamano }: PaginacionDto): Promise<DireccionPaginaDto> {
    const [total, filas] = await this.prisma.$transaction([
      this.prisma.direccion.count(),
      this.prisma.direccion.findMany({
        // Orden estable: dos páginas seguidas nunca repiten ni saltan un registro.
        orderBy: [{ creadoEn: 'asc' }, { id: 'asc' }],
        skip: (pagina - 1) * tamano,
        take: tamano,
      }),
    ]);
    return { elementos: filas.map(aRespuesta), total, pagina, tamano };
  }

  async obtener(id: string): Promise<DireccionRespuestaDto> {
    return aRespuesta(await this.buscar(id));
  }

  async actualizar(
    id: string,
    cambios: ActualizarDireccionDto,
  ): Promise<DireccionRespuestaDto> {
    const actual = await this.buscar(id);
    await this.reglasAlActualizar(actual, cambios);
    try {
      const fila = await this.prisma.direccion.update({
        where: { id },
        data: {
          clienteId: cambios.clienteId,
          nombreRecibe: cambios.nombreRecibe,
          calle: cambios.calle,
          ciudad: cambios.ciudad,
          codigoPostal: cambios.codigoPostal,
          pais: cambios.pais,
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
      await this.prisma.direccion.delete({ where: { id } });
    } catch (error) {
      throw this.traducirError(error, 'eliminar');
    }
  }

  private async buscar(id: string): Promise<Direccion> {
    const fila = await this.prisma.direccion.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('No existe ningún registro de Direccion con ese id');
    }
    return fila;
  }

  /** Los errores de datos de Prisma son 400, 404 o 409, nunca 500. */
  private traducirError(error: unknown, operacion: 'guardar' | 'eliminar'): unknown {
    if (esValorRepetido(error)) {
      return new ConflictException('Ya existe un registro de Direccion con ese valor único');
    }
    if (esRegistroInexistente(error)) {
      return new NotFoundException('No existe ningún registro de Direccion con ese id');
    }
    if (esRelacionRota(error)) {
      return operacion === 'eliminar'
        ? new ConflictException('Otros registros dependen de este Direccion: no se puede eliminar')
        : new BadRequestException('Un identificador de otra entidad no corresponde a ningún registro');
    }
    return error;
  }

  // @framework:logica-negocio:inicio direccion
  // Reglas de negocio de Direccion generadas por el LLM (fase 3) y verificadas con tsc.
  // Se regeneran con «framework servicio logica»: no editar a mano.
  // Requisitos: RF-14
  // Controles ASVS: ASVS-V4.1.3, ASVS-V4.1.5, ASVS-V4.2.1, ASVS-V7.4.1, ASVS-V5.1.4
  // Pendiente: Validar que el clienteId del DTO coincida con el usuario autenticado (se necesita el id del usuario en el contexto)

  protected reglasAlCrear(datos: CrearDireccionDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected async reglasAlActualizar(actual: Direccion, cambios: ActualizarDireccionDto): Promise<void> {
    if (cambios.clienteId && cambios.clienteId !== actual.clienteId) {
      throw new BadRequestException('No es posible cambiar el cliente de la dirección');
    }
  }

  protected async reglasAlEliminar(actual: Direccion): Promise<void> {
    const pedidos = await this.prisma.pedido.findMany({
      where: {
        direccionId: actual.id,
        cancelado: false,
      },
      select: { id: true },
    });

    if (pedidos.length > 0) {
      throw new ConflictException('No se puede eliminar la dirección porque existen pedidos asociados');
    }
  }
  // @framework:logica-negocio:fin direccion
}
