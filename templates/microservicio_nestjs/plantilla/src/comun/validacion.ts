// Utilidades de validación que comparten los DTO generados por la plantilla.

/**
 * Sin caracteres de control: PostgreSQL rechaza el byte 0x00 y daría un error 500 en lugar de un
 * 400 (hallazgo de ZAP en el servicio de referencia).
 */
export const SIN_CONTROL = /^\P{Cc}+$/u;

/** El mismo conjunto que SIN_CONTROL, sin propiedades Unicode: el contrato lo leen otros motores. */
export const PATRON_SIN_CONTROL = '^[^\u0000-\u001F\u007F-\u009F]+$';

export const MENSAJE_SIN_CONTROL = '$property no puede contener caracteres de control';

/** Solo la fecha (AAAA-MM-DD), sin hora. */
export const FORMATO_FECHA = /^\d{4}-\d{2}-\d{2}$/;

export const MENSAJE_FECHA = '$property debe ser una fecha con el formato AAAA-MM-DD';

/** Quita los espacios de los extremos antes de validar la longitud. */
export const limpiarTexto = ({ value }: { value: unknown }): unknown =>
  typeof value === 'string' ? value.trim() : value;

/** Un correo se compara siempre en minúsculas y sin espacios en los extremos. */
export const normalizarCorreo = ({ value }: { value: unknown }): unknown =>
  typeof value === 'string' ? value.trim().toLowerCase() : value;

/**
 * Para @ValidateIf al actualizar: valida el campo solo si viene en la petición. A diferencia de
 * @IsOptional, un null sí se valida (y se rechaza) en los campos obligatorios.
 */
export const seEnvio = (_objeto: object, valor: unknown): boolean =>
  valor !== undefined;
