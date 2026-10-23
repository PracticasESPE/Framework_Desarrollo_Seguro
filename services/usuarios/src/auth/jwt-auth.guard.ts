import {
  CanActivate,
  ExecutionContext,
  Inject,
  Injectable,
  InternalServerErrorException,
  Logger,
  Optional,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import {
  createRemoteJWKSet,
  errors,
  JWTPayload,
  jwtVerify,
  JWTVerifyGetKey,
} from 'jose';

export const OPCIONES_JWT = Symbol('OPCIONES_JWT');

export interface OpcionesJwt {
  /** Valor esperado del claim `iss` (URL del realm de Keycloak). */
  emisor: string;
  /** Valor esperado del claim `aud` (identificador de este servicio). */
  audiencia: string;
  /** Obtiene la clave pública que firmó el token (JWKS de Keycloak). */
  claves: JWTVerifyGetKey;
}

export interface SolicitudAutenticada {
  headers: Record<string, string | string[] | undefined>;
  user?: JWTPayload;
}

/** Lee la configuración del entorno; falla si falta algo (nunca hay valores por defecto inseguros). */
export function opcionesDesdeEntorno(
  env: NodeJS.ProcessEnv = process.env,
): OpcionesJwt {
  const emisor = env.KEYCLOAK_ISSUER;
  const audiencia = env.KEYCLOAK_AUDIENCE;
  if (!emisor || !audiencia) {
    throw new Error(
      'Faltan KEYCLOAK_ISSUER y/o KEYCLOAK_AUDIENCE en el entorno',
    );
  }
  const uri =
    env.KEYCLOAK_JWKS_URI ?? `${emisor}/protocol/openid-connect/certs`;
  return {
    emisor,
    audiencia,
    claves: createRemoteJWKSet(new URL(uri), {
      timeoutDuration: 3000,
      cooldownDuration: 30000,
    }),
  };
}

/** Se llama al arrancar (main.ts) para que el servicio no inicie sin configuración de seguridad. */
export function validarConfiguracionJwt(
  env: NodeJS.ProcessEnv = process.env,
): void {
  opcionesDesdeEntorno(env);
}

function extraerToken(
  cabecera: string | string[] | undefined,
): string | undefined {
  if (typeof cabecera !== 'string') return undefined;
  const partes = cabecera.split(' ');
  if (
    partes.length !== 2 ||
    partes[0].toLowerCase() !== 'bearer' ||
    partes[1] === ''
  ) {
    return undefined;
  }
  return partes[1];
}

// Errores de jose que indican que Keycloak no respondió bien (no que el token sea inválido):
// tiempo agotado, JWKS mal formado o respuesta HTTP distinta de 200.
const ERRORES_DE_DISPONIBILIDAD = new Set([
  'ERR_JWKS_TIMEOUT',
  'ERR_JWKS_INVALID',
  'ERR_JOSE_GENERIC',
]);

function esTokenInvalido(error: unknown): error is errors.JOSEError {
  return (
    error instanceof errors.JOSEError &&
    !ERRORES_DE_DISPONIBILIDAD.has(error.code)
  );
}

@Injectable()
export class JwtAuthGuard implements CanActivate {
  private readonly logger = new Logger(JwtAuthGuard.name);
  private opciones?: OpcionesJwt;

  constructor(@Optional() @Inject(OPCIONES_JWT) opciones?: OpcionesJwt) {
    this.opciones = opciones;
  }

  async canActivate(contexto: ExecutionContext): Promise<boolean> {
    const solicitud = contexto
      .switchToHttp()
      .getRequest<SolicitudAutenticada>();
    const token = extraerToken(solicitud.headers.authorization);
    if (!token) throw new UnauthorizedException();

    let opciones: OpcionesJwt;
    try {
      opciones = this.opciones ??= opcionesDesdeEntorno();
    } catch (error) {
      this.logger.error((error as Error).message);
      throw new InternalServerErrorException(); // cierra el acceso si falta configuración
    }

    try {
      const { payload } = await jwtVerify(token, opciones.claves, {
        issuer: opciones.emisor,
        audience: opciones.audiencia,
        algorithms: ['RS256'], // evita alg=none y la confusión HS256/RS256
        clockTolerance: 5,
      });
      solicitud.user = payload;
      return true;
    } catch (error) {
      if (esTokenInvalido(error)) {
        this.logger.warn(`Token rechazado: ${error.code}`); // sin registrar el token
        throw new UnauthorizedException();
      }
      this.logger.error(
        `No se pudieron obtener las claves de Keycloak: ${(error as Error).message}`,
      );
      throw new ServiceUnavailableException();
    }
  }
}
