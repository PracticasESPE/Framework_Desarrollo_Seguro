import { Module } from '@nestjs/common';
import { APP_FILTER, APP_GUARD, APP_PIPE } from '@nestjs/core';
import { PrismaService } from './prisma.service';
import { FiltroErrores } from './seguridad/filtro-errores';
import { JwtAuthGuard } from './seguridad/jwt-auth.guard';
import { crearValidacionGlobal } from './seguridad/validacion-global';
import { AuditoriaLogController } from './auditoria-log.controller';
import { AuditoriaLogService } from './auditoria-log.service';
import { VentaReporteController } from './venta-reporte.controller';
import { VentaReporteService } from './venta-reporte.service';

/**
 * Módulo del servicio auditoria: un controlador y un servicio por entidad. Los controles
 * transversales se registran aquí, no en main.ts, para que viajen con el módulo (también en las
 * pruebas): token de Keycloak en todas las rutas, validación en lista blanca y errores sin
 * detalles internos.
 */
@Module({
  controllers: [AuditoriaLogController, VentaReporteController],
  providers: [
    PrismaService,
    AuditoriaLogService,
    VentaReporteService,
    { provide: APP_GUARD, useClass: JwtAuthGuard },
    { provide: APP_PIPE, useFactory: crearValidacionGlobal },
    { provide: APP_FILTER, useClass: FiltroErrores },
  ],
})
export class AuditoriaModule {}
