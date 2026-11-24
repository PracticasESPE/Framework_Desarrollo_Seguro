import type { LogLevel } from '@nestjs/common';

/** Entornos admitidos en NODE_ENV. */
export const ENTORNOS = ['development', 'test', 'production'] as const;

export type NombreEntorno = (typeof ENTORNOS)[number];

/** Configuración del servicio ya validada. */
export interface Entorno {
  nombre: NombreEntorno;
  puerto: number;
  /** Swagger UI en /docs y el contrato en /docs-json: nunca en producción. */
  documentacion: boolean;
  /** Niveles del registro de Nest. */
  registro: LogLevel[];
}

/** Configuración ausente o inválida: el servicio no arranca. */
export class ConfiguracionInvalida extends Error {
  constructor(readonly problemas: string[]) {
    super(`Configuración inválida:\n- ${problemas.join('\n- ')}`);
    this.name = 'ConfiguracionInvalida';
  }
}

// Un switch exhaustivo en lugar de un objeto indexado por una variable: sin acceso por clave
// dinámica (eslint-plugin-security, detect-object-injection) y tsc avisa si falta un entorno.
function nivelesDeRegistro(nombre: NombreEntorno): LogLevel[] {
  switch (nombre) {
    case 'development':
      return ['fatal', 'error', 'warn', 'log', 'debug', 'verbose'];
    case 'test':
      return ['fatal', 'error', 'warn'];
    case 'production':
      return ['fatal', 'error', 'warn', 'log'];
  }
}

// La contraseña de .env.example: si llega a producción, nadie configuró la real.
const CLAVE_DE_EJEMPLO = 'cambiar';

function esEntorno(valor: string): valor is NombreEntorno {
  return (ENTORNOS as readonly string[]).includes(valor);
}

function decodificar(valor: string): string {
  try {
    return decodeURIComponent(valor);
  } catch {
    return valor;
  }
}

function url(valor: string, protocolos: string[]): URL | undefined {
  try {
    const leida = new URL(valor);
    return protocolos.includes(leida.protocol) ? leida : undefined;
  } catch {
    return undefined;
  }
}

/**
 * Lee y valida toda la configuración del servicio antes de crear nada.
 *
 * - Sin NODE_ENV se asume producción, el entorno más restrictivo (seguro por defecto): /docs
 *   desactivado y la contraseña de ejemplo rechazada.
 * - Reúne todos los problemas en un solo error para corregirlos de una vez.
 * - Los mensajes nombran la variable, nunca su valor: DATABASE_URL lleva la contraseña.
 */
export function leerEntorno(
  env: NodeJS.ProcessEnv,
  puertoPorDefecto: number,
): Entorno {
  const problemas: string[] = [];

  const nodeEnv = env.NODE_ENV?.trim() || 'production';
  const nombre: NombreEntorno = esEntorno(nodeEnv) ? nodeEnv : 'production';
  if (!esEntorno(nodeEnv)) {
    problemas.push(`NODE_ENV debe ser ${ENTORNOS.join(', ')}`);
  }

  let puerto = puertoPorDefecto;
  if (env.PORT !== undefined && env.PORT !== '') {
    puerto = /^\d{1,5}$/.test(env.PORT) ? Number(env.PORT) : NaN;
    if (!(puerto >= 1024 && puerto <= 65535)) {
      problemas.push('PORT debe ser un número entre 1024 y 65535');
    }
  }

  if (!env.DATABASE_URL) {
    problemas.push('Falta DATABASE_URL');
  } else {
    const base = url(env.DATABASE_URL, ['postgresql:', 'postgres:']);
    if (!base) {
      problemas.push('DATABASE_URL debe ser una URL postgresql://');
    } else if (nombre === 'production') {
      const clave = decodificar(base.password).toLowerCase();
      if (clave === '' || clave === CLAVE_DE_EJEMPLO) {
        problemas.push(
          'DATABASE_URL no tiene contraseña o usa la de .env.example; en producción hace falta la real',
        );
      }
    }
  }

  if (!env.KEYCLOAK_ISSUER) {
    problemas.push('Falta KEYCLOAK_ISSUER');
  } else if (!url(env.KEYCLOAK_ISSUER, ['http:', 'https:'])) {
    problemas.push('KEYCLOAK_ISSUER debe ser la URL http(s) del realm');
  }

  if (!env.KEYCLOAK_AUDIENCE) {
    problemas.push('Falta KEYCLOAK_AUDIENCE');
  } else if (!/^[A-Za-z0-9._-]{1,100}$/.test(env.KEYCLOAK_AUDIENCE)) {
    problemas.push(
      'KEYCLOAK_AUDIENCE solo admite letras, números, «.», «_» y «-»',
    );
  }

  if (
    env.KEYCLOAK_JWKS_URI &&
    !url(env.KEYCLOAK_JWKS_URI, ['http:', 'https:'])
  ) {
    problemas.push('KEYCLOAK_JWKS_URI debe ser una URL http(s)');
  }

  if (problemas.length > 0) {
    throw new ConfiguracionInvalida(problemas);
  }
  return {
    nombre,
    puerto,
    documentacion: nombre !== 'production',
    registro: nivelesDeRegistro(nombre),
  };
}
