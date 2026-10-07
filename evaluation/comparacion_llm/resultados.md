# Comparación de proveedores de LLM

Ejecutada el 2026-10-07 17:24 UTC. Cinco requisitos; la salida se valida al primer intento y solo se reintentan los fallos del servicio.

| Proveedor | Modelo rápido | Modelo de razonamiento | JSON válido | Tipo correcto | Cobertura de etiquetas | TypeScript generado | TypeScript compila | Latencia extracción (s) | Latencia generación (s) | Reintentos por servicio |
|---|---|---|---|---|---|---|---|---|---|---|
| gemini | gemini-3.5-flash-lite | gemini-3.8-flash | 5/5 | 5/5 | 0.8 | 1/5 | 1/1 | 10.33 | 110.26 | 10 |
| groq | openai/gpt-oss-20b | openai/gpt-oss-120b | 5/5 | 5/5 | 0.77 | 5/5 | 5/5 | 0.93 | 2.0 | 0 |

## Errores

- **gemini**, RF-01: generación: gemini: error 503 de la API: This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.
- **gemini**, RF-02: generación: gemini: error 503 de la API: This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.
- **gemini**, RF-03: generación: gemini: error 503 de la API: This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.
- **gemini**, RNF-02: generación: gemini: error 429 de la API: You exceeded your current quota, please check your plan and billing details. For more information on this error, head to: https://ai.google.dev/gemini-api/docs/rate-limits. To monitor your current usage, head to: https://ai.dev/rate-limit. 
* Quota exceeded for metric: generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 20, model: gemini-3.8-flash
Please retry in 6h36m13.660171768s.

## Cómo leer la tabla

- **JSON válido**: la respuesta cumplió el esquema Pydantic al primer intento.
- **Tipo correcto**: clasificó bien el requisito como funcional o no funcional.
- **Cobertura de etiquetas**: proporción media de las etiquetas de seguridad esperadas que el modelo asignó (1.0 es el máximo).
- **TypeScript compila**: archivos que pasan `tsc --noEmit` en modo estricto con la configuración del servicio de referencia, sin ningún cambio.
- **Latencias**: media de las llamadas que terminaron bien, sin contar esperas.
- **Reintentos por servicio**: llamadas repetidas porque el proveedor estaba saturado o sin cuota; no cuentan como fallo de calidad, pero indican su disponibilidad.
