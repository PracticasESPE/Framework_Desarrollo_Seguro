import {
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { CrearUsuarioDto } from './dto/crear-usuario.dto';
import { UsuarioRespuestaDto } from './dto/usuario-respuesta.dto';
import { PrismaService } from './prisma.service';

interface FilaUsuario {
  id: string;
  nombre: string;
  correo: string;
  telefono: string | null;
  creadoEn: Date;
}

// Código de Prisma para "ya existe un registro con ese valor único".
const VIOLACION_UNICA = 'P2002';

function esViolacionUnica(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    error.code === VIOLACION_UNICA
  );
}

function aRespuesta(fila: FilaUsuario): UsuarioRespuestaDto {
  return {
    id: fila.id,
    nombre: fila.nombre,
    correo: fila.correo,
    telefono: fila.telefono ?? undefined,
    creadoEn: fila.creadoEn.toISOString(),
  };
}

@Injectable()
export class UsuariosService {
  constructor(private readonly prisma: PrismaService) {}

  async crear(dto: CrearUsuarioDto): Promise<UsuarioRespuestaDto> {
    try {
      const fila = await this.prisma.usuario.create({
        data: {
          nombre: dto.nombre,
          correo: dto.correo,
          telefono: dto.telefono,
        },
      });
      return aRespuesta(fila);
    } catch (error) {
      if (esViolacionUnica(error)) {
        throw new ConflictException('Ya existe un usuario con ese correo');
      }
      throw error;
    }
  }

  async listar(): Promise<UsuarioRespuestaDto[]> {
    // Máximo 100 por ahora; la paginación llega más adelante.
    const filas = await this.prisma.usuario.findMany({
      orderBy: { creadoEn: 'asc' },
      take: 100,
    });
    return filas.map(aRespuesta);
  }

  async obtener(id: string): Promise<UsuarioRespuestaDto> {
    const fila = await this.prisma.usuario.findUnique({ where: { id } });
    if (!fila) {
      throw new NotFoundException('Usuario no encontrado');
    }
    return aRespuesta(fila);
  }
}
