import { ApiProperty } from '@nestjs/swagger';
import { MAXIMO_POR_PAGINA, MAXIMO_DE_PAGINAS } from '../comun/paginacion.dto';
import { NotificacionRespuestaDto } from './notificacion-respuesta.dto';

/** Una página del listado de Notificacion. */
export class NotificacionPaginaDto {
  @ApiProperty({
    type: [NotificacionRespuestaDto],
    maxItems: MAXIMO_POR_PAGINA,
  })
  elementos!: NotificacionRespuestaDto[];

  @ApiProperty({
    type: 'integer',
    format: 'int32',
    minimum: 0,
    maximum: 2147483647,
    description: 'Total de registros, en todas las páginas',
  })
  total!: number;

  @ApiProperty({ type: 'integer', format: 'int32', minimum: 1, maximum: MAXIMO_DE_PAGINAS })
  pagina!: number;

  @ApiProperty({ type: 'integer', format: 'int32', minimum: 1, maximum: MAXIMO_POR_PAGINA })
  tamano!: number;
}
