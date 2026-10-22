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

## Reglas en "warn" que volverán a "error"

Todas las reglas OWASP conservan su severidad original salvo estas dos, que dependen de piezas
que el plan programa más adelante:

| Regla | Vuelve a "error" cuando |
|---|---|
| `owasp:api2:2023-write-restricted` | exista el guard JWT de Keycloak en el servicio (23/10) |
| `owasp:api4:2023-rate-limit` | Traefik limite la tasa de peticiones (sprint 5, 01/12) |

Los avisos de 401, 429 y 500 sin documentar (`define-error-responses-*`, `rate-limit-responses-429`)
y `read-restricted` se resolverán con esas mismas piezas.

## Probar en local

```powershell
npm ci --ignore-scripts --prefix spectral
cd services\usuarios; npm run build; cd ..\..
node services\usuarios\dist\openapi\generar-openapi.js "$PWD\salida\openapi\usuarios.json"
spectral\node_modules\.bin\spectral lint salida\openapi\usuarios.json --ruleset spectral\.spectral.yaml
```

O el Gate completo, en Git Bash o en Linux: `bash scripts/gate2.sh`.
