# Sprint 2: demostración del walking skeleton completo

Hito del plan técnico (30 de octubre de 2026): *walking skeleton completo (tres gates) con avisos
en Telegram. Primer hito importante del proyecto.* No se empieza el sprint 3 sin haberlo cumplido.

## Qué se demuestra

```
Servicio de referencia   Fase 4: Gate 1          Fase 8: Gate 2         Fase 11: Gate 3
services/usuarios  ──►  tsc, ESLint, Semgrep, ─► Spectral y Conftest ─► Trivy image, Syft,
                        Gitleaks, Trivy,                                ZAP y Nuclei
                        Hadolint
                              │                       │                       │
                              ▼                       ▼                       ▼
                        OPA decide ──────────── OPA decide ──────────── OPA decide
                              │                       │                       │
                              └───────────────────────┼───────────────────────┘
                                                      ▼
                        Neo4j: Ejecucion ─TIENE_RESULTADO─► ResultadoGate ─BASADA_EN─► Regla
                        Telegram: un mensaje de progreso por ejecución y un aviso final
```

Tres cosas tienen que verse: los tres gates pasan sobre el servicio de referencia, un gate
rechazado detiene los siguientes y Telegram cuenta lo que ocurrió en cada caso.

## Escenario 1: cadena completa en verde

Dura unos 11 minutos. Con el chat de Telegram abierto:

1. Lanzar el pipeline con un pull request hacia `dev` o, en la última ejecución de `dev`, con
   **Re-run all jobs**. El botón **Run workflow** no aparece: GitHub lo muestra solo si el workflow
   existe en la rama por defecto, y `main` todavía no tiene `framework.yml`.
2. En Telegram, mostrar cómo un único mensaje se edita al avanzar cada fase:

   ```
   Pipeline PracticasESPE/Framework_Desarrollo_Seguro · rama dev · ejecución #N
   ⏭️ Fase 1: Requisitos
   ⏭️ Fase 2: Arquitectura
   ✅ Fase 3: Generación
   ✅ Fase 4: Security Gate 1
   ⏭️ Fases 5-6: Refinamiento
   ⏭️ Fase 7: Integración
   ✅ Fase 8: Security Gate 2
   ✅ Fase 9: Pruebas
   ✅ Fase 10: Contenedores
   ✅ Fase 11: DAST y Security Gate 3
   ```

   Las fases con ⏭️ aún no existen: se construyen en los sprints 3 y 5.
3. Al terminar llega un mensaje nuevo, para que Telegram notifique el resultado:

   ```
   ✅ Pipeline terminado correctamente
   ✅ Gate 1 · ✅ Gate 2 · ✅ Gate 3
   ```

4. En **Actions**, abrir la ejecución y mostrar los pasos **Decisión OPA: Gate 1, 2 y 3** y
   **Decisiones de los gates en Neo4j**, que lista las tres decisiones con sus criterios.
5. En **Summary**, mostrar la tabla **Cadena de Security Gates** y el detalle de cada decisión.
6. En la pestaña **Security**, mostrar los resultados publicados por herramienta.

## Escenario 2: un gate rechazado detiene la cadena

Se introduce a propósito un fallo que solo ve el Gate 2. Dura unos 3 minutos y **no se fusiona**.

```bash
git checkout -b feature/demo-gate2-rechazado
# En docker-compose.dev.yml, servicio neo4j, debajo de "restart: unless-stopped":
#     privileged: true
git commit -am "demo: Gate 2 rechazado (no fusionar)"
git push -u origin feature/demo-gate2-rechazado
gh pr create --draft --base dev --title "demo: Gate 2 rechazado (no fusionar)" \
  --body "Solo para la demostración del sprint 2. No fusionar."
```

Resultado esperado en Telegram:

```
❌ Pipeline detenido en Fase 8: Security Gate 2
✅ Gate 1 · ❌ Gate 2 · 🚫 Gate 3
```

En **Actions**, las fases 9, 10 y 11 quedan omitidas. **Decisión OPA: Gate 2** falla con:

```
Gate 2: RECHAZADO
  Gate 2 rechazado: incumple 1 de 5 criterios (gate2.politica_compose)
  Bloqueante gate2.politica_compose: La configuración de despliegue incumple una política:
  [neo4j] privileged: true da al contenedor acceso casi total al host
```

Al terminar, se cierra el pull request y se borra la rama:

```bash
gh pr close feature/demo-gate2-rechazado --delete-branch
```

## Caso real: una CVE detenida por el Gate 1

El Gate 1 ya detuvo la cadena de verdad. En la ejecución
[41316955153](https://github.com/PracticasESPE/Framework_Desarrollo_Seguro/actions/runs/41316955153)
(`dev`, 01/11/2026), Trivy encontró cuatro vulnerabilidades HIGH en `pyasn1` 0.6.4
(CVE-2026-119194 a CVE-2026-119197). El Gate 1 quedó rechazado, los Gates 2 y 3 no se ejecutaron y
el pull request #175 actualizó `pyasn1` a 0.6.5. El aviso de esa ejecución sigue en el chat.

## Demostración local

Muestra las decisiones de OPA y su registro en el grafo sin ejecutar las herramientas, con los
resultados de ejemplo de `tests/datos/gates/`. Requiere Docker Desktop en marcha, `uv`, OPA
(`winget install open-policy-agent.opa`) y `NEO4J_PASSWORD` en el `.env`.

```bash
docker compose -f docker-compose.dev.yml up -d neo4j
uv run framework grafo esquema
uv run framework gates decidir --gate 1 --salida tests/datos/gates --compilacion-ok --no-bloquear --grafo
uv run framework gates decidir --gate 2 --salida tests/datos/gates --no-bloquear --grafo
uv run framework gates decidir --gate 3 --salida tests/datos/gates --no-bloquear --grafo
uv run framework gates listar
```

Los Gates 1 y 3 salen rechazados y el Gate 2 aprobado, como se describe en
`tests/datos/gates/README.md`.

> En Windows, si la ruta del repositorio tiene tildes (`Prácticas`), `uv run framework` falla con
> `ModuleNotFoundError: No module named 'orchestrator'`. Se evita con
> `uv run python -m orchestrator.cli`, que admite los mismos comandos. En CI no ocurre.

Después, en Neo4j Browser (`http://localhost:7474`):

```cypher
MATCH p = (:Ejecucion)-[:TIENE_RESULTADO]->(:ResultadoGate)-[:BASADA_EN]->(:Regla)
OPTIONAL MATCH q = (:ResultadoGate)-[:BLOQUEADO_POR]->(:Hallazgo)
RETURN p, q
```

## Evidencias

Van en `docs/sprints/sprint2/capturas/`. Si se graba un video, se comparte por enlace y no se sube
al repositorio. Ninguna captura debe mostrar tokens ni el valor de un secreto.

| Archivo | Qué muestra | Dónde |
|---|---|---|
| `01-telegram-progreso.png` | Mensaje de progreso con fases en curso | Telegram, escenario 1 |
| `02-telegram-fin.png` | Aviso final con los tres gates en verde | Telegram, escenario 1 |
| `03-actions-pasos.png` | Pasos del pipeline en verde, con las decisiones de OPA | Actions, escenario 1 |
| `04-actions-resumen.png` | Tabla "Cadena de Security Gates" y decisiones | Summary, escenario 1 |
| `05-actions-neo4j.png` | Paso "Decisiones de los gates en Neo4j" con las 3 decisiones | Actions, escenario 1 |
| `06-security.png` | Resultados por herramienta y alertas abiertas | Pestaña Security |
| `07-telegram-rechazo.png` | Aviso "Pipeline detenido en Fase 8" | Telegram, escenario 2 |
| `08-actions-rechazo.png` | Fases 9 a 11 omitidas y decisión OPA rechazada | Actions, escenario 2 |
| `09-telegram-cve.png` | Aviso real de la CVE de `pyasn1` del 01/11 | Telegram, caso real |

## Resultado al cierre del sprint

Datos de la ejecución
[41341510212](https://github.com/PracticasESPE/Framework_Desarrollo_Seguro/actions/runs/41341510212)
(`dev`, 01/11/2026, commit `78c0a37`), la primera con las decisiones de OPA integradas.

| Elemento | Estado |
|---|---|
| Gate 1 | 8 de 8 comprobaciones correctas. OPA aprueba, 4 de 4 criterios, 0 hallazgos |
| Gate 2 | Spectral y Conftest correctos. OPA aprueba, 5 de 5 criterios, 21 advertencias que no bloquean |
| Gate 3 | Trivy image: 0 HIGH o CRITICAL. ZAP: 0 altos, 0 medios, 4 bajos. Nuclei: 0. OPA aprueba, 5 de 5 criterios |
| SBOM | CycloneDX 1.7 con 1866 componentes |
| Trazabilidad | 3 nodos `ResultadoGate` en la ejecución `ej-20261101-192629-a1080e` |
| Políticas OPA | 64 de 64 pruebas, con `opa check --strict` |
| Pruebas del motor | 239 correctas, 8 omitidas, 88 % de cobertura de `orchestrator/` |
| Pruebas del servicio | 42 pruebas Jest correctas |
| Reglas Semgrep propias | 8 de 8 reglas detectan sus casos de prueba |
| Duración del pipeline | 10 min 52 s de los 30 min de límite (Gate 3: 5 min 20 s) |
| Alertas abiertas en GitHub Security | 0 |

El pipeline con las decisiones de OPA quedó en verde el 01/11, dos días después de la fecha del
hito. El retraso se absorbió en los días sin actividad previos al sprint 3, que empieza el 04/11.

### Corrección hecha durante la revisión

Las decisiones de OPA se añadieron en pasos propios, fuera del notificador. Si un script aprobaba y
OPA rechazaba (por ejemplo, porque faltaba el SARIF de una herramienta), la cadena se detenía, pero
Telegram y el resumen seguían mostrando el gate como aprobado. Ahora esos pasos usan la orden
`decision` del notificador y un rechazo de OPA marca el gate como rechazado. Una aprobación de OPA
no cambia la fase, para que no pueda dejar en verde un gate que su script ya rechazó.

## Pendiente para el sprint 3

Los pendientes de este sprint, con su responsable y su fecha, están en
[sprint3-planificacion.md](sprint3-planificacion.md).
