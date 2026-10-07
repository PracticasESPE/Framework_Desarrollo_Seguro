import {
  ConflictException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import { CrearUsuarioDto } from './dto/crear-usuario.dto';
import { UsuarioRespuestaDto } from './dto/usuario-respuesta.dto';

@Injectable()
export class UsuariosService {
  // Almacenamiento temporal en memoria: se reemplaza por Prisma + PostgreSQL (07/10).
  private readonly usuarios = new Map<string, UsuarioRespuestaDto>();

  crear(dto: CrearUsuarioDto): UsuarioRespuestaDto {
    const existe = [...this.usuarios.values()].some((u) => u.correo === dto.correo);
    if (existe) {
      throw new ConflictException('Ya existe un usuario con ese correo');
    }
    const usuario: UsuarioRespuestaDto = {
      id: randomUUID(),
      nombre: dto.nombre,
      correo: dto.correo,
      telefono: dto.telefono,
      creadoEn: new Date().toISOString(),
    };
    this.usuarios.set(usuario.id, usuario);
    return usuario;
  }

  listar(): UsuarioRespuestaDto[] {
    return [...this.usuarios.values()];
  }

  obtener(id: string): UsuarioRespuestaDto {
    const usuario = this.usuarios.get(id);
    if (!usuario) {
      throw new NotFoundException('Usuario no encontrado');
    }
    return usuario;
  }
}
