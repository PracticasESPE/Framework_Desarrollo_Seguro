# Controles de seguridad (OWASP ASVS 4.0.3)

`asvs.yaml` contiene los requisitos de OWASP ASVS (Application Security Verification Standard,
el estándar de OWASP que lista qué debe verificarse en una aplicación segura) que citan los
patrones, las directrices y los riesgos del API Top 10.

| Campo | Contenido |
|---|---|
| `id` | `ASVS-V<capítulo>.<sección>.<requisito>`, igual que en el estándar |
| `capitulo`, `seccion` | Ubicación del requisito en ASVS |
| `descripcion` | Resumen propio en español |
| `niveles` | Niveles de ASVS en los que se exige: 1 (básico), 2 (estándar), 3 (crítico) |
| `cwe` | Debilidad CWE que ASVS asocia al requisito |

Identificadores, niveles y CWE se tomaron del CSV oficial de la versión 4.0.3.

## Revisión del 20/10/2026

Al contrastar los mapeos iniciales con el CSV oficial se corrigieron tres:

| Archivo | Antes | Después | Motivo |
|---|---|---|---|
| `directrices/minimo_privilegio.yaml` | ASVS-V1.4.3 | (eliminado) | ASVS 4.0.3 lo borró por duplicar a V4.1.3, que ya estaba |
| `patrones/api_gateway.yaml` | ASVS-V13.1.3 | ASVS-V1.4.1 | V13.1.3 trata de no exponer datos en las URL; V1.4.1 exige aplicar el control de acceso en puntos de confianza como un gateway |
| `directrices/seguro_por_defecto.yaml` | ASVS-V14.4.1 | ASVS-V14.4.4 y ASVS-V14.4.5 | V14.4.1 solo exige la cabecera Content-Type; las cabeceras que activa Helmet por defecto corresponden a V14.4.4 (nosniff) y V14.4.5 (HSTS) |

El validador (`uv run framework conocimiento validar`) rechaza cualquier control citado que no
esté en `asvs.yaml`.
