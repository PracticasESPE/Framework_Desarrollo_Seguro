import { ApiProperty } from '@nestjs/swagger';
import { PATRON_SIN_CONTROL } from '../comun/validacion';

/**
 * Producto tal como la devuelve la API. Los límites coinciden con CrearProductoDto
 * y con prisma/schema.prisma (Gate 2, OWASP API4).
 */
export class ProductoRespuestaDto {
  @ApiProperty({ format: 'uuid', maxLength: 36 })
  id!: string;

  @ApiProperty({ description: 'Nombre del producto', maxLength: 100, pattern: PATRON_SIN_CONTROL })
  nombre!: string;

  @ApiProperty({ description: 'Descripción detallada del producto', maxLength: 1000, pattern: PATRON_SIN_CONTROL })
  descripcion!: string;

  @ApiProperty({ description: 'Precio del producto', type: 'number', minimum: 0.0, maximum: 999999.99 })
  precio!: number;

  @ApiProperty({ description: 'Cantidad de unidades disponibles en stock', type: 'integer', format: 'int32', minimum: 0, maximum: 1000000 })
  unidadesDisponibles!: number;

  @ApiProperty({ description: 'Referencia a la categoría del producto', format: 'uuid', maxLength: 36 })
  categoriaId!: string;

  @ApiProperty({ description: 'Indica si el producto está retirado del catálogo', type: 'boolean' })
  retirado!: boolean;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  creadoEn!: string;

  @ApiProperty({ format: 'date-time', maxLength: 30 })
  actualizadoEn!: string;
}
