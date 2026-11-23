import { ValidationPipe } from '@nestjs/common';

/**
 * Validación de toda entrada con los DTO (class-validator), en lista blanca: una propiedad que el
 * DTO no declara (por ejemplo `esAdmin`) se rechaza con 400 en lugar de ignorarse (OWASP API3,
 * asignación masiva). Los errores no incluyen el objeto ni el valor recibido.
 */
export function crearValidacionGlobal(): ValidationPipe {
  return new ValidationPipe({
    whitelist: true,
    forbidNonWhitelisted: true,
    forbidUnknownValues: true,
    transform: true,
    validationError: { target: false, value: false },
  });
}
