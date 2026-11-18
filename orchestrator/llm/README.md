# Proveedores de LLM

Las fases del motor solo conocen `ProveedorLLM.generar_estructurado`: piden una respuesta que
cumpla un esquema Pydantic y nunca llaman a un SDK. Detrás de esa interfaz, `crear_proveedor`
monta lo que indique `.env`:

```
LLM_PROVIDER ──► caché ─┐
LLM_RESPALDO ──► caché ─┴─► cadena de respaldo (solo si LLM_RESPALDO tiene algo)
```

| Archivo | Qué hace |
|---|---|
| `base.py` | Interfaz, reintentos si la salida no cumple el esquema, errores y conteo de tokens |
| `groq.py`, `gemini.py`, `claude.py`, `ollama.py` | Un adaptador por proveedor |
| `cache.py` | Caché en disco de las respuestas |
| `cadena.py` | Respaldo entre proveedores |
| `fabrica.py` | Monta todo según `.env` y resume el uso |

## Cuota del plan gratuito de Groq

Límites por organización con `openai/gpt-oss-20b`. Varias claves de la misma cuenta comparten la
cuota, y crear varias cuentas para sumar cuota va contra la política de uso de Groq.

| Límite | Valor |
|---|---|
| Peticiones | 30 por minuto, 1000 por día |
| Tokens | 8000 por minuto, 200 000 por día |

Medido con el documento 1 del dataset (DOCX, 11 secciones), el 10/11/2026:

| Configuración | Tokens | Tiempo | Tipo correcto | F1 de etiquetas |
|---|---|---|---|---|
| Esfuerzo por defecto | 27 743 (15 271 de entrada y 12 472 de salida) | 160 s | 90 % | 0,76 |
| `LLM_ESFUERZO_RAZONAMIENTO=low` | 18 997 (14 821 y 4176) | 113 s | 87 % | 0,65 |
| Repetición con caché | 0 | 25 s (solo Docling) | Igual | Igual |

Con el esfuerzo por defecto, la cuota diaria da para unos 7 documentos. Los 8000 tokens por
minuto explican buena parte de los casi 3 minutos que tarda un documento. Es una sola medición, y
el LLM no responde siempre igual.

## Groq frente a Gemini (los 3 documentos del dataset, en DOCX, 10/11/2026)

Groq con `openai/gpt-oss-20b` y Gemini con `gemini-3.5-flash-lite`. Ambos usaron el esfuerzo por
defecto y la caché vacía. El tiempo incluye unos 20 s de arranque de Docling.

| Documento | Proveedor | Tokens | Tiempo | Encontrados | Tipo correcto | F1 de etiquetas |
|---|---|---|---|---|---|---|
| 1 Tienda | Groq | 27 743 | 160 s | 30/30 | 90 % | 0,76 |
| | Gemini | 12 570 | 24 s | 30/30 | 87 % | 0,67 |
| 2 Gestión académica | Groq | 34 146 | 187 s | 38/38 | 92 % | 0,67 |
| | Gemini | 15 958 | 30 s | 38/38 | 92 % | 0,67 |
| 3 Citas médicas | Groq | 34 278 | 242 s | 43/43 | 86 % | 0,58 |
| | Gemini | 16 483 | 88 s* | 43/43 | 77 % | 0,64 |
| **Total** | **Groq** | **96 167** | **589 s** | **111/111** | **89 %** | **0,67** |
| | **Gemini** | **45 011** | **142 s** | **111/111** | **85 %** | **0,66** |

\* Gemini llegó a su límite por minuto y el motor esperó los 37 s que pidió.

Los dos encuentran todos los requisitos y etiquetan con calidad parecida. Groq acierta algo más en
funcional o no funcional. Gemini gasta la mitad de tokens y tarda unas 4 veces menos, así que
encaja como respaldo.

Para que Gemini funcionara hubo que corregir dos cosas:
- El adaptador usa `response_json_schema` (JSON Schema estándar) sin `maxItems`. Con
  `response_schema` rechazaba el esquema de la clasificación.
- La clasificación decodifica las entidades HTML de la ubicación, porque Gemini devolvía
  «p&aacute;rrafo».

## Cómo se gestiona la cuota

1. **Caché (`LLM_CACHE=true`, por defecto).** La misma pregunta al mismo modelo se responde desde
   `.cache/llm/`. La clave incluye proveedor, modelo, ajustes, instrucciones, esquema y prompt, y
   ignora el código aleatorio de las marcas de la clasificación. `framework llm vaciar-cache` la
   borra.
2. **Límite de uso (HTTP 429).** Los adaptadores lanzan `ErrorLimiteLLM` con la espera que pide el
   proveedor (`retry-after`) y si la cuota agotada es la del día.
   - La clasificación espera ese tiempo y reintenta la sección, como mucho 2 veces y solo si la
     espera no pasa de 120 s.
   - Si la cuota agotada es la del día, se detiene enseguida con un mensaje claro: «groq: cuota
     diaria agotada; se renueva en 7 min».
   - En el dashboard, la espera se ve en el progreso y se corta si se cancela la ejecución.
3. **Respaldo (`LLM_RESPALDO`).** Si el principal llega a su límite o falla por red, servidor o
   clave, la sección pasa al siguiente proveedor, y el principal queda apartado el tiempo que pidió.
   - Si la respuesta no cumple el esquema, no cambia de proveedor: eso es un problema del prompt.
   - Cada proveedor tiene su propia caché.
   - El cambio de proveedor se ve en el progreso del dashboard y en la CLI.
4. **Esfuerzo de razonamiento (`LLM_ESFUERZO_RAZONAMIENTO`).** Gasta menos tokens, pero bajó la
   calidad de las etiquetas (tabla anterior). Úsalo solo si falta cuota.

## Respaldo recomendado

| Proveedor | Coste | Cómo activarlo |
|---|---|---|
| Gemini | Plan gratuito, con límites por proyecto. Probado: ver la tabla anterior | Crear una clave en Google AI Studio y ponerla en `GEMINI_API_KEY` |
| Ollama | Gratis, local, sin cuota; más lento | Instalar Ollama, descargar `ollama pull llama3.1` y dejar `OLLAMA_HOST` |

Por ejemplo: `LLM_RESPALDO=gemini,ollama`.

**Evaluación de la tesis.** Mezclar modelos cambia los resultados. Las corridas de evaluación se
hacen con un solo proveedor y sin respaldo (`LLM_RESPALDO=` vacío). La comparación de modelos
(`evaluation/comparacion_llm`) ya desactiva la caché y el respaldo.

## Comandos

```powershell
python -m uv run python -m orchestrator.cli llm estado        # principal, respaldo, claves definidas y caché
python -m uv run python -m orchestrator.cli llm probar        # petición mínima a cada proveedor, sin caché
python -m uv run python -m orchestrator.cli llm vaciar-cache  # borra las respuestas guardadas
```

`requisitos clasificar` y el progreso del dashboard muestran el uso de cada documento: llamadas,
respuestas desde caché y tokens.

## Seguridad

- Las claves solo se leen de `.env` o del entorno, como `SecretStr`. `llm estado` dice si están
  definidas, nunca su valor.
- `LLM_PROVIDER` y `LLM_RESPALDO` solo admiten nombres de proveedor. Si contienen otra cosa (por
  ejemplo, una clave pegada en la línea equivocada), el error lo indica sin repetir el valor, y
  `/configuracion` solo muestra los nombres reconocidos. La CLI no imprime variables locales en
  los errores no controlados.
- Una clave inválida se informa como «la clave … no es válida (401)», sin el cuerpo de la
  respuesta del proveedor.
- El texto de un error 429 del proveedor (que incluye el id de la organización) no llega al
  usuario: el mensaje lo arma el motor.
- La caché guarda la salida del LLM, pero no el prompt ni el documento. Está en `.cache/`, que Git
  ignora, y una entrada dañada se descarta.
