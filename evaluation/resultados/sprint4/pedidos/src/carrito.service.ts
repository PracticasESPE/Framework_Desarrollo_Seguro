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
  // Reglas de negocio de Carrito generadas por el LLM (fase 3) y verificadas con tsc.
  // Se regeneran con «framework servicio logica»: no editar a mano.
  // Requisitos: RF-01, RF-10, RF-11, RF-12, RF-13, RF-14, RF-16, RF-17, RF-18, RF-20
  // Controles ASVS: ASVS-V4.1.3, ASVS-V4.2.1, ASVS-V4.1.5
  // Pendiente: Validar que la cantidad de cada producto en el carrito esté entre 1 y 10 (RF-10).
  // Pendiente: Calcular precios y total del pedido usando el catálogo, sin confiar en datos del cliente (RF-11).
  // Pendiente: Gestionar concurrencia de stock al confirmar el pedido, rechazando productos sin disponibilidad (RF-12).
  // Pendiente: Descontar unidades del stock al aceptar el pedido (RF-13).
  // Pendiente: Aplicar control de acceso para que los clientes solo vean sus propios pedidos (RF-14).
  // Pendiente: Cancelar automáticamente pedidos no pagados en 30 minutos y devolver stock (RF-16).
  // Pendiente: Enviar correos al cliente en cambios de estado del pedido (RF-17).
  // Pendiente: Permitir al administrador cambiar el estado del pedido siguiendo el orden definido (RF-18).
  // Pendiente: Permitir al cliente cancelar un pedido antes de que sea enviado (RF-20).

  protected reglasAlCrear(datos: CrearCarritoDto): Promise<void> {
    void datos;
    return Promise.resolve();
  }

  protected async reglasAlActualizar(actual: Carrito, cambios: ActualizarCarritoDto): Promise<void> {
    if (cambios.clienteId && cambios.clienteId !== actual.clienteId) {
      throw new BadRequestException('No se puede cambiar el cliente del carrito.');
    }
  }

  protected async reglasAlEliminar(actual: Carrito): Promise<void> {
    const items = await this.prisma.carritoItem.findMany({
      where: { carritoId: actual.id },
      select: { id: true },
    });
    if (items.length > 0) {
      throw new ConflictException('No se puede eliminar el carrito porque contiene productos.');
    }
  }
  // @framework:logica-negocio:fin carrito
}
