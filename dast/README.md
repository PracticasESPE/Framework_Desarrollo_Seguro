# Análisis dinámico (DAST) del Gate 3

El DAST ataca el servicio **en marcha**, a diferencia de los Gates 1 y 2, que revisan archivos. Lo
ejecuta `scripts/gate3.sh` en la fase 11 del workflow.

## Cómo funciona

1. `docker-compose.dast.yml` levanta un entorno desechable: el servicio, su PostgreSQL y Keycloak.
   No publica ningún puerto: las herramientas entran por la red privada `framework-dast`. Las
   contraseñas se generan en cada ejecución y el entorno se destruye al terminar.
2. El script pide un token a Keycloak y **exige un 200** del servicio antes de escanear. Todas las
   rutas requieren token: sin él, las herramientas solo verían 401 y el reporte saldría "limpio"
   sin haber probado nada. Si la autenticación falla, el Gate da error.
3. **OWASP ZAP** importa el contrato OpenAPI y ataca cada operación con el token.
4. **Nuclei** aplica sus plantillas de CVE conocidas, configuraciones erróneas y paneles expuestos.

## Cuándo bloquea

| Herramienta | Bloquea cuando |
|---|---|
| ZAP | Hay una alerta de riesgo alto, o el servicio responde 500 ante un ataque (regla 100000) |
| Nuclei | Hay una coincidencia de severidad alta o crítica |

Los riesgos medios y bajos no bloquean: quedan en el reporte.

Un escaneo incompleto nunca cuenta como limpio. Por defecto, tras 30 errores Nuclei abandona el
objetivo y aun así termina con "0 matches"; por eso se ejecuta con `-nmhe`, y si abandona el objetivo
de todos modos, el Gate da error.

## Reglas de ZAP (`zap-reglas.conf`)

Sin este archivo, `zap-api-scan.py` usa la política `API-Minimal`: 23 reglas en unos 5 segundos. Al
pasarlo con `-c`, usa la política completa, que tarda algo más de un minuto en este servicio. Fue la
que encontró un error 500 real: un byte nulo en `nombre` llegaba a PostgreSQL y hacía fallar la
petición (corregido en `CrearUsuarioDto`).

El archivo solo excluye reglas que no aplican a una API REST con JSON (SOAP, WSDL y JSF).

## Límite de tiempo

El escaneo activo de ZAP se limita a 4 minutos porque el token de Keycloak vive 5: más tiempo y las
últimas peticiones recibirían 401. Además, cada regla tiene 1 minuto como máximo. ZAP y Nuclei tienen
un tope total de 8 y 6 minutos.

## Conversión a SARIF (`zap-a-sarif.mjs`)

ZAP no genera SARIF, el formato común de los resultados (principio P2). El conversor toma `zap.json`
y escribe `salida/security/sarif/zap.sarif`, que se publica en GitHub Security y que lee el motor
(`orchestrator/gates/sarif.py`).

| En ZAP | En SARIF |
|---|---|
| Riesgo alto, medio, bajo | `error` 8.0, `warning` 5.0, `note` 2.0 (`security-severity`) |
| Regla `FAIL` en `zap-reglas.conf` | Alta (8.0), aunque ZAP le dé riesgo bajo: OPA solo bloquea alta o crítica |
| Riesgo informativo | No se publica: sigue en `zap.html` y `zap.json` |
| Confianza 0 (falso positivo) | Resultado con `suppressions`: queda constancia, pero no cuenta |
| `cweid` | Etiqueta `external/cwe/cwe-N`; el valor `-1` (desconocida) se omite |
| Cada instancia | Un resultado por regla, método, ruta y parámetro |

- **Informativas:** el escaneo real generó 102 resultados de este tipo, casi todos respuestas 404
  correctas ante rutas de prueba como `/.env`. No son fallos y tapaban los 7 hallazgos reales.
- **Ubicación:** un hallazgo DAST no está en un archivo. Se usa la ruta de la API (`api/usuarios`) con
  la línea 1, porque GitHub exige una línea. El detalle real va en el mensaje.
- **Huella:** se calcula con la regla, el método, la ruta y el parámetro, sin el host, el ataque ni la
  evidencia. Así el mismo hallazgo se reconoce entre ejecuciones y entornos.
- **Secretos:** de la evidencia se ocultan los tokens `Bearer` y los JWT. El texto del ataque no se
  publica.

Si la conversión falla, el Gate da error de herramienta. Las pruebas del conversor se ejecutan al
inicio del Gate 3:

```bash
node --test dast/zap-a-sarif.test.mjs
```

## Reportes

Quedan en `salida/dast/` y en el artefacto `sarif-gate1` de cada ejecución:

| Archivo | Contenido |
|---|---|
| `zap.html` | Reporte de ZAP para leer en el navegador |
| `zap.json` | Reporte de ZAP en bruto; de aquí sale `security/sarif/zap.sarif` |
| `nuclei.log` | Ejecución de Nuclei: plantillas, peticiones y resultado |
| `nuclei.jsonl` | Coincidencias de Nuclei (vacío si no hay) |
| `nuclei.sarif` | Se publica en GitHub Security; Nuclei solo lo crea si hay coincidencias |

## Probar en local

Con Docker abierto, en Linux o WSL, y con el servicio compilado y su contrato ya generados:

```bash
docker build -t fw-usuarios:ci services/usuarios
bash scripts/gate3.sh
```
