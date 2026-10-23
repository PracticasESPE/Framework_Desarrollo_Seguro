# Gate 2 (inicial): contrato OpenAPI con Spectral

El Security Gate 2 revisa el **contrato OpenAPI** del servicio, que se genera desde el código
(`services/usuarios/src/openapi/`), con reglas alineadas con el OWASP API Security Top 10 (2023).
Lo ejecuta `scripts/gate2.sh` en la fase 8 del workflow y publica `spectral.sarif` en la
pestaña Security.

| Archivo | Qué contiene |
|---|---|
| `.spectral.yaml` | Conjuntos `spectral:oas` y `@stoplight/spectral-owasp-ruleset`, más las reglas propias |
| `reglas-propias.yaml` | 4 reglas del framework (ver abajo) |
| `pruebas/malo.json`, `pruebas/bueno.json` | Ejemplos que el Gate usa en cada ejecución para comprobar que las reglas propias siguen detectando lo que deben |
| `convertir-a-sarif.mjs` | Convierte la salida JSON de Spectral a SARIF 2.1.0 |
| `package.json`, `package-lock.json` | Versiones fijadas de Spectral (solo se usan en CI) |

## Reglas propias

| Regla | Severidad | Qué exige |
|---|---|---|
| `fw-ruta-con-prefijo-api` | error | Todas las rutas empiezan por `/api/` (OWASP API9) |
| `fw-sin-secretos-en-query` | error | Ningún parámetro de consulta se llama `password`, `token`, `api_key`… (ASVS V13.1.3) |
| `fw-respuesta-sin-campos-sensibles` | error | Los esquemas de respuesta no exponen contraseñas, hashes ni secretos (OWASP API3) |
| `fw-version-semantica` | warn | `info.version` con formato `1.0.0` (OWASP API9) |

## Severidades ajustadas

Todas las reglas OWASP conservan su severidad original salvo estas:

| Regla | Severidad | Motivo |
|---|---|---|
| `owasp:api2:2023-read-restricted` | warn → **error** | Desde el 23/10 todas las operaciones exigen el token de Keycloak (guard JWT) |
| `owasp:api8:2023-define-error-responses-401` | warn → **error** | El contrato documenta el 401 de todas las operaciones |
| `owasp:api4:2023-rate-limit` | error → warn | Volverá a "error" cuando Traefik limite la tasa de peticiones (sprint 5, 01/12) |

`owasp:api2:2023-write-restricted` volvió a su valor original ("error") con el guard JWT.
Siguen como avisos `rate-limit-responses-429` y `define-error-responses-500`, que se resolverán
con la limitación de tasa y el filtro global de errores.

## Probar en local

```powershell
npm ci --ignore-scripts --prefix spectral
cd services\usuarios; npm run build; cd ..\..
node services\usuarios\dist\openapi\generar-openapi.js "$PWD\salida\openapi\usuarios.json"
spectral\node_modules\.bin\spectral lint salida\openapi\usuarios.json --ruleset spectral\.spectral.yaml
```

O el Gate completo, en Git Bash o en Linux: `bash scripts/gate2.sh`.
