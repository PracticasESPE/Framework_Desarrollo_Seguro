import { ApiProperty } from '@nestjs/swagger';

/** Cuerpo de las respuestas de error de NestJS (por ejemplo el 401 del guard JWT). */
export class ErrorRespuestaDto {
  @ApiProperty({
    type: 'integer',
    format: 'int32',
    minimum: 100,
    maximum: 599,
    example: 401,
  })
  statusCode!: number;

  @ApiProperty({ maxLength: 200, example: 'Unauthorized' })
  message!: string;
}
