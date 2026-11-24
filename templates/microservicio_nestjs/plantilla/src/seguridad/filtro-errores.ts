import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import type { Response } from 'express';
import { STATUS_CODES } from 'node:http';

/** Cuerpo de toda respuesta de error: el de ErrorRespuestaDto y ErrorValidacionDto. */
export interface CuerpoError {
  statusCode: number;
  message: string | string[];
  error: string;
}

const MENSAJE_INTERNO = 'Error interno del servidor';
const RUTA_NO_ENCONTRADA = 'La ruta no existe';

// Los nombres estándar de los códigos HTTP («Not Found»…), en un Map: sin acceso por clave
// dinámica a un objeto (eslint-plugin-security, detect-object-injection).
const NOMBRES_DE_ESTADO = new Map(Object.entries(STATUS_CODES));

function nombreDelEstado(estado: number): string {
  return NOMBRES_DE_ESTADO.get(String(estado)) ?? 'Error';
}

function mensajeDe(respuesta: string | object): string | string[] | undefined {
  if (typeof respuesta === 'string') return respuesta;
  const { message } = respuesta as { message?: unknown };
  if (typeof message === 'string') return message;
  if (Array.isArray(message) && message.every((m): m is string => typeof m === 'string')) {
    return message;
  }
  return undefined;
}

/** Traduce cualquier excepción al cuerpo de error del contrato, sin datos internos. */
export function cuerpoDeError(excepcion: unknown): CuerpoError {
  if (!(excepcion instanceof HttpException)) {
    const estado = HttpStatus.INTERNAL_SERVER_ERROR;
    return { statusCode: estado, message: MENSAJE_INTERNO, error: nombreDelEstado(estado) };
  }
  const estado = excepcion.getStatus();
  const error = nombreDelEstado(estado);
  // Un 5xx nunca describe la causa: queda en el registro del servidor.
  if (estado >= 500) {
    const mensaje = estado === 500 ? MENSAJE_INTERNO : excepcion.message;
    return { statusCode: estado, message: mensaje, error };
  }
  let mensaje = mensajeDe(excepcion.getResponse()) ?? error;
  // El 404 del enrutador de NestJS repite la ruta pedida («Cannot GET /…»): no se refleja.
  if (estado === 404 && typeof mensaje === 'string' && mensaje.startsWith('Cannot ')) {
    mensaje = RUTA_NO_ENCONTRADA;
  }
  return { statusCode: estado, message: mensaje, error };
}

/**
 * Filtro global: todas las respuestas de error tienen el mismo formato y ninguna expone trazas,
 * consultas ni mensajes de librerías (OWASP API8, CWE-209). Los errores inesperados se registran
 * con su traza en el servidor, sin el cuerpo de la petición.
 */
@Catch()
export class FiltroErrores implements ExceptionFilter {
  private readonly logger = new Logger('FiltroErrores');

  catch(excepcion: unknown, host: ArgumentsHost): void {
    const respuesta = host.switchToHttp().getResponse<Response>();
    const cuerpo = cuerpoDeError(excepcion);

    if (!(excepcion instanceof HttpException)) {
      const traza = excepcion instanceof Error ? excepcion.stack : String(excepcion);
      this.logger.error(`Error no controlado: ${traza}`);
    }
    if (respuesta.headersSent) return;
    // statusCode es un number: se compara con 401 y no con el enum HttpStatus
    // (@typescript-eslint/no-unsafe-enum-comparison).
    if (cuerpo.statusCode === 401) {
      // RFC 6750: el 401 indica el esquema de autenticación que espera.
      respuesta.setHeader('WWW-Authenticate', 'Bearer');
    }
    respuesta.status(cuerpo.statusCode).json(cuerpo);
  }
}
