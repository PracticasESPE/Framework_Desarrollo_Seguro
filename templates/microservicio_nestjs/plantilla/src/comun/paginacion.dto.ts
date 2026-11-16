import { ApiPropertyOptional } from '@nestjs/swagger';
import { Type } from 'class-transformer';
import { IsInt, Max, Min } from 'class-validator';

/** Tope de cada página: ningún listado devuelve más (OWASP API4, consumo de recursos). */
export const MAXIMO_POR_PAGINA = 100;

/** Tope del número de página: evita saltos que obliguen a la base a recorrer millones de filas. */
export const MAXIMO_DE_PAGINAS = 10000;

/** Parámetros de consulta de los listados: ?pagina=1&tamano=20. */
export class PaginacionDto {
  @ApiPropertyOptional({
    type: 'integer',
    format: 'int32',
    minimum: 1,
    maximum: MAXIMO_DE_PAGINAS,
    default: 1,
  })
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(MAXIMO_DE_PAGINAS)
  pagina: number = 1;

  @ApiPropertyOptional({
    type: 'integer',
    format: 'int32',
    minimum: 1,
    maximum: MAXIMO_POR_PAGINA,
    default: 20,
  })
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(MAXIMO_POR_PAGINA)
  tamano: number = 20;
}
