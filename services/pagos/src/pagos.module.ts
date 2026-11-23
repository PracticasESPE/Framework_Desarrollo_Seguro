import { Module } from '@nestjs/common';
import { APP_FILTER, APP_GUARD, APP_PIPE } from '@nestjs/core';
import { PrismaService } from './prisma.service';
import { FiltroErrores } from './seguridad/filtro-errores';
import { JwtAuthGuard } from './seguridad/jwt-auth.guard';
import { crearValidacionGlobal } from './seguridad/validacion-global';
import { PagoController } from './pago.controller';
import { PagoService } from './pago.service';
import { TransaccionController } from './transaccion.controller';
import { TransaccionService } from './transaccion.service';

/**
 * Módulo del servicio pagos: un controlador y un servicio por entidad. Los controles
 * transversales se registran aquí, no en main.ts, para que viajen con el módulo (también en las
 * pruebas): token de Keycloak en todas las rutas, validación en lista blanca y errores sin
 * detalles internos.
 */
@Module({
  controllers: [PagoController, TransaccionController],
  providers: [
    PrismaService,
    PagoService,
    TransaccionService,
    { provide: APP_GUARD, useClass: JwtAuthGuard },
    { provide: APP_PIPE, useFactory: crearValidacionGlobal },
    { provide: APP_FILTER, useClass: FiltroErrores },
  ],
})
export class PagosModule {}
