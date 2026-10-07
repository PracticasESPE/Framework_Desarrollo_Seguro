# Comparación de proveedores de LLM

Prueba corta del sprint 1 para elegir el proveedor de LLM del framework (plan técnico, sección 6.3).
Los mismos cinco requisitos (`requisitos.json`) se procesan con cada proveedor candidato y se mide:

| Tarea | Nivel de modelo | Qué se mide |
|---|---|---|
| Extracción del requisito a JSON | rápido | Esquema válido al primer intento, tipo RF/RNF correcto, cobertura de etiquetas de seguridad, latencia |
| Generación de un servicio NestJS | razonamiento | Archivo generado, compila con `tsc --noEmit` en modo estricto sin cambios, latencia |

## Ejecución

```bash
# Una vez: dependencias del servicio de referencia, para poder compilar el TypeScript generado
cd services/usuarios && npm ci --ignore-scripts && cd ../..

# Claves en .env (GEMINI_API_KEY y GROQ_API_KEY tienen plan gratuito)
uv run python -m evaluation.comparacion_llm.comparar gemini groq
```

Genera `resultados.md` (tabla comparativa) y `resultados.json` (detalle por requisito).
Un proveedor sin clave configurada se omite con un aviso.

## Proveedor elegido

**Groq**, con `openai/gpt-oss-20b` como modelo rápido y `openai/gpt-oss-120b` como modelo de
razonamiento. Decisión tomada con la ejecución del 7 de octubre de 2026 (`resultados.md`):

| Criterio (plan técnico, 6.3) | Groq | Gemini |
|---|---|---|
| Salida estructurada | 5/5 JSON válidos al primer intento | 5/5 JSON válidos al primer intento |
| Calidad de TypeScript y NestJS | 5/5 archivos compilan sin cambios | Solo se pudo generar 1 de 5 (compiló) |
| Plan gratuito suficiente | Sin errores de cuota en la prueba | Límite de 20 peticiones diarias en `gemini-3.8-flash`, agotado durante la prueba |
| Latencia | 0,9 s en extracción y 2,0 s en generación | 10,3 s en extracción y 110 s en generación |
| Disponibilidad | 0 reintentos | 10 reintentos por saturación (503) o cuota (429) |

Motivo principal: el plan gratuito de Gemini no alcanza para el pipeline, que hace varias llamadas
por requisito y por iteración de refinamiento. En la clasificación de requisitos ambos acertaron
el tipo en los cinco casos y la cobertura de etiquetas fue similar (0,80 Gemini, 0,77 Groq).

Limitaciones de la prueba:

- Es una sola ejecución con cinco requisitos; sirve para elegir, no para afirmar diferencias de calidad.
- La calidad de generación de Gemini no quedó medida: cuatro de cinco llamadas fallaron por
  disponibilidad, no por el contenido de la respuesta.
- Claude no se evaluó por ser de pago y Ollama por los recursos que exige en los equipos locales.
  Ambos adaptadores siguen disponibles para la comparación de modelos de la evaluación DSR.
