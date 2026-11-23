import { Module } from '@nestjs/common';
import { APP_FILTER, APP_GUARD, APP_PIPE } from '@nestjs/core';
import { PrismaService } from './prisma.service';
import { FiltroErrores } from './seguridad/filtro-errores';
import { JwtAuthGuard } from './seguridad/jwt-auth.guard';
import { crearValidacionGlobal } from './seguridad/validacion-global';
import { PedidoController } from './pedido.controller';
import { PedidoService } from './pedido.service';
import { CarritoController } from './carrito.controller';
import { CarritoService } from './carrito.service';
import { StockController } from './stock.controller';
import { StockService } from './stock.service';
import { LineaPedidoController } from './linea-pedido.controller';
import { LineaPedidoService } from './linea-pedido.service';

/**
 * Módulo del servicio pedidos: un controlador y un servicio por entidad. Los controles
 * transversales se registran aquí, no en main.ts, para que viajen con el módulo (también en las
 * pruebas): token de Keycloak en todas las rutas, validación en lista blanca y errores sin
 * detalles internos.
 */
@Module({
  controllers: [PedidoController, CarritoController, StockController, LineaPedidoController],
  providers: [
    PrismaService,
    PedidoService,
    CarritoService,
    StockService,
    LineaPedidoService,
    { provide: APP_GUARD, useClass: JwtAuthGuard },
    { provide: APP_PIPE, useFactory: crearValidacionGlobal },
    { provide: APP_FILTER, useClass: FiltroErrores },
  ],
})
export class PedidosModule {}
