// Errores conocidos de Prisma que no son fallos del servidor: el servicio los convierte en 400,
// 404 o 409. Si se dejaran pasar, la API respondería 500 y el DAST lo contaría como hallazgo.

function codigo(error: unknown): string | undefined {
  if (typeof error === 'object' && error !== null && 'code' in error) {
    return typeof error.code === 'string' ? error.code : undefined;
  }
  return undefined;
}

/** P2002: ya existe un registro con ese valor en un campo único. */
export function esValorRepetido(error: unknown): boolean {
  return codigo(error) === 'P2002';
}

/** P2025: el registro que se quería cambiar o borrar ya no existe. */
export function esRegistroInexistente(error: unknown): boolean {
  return codigo(error) === 'P2025';
}

/** P2003 y P2014: la operación rompería una relación (una referencia que no existe o en uso). */
export function esRelacionRota(error: unknown): boolean {
  const valor = codigo(error);
  return valor === 'P2003' || valor === 'P2014';
}
