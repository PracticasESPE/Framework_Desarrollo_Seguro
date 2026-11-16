import { ApiProperty } from '@nestjs/swagger';
import { PATRON_SIN_CONTROL } from './validacion';

/** Cuerpo de las respuestas de error (404, 409…), tal como lo devuelve NestJS. */
export class ErrorRespuestaDto {
  @ApiProperty({ type: 'integer', format: 'int32', minimum: 400, maximum: 599, example: 404 })
  statusCode!: number;

  @ApiProperty({ maxLength: 300, pattern: PATRON_SIN_CONTROL, example: 'Registro no encontrado' })
  message!: string;

  @ApiProperty({ maxLength: 50, pattern: PATRON_SIN_CONTROL, example: 'Not Found' })
  error!: string;
}

/** Cuerpo del 400 de ValidationPipe: un mensaje por cada regla que no se cumplió. */
export class ErrorValidacionDto {
  @ApiProperty({ type: 'integer', format: 'int32', minimum: 400, maximum: 400, example: 400 })
  statusCode!: number;

  @ApiProperty({
    type: 'array',
    items: { type: 'string', maxLength: 300, pattern: PATRON_SIN_CONTROL },
    maxItems: 100,
    example: ['total must not be less than 0'],
  })
  message!: string[];

  @ApiProperty({ maxLength: 50, pattern: PATRON_SIN_CONTROL, example: 'Bad Request' })
  error!: string;
}
