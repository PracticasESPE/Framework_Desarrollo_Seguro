# Sprint 4: compilación de los servicios generados (24/11)

Verificación del código generado desde `arquitectura.json` del documento 1: instalación de
dependencias, generación del cliente de Prisma y compilación con `tsc --noEmit`.

| Servicio | npm ci | prisma generate | tsc --noEmit |
|---|---|---|---|
| auditoria | 0 | 0 | 0 (sin errores) |
| catalogo | 0 | 0 | 0 (sin errores) |
| notificaciones | 0 | 0 | 0 (sin errores) |
| pagos | 0 | 0 | 0 (sin errores) |
| pedidos | 0 | 0 | 0 (sin errores) |

Comandos por servicio (dentro de `services/<servicio>`):

```powershell
npm ci --ignore-scripts --no-audit --no-fund
$env:DATABASE_URL="postgresql://compilacion:compilacion@localhost:5432/compilacion"; npx prisma generate
npx tsc --noEmit
```

`DATABASE_URL` solo hace falta para que Prisma lea su configuración: no se conecta a ninguna base de
datos. No se escribió ningún `.env`.

El ciclo de reintento con el LLM para la lógica de negocio está en `orchestrator/generation/logica.py`
(hasta 3 intentos, verificados con `tsc --noEmit`). Esta comprobación no usa el LLM.

El Gate 1 sobre los servicios generados lo ejecutó Abner en #222.
