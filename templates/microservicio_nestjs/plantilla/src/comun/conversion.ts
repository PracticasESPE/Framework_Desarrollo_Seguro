// Conversión de las fechas que llegan como texto en los DTO al tipo que espera Prisma.

/**
 * «2026-12-01» o «2026-12-01T10:00:00Z» como Date. null y undefined se conservan: null vacía un
 * campo opcional y undefined lo deja como estaba.
 */
export function aFecha(valor: string): Date;
export function aFecha(valor: string | null | undefined): Date | null | undefined;
export function aFecha(valor: string | null | undefined): Date | null | undefined {
  return typeof valor === 'string' ? new Date(valor) : valor;
}
