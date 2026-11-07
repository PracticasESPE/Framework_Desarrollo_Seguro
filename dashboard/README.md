# Dashboard del framework

Interfaz web del framework de desarrollo seguro, hecha con React + Vite (plan técnico, 4.3). Se
compila a archivos estáticos que sirve la propia API del motor (`orchestrator/api.py`), así que no
necesita servidor propio ni CORS. No forma parte de lo que genera el framework.

## Versión 0 (sprint 3, #49)

- **Carga del documento de requisitos.** Se arrastra el archivo o se elige, y la API lo guarda en
  `salida/documentos/` con un nombre generado por el servidor. El dashboard muestra su nombre,
  formato, tamaño, SHA-256 e identificador.
- **Documentos cargados.** Lista de lo subido, del más reciente al más antiguo.
- **Fases del pipeline.** Las 11 fases que publica el motor en `/fases`, con los gates resaltados.
  El progreso en tiempo real con Server-Sent Events llega en #51.
- **Estado del motor.** Versión de la API, o aviso si no está levantada.

## Uso

Con la API del motor sirviendo el dashboard compilado:

```bash
cd dashboard
npm ci                # .npmrc desactiva los scripts de instalación
npm run build         # genera dashboard/dist
cd ..
uv run framework api  # http://127.0.0.1:8000
```

En desarrollo, con recarga automática: `uv run framework api` en una terminal y `npm run dev` en
otra (http://127.0.0.1:5173). Vite reenvía a la API las rutas `/salud`, `/fases`, `/configuracion`
y `/documentos`.

| Comando | Qué hace |
|---|---|
| `npm run lint` | ESLint con `eslint-plugin-security`, reglas con tipos y hooks de React |
| `npm test` | Pruebas con Vitest y Testing Library |
| `npm run build` | Comprueba los tipos (`tsc -b`) y compila con Vite |

## Seguridad de la carga

El documento es la entrada menos confiable del framework. El dashboard avisa antes de subir, pero
quien decide es la API (`orchestrator/documentos.py`):

| Riesgo | Control |
|---|---|
| Archivo peligroso con otra extensión (CWE-434) | Lista permitida (PDF, DOCX, TXT y MD) y comprobación del contenido: cabecera `%PDF-`, estructura del DOCX o texto UTF-8 sin bytes nulos |
| Recorrido de rutas (CWE-22) | El nombre guardado lo genera el servidor; el original solo se muestra |
| Archivo enorme (CWE-400) | Máximo 10 MB, cortando la lectura del cuerpo al superarlo |
| DOCX que se descomprime en gigas (CWE-409) | Límite de entradas y de tamaño descomprimido |
| Inyección de contenido en la página | Cabeceras CSP `default-src 'self'`, `nosniff` y `frame-ancestors 'none'` |

El archivo viaja como cuerpo binario (`application/octet-stream`) y no como formulario
`multipart`. Así no hace falta otra dependencia para interpretar formularios, y el tamaño se
controla mientras llega el cuerpo.

La API escucha solo en `127.0.0.1` porque aún no tiene autenticación.

## Por qué no está en el Gate 1

El Gate 1 analiza el código que genera el framework. Sus SARIF alimentan la decisión de OPA y las
métricas de cada ejecución, y mezclar ahí el dashboard falsearía esas métricas. Por eso el workflow
tiene un job propio, `dashboard`, que aplica las mismas herramientas: `npm ci --ignore-scripts`,
ESLint con `eslint-plugin-security`, `tsc`, pruebas y Semgrep. Trivy fs y Gitleaks del Gate 1 ya
revisan `dashboard/package-lock.json` y el historial.
