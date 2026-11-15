# Sprint 3: demostración de las fases 1 y 2

Objetivo del sprint (plan técnico, cronograma 13.2): *del documento de requisitos al modelo
estructurado, la arquitectura validada por OPA, los ADR y el diagrama C4.* El sprint no tiene hito
propio; prepara la entrada del hito del 27 de noviembre (fases 1 a 4).

## Qué se demuestra

```
Documento del cliente (PDF, DOCX, TXT o MD)
   │  FASE 1 (dashboard o API): Docling → normalización → clasificación con el LLM
   ▼
modelo_requisitos.json ──► Neo4j: Ejecucion ─TIENE_REQUISITO─► Requisito
   │  FASE 2 (CLI): el LLM propone ──► OPA valida ──► si rechaza, el LLM corrige (3 intentos)
   ▼
arquitectura.json ──► Neo4j: Decision ─BASADA_EN─► Regla · Requisito ─ORIGINA─► Decision
   ├──► docs/adr/*.md          (ADR: la decisión, su porqué y sus controles)
   └──► docs/arquitectura.md   (diagrama C4 en Mermaid)
```

La idea que tiene que quedar: **el LLM propone, las reglas deciden.** El LLM lee y propone, OPA
comprueba con reglas fijas, y todo queda justificado y enlazado en el grafo.

## Preparación (una vez)

Docker Desktop abierto, OPA instalado (`winget install open-policy-agent.opa`) y, en PowerShell,
desde la carpeta del proyecto:

```powershell
git checkout dev; git pull
python -m uv sync
cd dashboard; npm ci; npm run build; cd ..
docker compose -f docker-compose.dev.yml up -d neo4j
python -m uv run python -m orchestrator.cli grafo esquema   # solo la primera vez en un PC
python -m uv run python -m orchestrator.cli llm probar      # Groq y el respaldo deben responder
```

Conviene hacer un ensayo completo antes: la caché del LLM guarda las respuestas y en la
demostración la fase 1 sale en segundos y sin gastar cuota.

## Levantar

| Terminal | Comando |
|---|---|
| 1 | `python -m uv run python -m orchestrator.cli api` (dashboard en http://127.0.0.1:8000) |
| 2 | CLI para la fase 2 |

En Windows, si la ruta del proyecto tiene tildes, `uv run framework` no arranca: se usa
`python -m orchestrator.cli` como arriba.

## Escenario 1: fase 1 en el dashboard

1. Subir `evaluation\datasets\01_tienda_en_linea\requisitos.docx`. La API valida el formato, el
   tamaño y que el contenido corresponda a la extensión, y lo guarda con un nombre generado por el
   servidor.
2. **Procesar documento.** Mostrar el progreso en tiempo real (Server-Sent Events): la fase 1 «En
   curso» en «Fases del pipeline» y el registro de eventos («Extrayendo…», «Clasificando…»).
   Opcional: recargar a mitad (se retoma) o cancelar.
3. Al terminar, en el registro: «Uso del LLM» (llamadas, caché y tokens) y «Requisitos
   registrados en Neo4j: N (ejecución ej-…)», automático.
4. En «Requisitos identificados»: RF/RNF, etiquetas de seguridad y la tabla de requisitos.
5. En Neo4j Browser (http://localhost:7474), la última ejecución:

   ```cypher
   MATCH (e:Ejecucion) WHERE (e)-[:TIENE_REQUISITO]->()
   WITH e ORDER BY e.fecha DESC LIMIT 1
   MATCH (e)-[:TIENE_REQUISITO]->(r:Requisito)
   RETURN e, r
   ```

   Sin filtrar por ejecución, la consulta mezcla los requisitos de todas las ejecuciones guardadas.

## Escenario 2: fase 2, ciclo LLM ↔ OPA

Con el id del documento (el «Identificador» del dashboard):

```powershell
$ID = "<id del documento>"
python -m uv run python -m orchestrator.cli arquitectura proponer "salida\requisitos\$ID.modelo_requisitos.json"
```

El comando muestra cada intento. Qué revisa OPA:

| Regla | Exige | Si falla |
|---|---|---|
| `arquitectura.base_datos_propia` | Cada servicio con su propia base de datos | Rechaza |
| `arquitectura.sin_ciclos` | Sin ciclos de **llamadas síncronas** (A espera a B y B espera a A) | Rechaza |
| `arquitectura.dependencias_conocidas` | Cada dependencia apunta a un servicio de la propuesta | Rechaza |
| `arquitectura.servicios_unicos` | Sin nombres repetidos | Rechaza |
| Ciclo solo de eventos | Servicios que se escuchan por eventos (una saga coreografiada) | Avisa, no bloquea |

Si OPA rechaza, el comando vuelve a pedir la propuesta con los motivos y lo registra en
`salida\arquitectura\$ID.intentos.json`. Las decisiones aprobadas quedan en Neo4j:

```cypher
MATCH p = (:Ejecucion {id: "<ejecucion>"})-[:TIENE_DECISION]->(d:Decision)
OPTIONAL MATCH q = (d)-[:BASADA_EN|APLICA]->()
RETURN p, q
```

## Escenario 3: ADR y diagrama C4

```powershell
$A = "salida\arquitectura\$ID.arquitectura.json"; $M = "salida\requisitos\$ID.modelo_requisitos.json"
python -m uv run python -m orchestrator.cli arquitectura adr $A --requisitos $M --destino salida\adr-demo
python -m uv run python -m orchestrator.cli arquitectura diagrama $A --requisitos $M --salida salida\adr-demo\arquitectura.md --adr salida\adr-demo --nombre "Tienda en línea"
```

Usar siempre `--destino` y `--salida` en la demostración: sin ellos se escriben `docs/adr/` y
`docs/arquitectura.md`, que son la evidencia del repositorio.

Después, en GitHub, `docs/adr/README.md`, un ADR (por ejemplo
`0008-aplicar-el-patron-api-gateway.md`) y `docs/arquitectura.md`. La cadena que conviene
recorrer: el requisito RF-02 (bloquear la cuenta tras cinco intentos) lleva a la decisión API
Gateway, que OPA valida y que aplica el control ASVS V1.4.1, que mitiga CWE-306. El LLM solo
redactó el texto: los hechos salen de datos validados.

## Si algo falla

| Situación | Qué hacer |
|---|---|
| Groq sin cuota | Nada: la sección pasa a Gemini (`LLM_RESPALDO=gemini`) y el registro lo muestra |
| Neo4j apagado | La fase 1 termina igual y avisa; registrar después con `requisitos registrar` |
| OPA no aprueba en 3 intentos | Mostrar los motivos y usar la arquitectura aprobada de `docs/adr/entrada/` |
| El dashboard no muestra el registro en Neo4j | Volver a compilarlo (`npm run build`) y reiniciar la API |

## Apagar

`Ctrl + C` en la terminal de la API y `docker compose -f docker-compose.dev.yml down` (sin `-v`,
que borraría los datos de Neo4j).
