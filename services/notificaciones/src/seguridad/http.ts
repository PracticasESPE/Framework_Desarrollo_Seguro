import {
  BadRequestException,
  PayloadTooLargeException,
  UnsupportedMediaTypeException,
} from '@nestjs/common';
import type { NestExpressApplication } from '@nestjs/platform-express';
import type { NextFunction, Request, Response } from 'express';
import helmet from 'helmet';

/** Tamaño máximo del cuerpo JSON de una petición (OWASP API4: consumo de recursos). */
export const LIMITE_DEL_CUERPO = '100kb';

/** Rutas de Swagger: la página /docs y el contrato en /docs-json y /docs-yaml. */
export function esDocumentacion(ruta: string): boolean {
  return ruta === '/docs' || ruta.startsWith('/docs/') || ruta.startsWith('/docs-');
}

// La API solo devuelve JSON: nada puede cargarse ni incrustarse desde sus respuestas.
const cabecerasApi = helmet({
  contentSecurityPolicy: {
    useDefaults: false,
    directives: { defaultSrc: ["'none'"], frameAncestors: ["'none'"] },
  },
  frameguard: { action: 'deny' },
});

// Swagger UI necesita sus scripts y estilos (del mismo origen) y los iconos en data:. Sin
// upgrade-insecure-requests para que «Try it out» funcione en http://localhost; en los demás
// entornos el TLS lo termina Traefik.
const cabecerasDocumentacion = helmet({
  contentSecurityPolicy: {
    directives: { frameAncestors: ["'none'"], upgradeInsecureRequests: null },
  },
  frameguard: { action: 'deny' },
});

function cabecerasDeSeguridad(req: Request, res: Response, next: NextFunction): void {
  if (esDocumentacion(req.path)) {
    cabecerasDocumentacion(req, res, next);
    return;
  }
  // Las respuestas de la API pueden llevar datos personales: ni el navegador ni un proxy las guardan.
  res.setHeader('Cache-Control', 'no-store');
  cabecerasApi(req, res, next);
}

/** Rechaza con 415 un cuerpo que no sea JSON (formularios, XML, texto). */
function soloJson(req: Request, _res: Response, next: NextFunction): void {
  // req.is devuelve null cuando la petición no tiene cuerpo y false cuando el tipo no coincide.
  if (req.is('application/json') === false) {
    next(new UnsupportedMediaTypeException('El cuerpo debe enviarse como application/json'));
    return;
  }
  next();
}

/**
 * Los errores del lector de JSON (body-parser) llevan el texto recibido en su mensaje; se cambian
 * por uno fijo antes de que lleguen al filtro de errores.
 */
function erroresDeLectura(
  error: unknown,
  _req: Request,
  _res: Response,
  next: NextFunction,
): void {
  const tipo = (error as { type?: unknown } | null)?.type;
  if (tipo === 'entity.too.large') {
    next(new PayloadTooLargeException(`El cuerpo supera el máximo de ${LIMITE_DEL_CUERPO}`));
  } else if (tipo === 'charset.unsupported' || tipo === 'encoding.unsupported') {
    next(new UnsupportedMediaTypeException('Codificación del cuerpo no admitida'));
  } else if (typeof tipo === 'string') {
    next(new BadRequestException('El cuerpo no es un JSON válido'));
  } else {
    next(error);
  }
}

/**
 * Controles HTTP del servicio, antes de cualquier ruta: cabeceras de seguridad (Helmet), sin
 * X-Powered-By, solo cuerpos JSON y con límite de tamaño. El servicio debe crearse con
 * `bodyParser: false` para que no haya otro lector (por ejemplo, de formularios).
 */
export function configurarHttp(app: NestExpressApplication): void {
  app.disable('x-powered-by');
  app.use(cabecerasDeSeguridad);
  app.use(soloJson);
  app.useBodyParser('json', { limit: LIMITE_DEL_CUERPO });
  app.use(erroresDeLectura);
}
