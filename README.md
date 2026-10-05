# Framework de Desarrollo Seguro guiado por Conocimiento

Framework DevSecOps que automatiza la seguridad y las buenas prácticas de diseño en el ciclo de vida de arquitecturas de microservicios. Recibe un documento de requisitos en lenguaje natural y produce microservicios backend en **NestJS/TypeScript**, contenerizados, probados y validados en seguridad, junto con un **informe de evidencia** que traza cada requisito hasta el código y los controles que lo satisfacen.

> **Estado:** en desarrollo (octubre 2026 – enero 2027).

## Objetivo

Sustituir las revisiones de seguridad manuales y aisladas por **conocimiento formalizado y reglas computacionales**. Los modelos de lenguaje (LLM) proponen y las reglas deciden: toda decisión que afecta la seguridad la toma un motor de reglas determinista (Open Policy Agent) y queda registrada con la regla que la justifica.

## Arquitectura

El framework se organiza en tres capas:

| Capa | Contenido |
|---|---|
| **Núcleo de conocimiento** | Base de conocimiento (YAML + Neo4j), motor de razonamiento (OPA + LLM) y trazabilidad |
| **Pipeline de construcción y validación** | 11 fases, desde los requisitos hasta los contenedores validados, con 3 Security Gates y refinamiento iterativo |
| **Marco metodológico** | Ciclo Design Science Research (DSR) para construir y evaluar el framework |

### Fases del pipeline

1. Adquisición de requisitos
2. Análisis y propuesta arquitectónica
3. Generación de microservicios NestJS
4. **Security Gate 1:** análisis estático (SAST, SCA, secretos)
5. y 6. Refinamiento iterativo guiado por conocimiento
7. Integración (API Gateway, event bus, Identity Provider)
8. **Security Gate 2:** seguridad de integración
9. Pruebas automatizadas
10. Contenerización
11. **Security Gate 3:** DAST

## Stack tecnológico

| Área | Herramientas |
|---|---|
| Motor | Python 3.12, FastAPI, Typer, Pydantic, uv |
| Conocimiento y razonamiento | Neo4j (grafo + índice vectorial), Open Policy Agent (Rego) |
| Microservicios generados | NestJS, TypeScript, Prisma, PostgreSQL |
| Seguridad | Semgrep, ESLint, Gitleaks, Trivy, Hadolint, Spectral, Conftest, OWASP ZAP, Nuclei |
| Integración | Traefik, RabbitMQ, Keycloak |
| Pruebas | Jest, Supertest, Testcontainers, Schemathesis |
| CI/CD | GitHub Actions, Docker Compose, notificaciones en Telegram |
| Interfaz | React + Vite |

## Estructura del repositorio

```
knowledge_base/   Conocimiento en YAML: patrones, controles, CWE/OWASP
graph/            Scripts Cypher de Neo4j
policies/         Políticas Rego (arquitectura, gates, integración)
semgrep_rules/    Reglas SAST propias para TypeScript/NestJS
spectral/         Reglas de seguridad para contratos OpenAPI
templates/        Plantilla Copier del microservicio NestJS
orchestrator/     Motor del framework en Python
tools/            Utilidades auxiliares (ts-integrity con ts-morph)
dashboard/        Interfaz React + Vite
evaluation/       Datasets, líneas base y experimentos
scripts/          Scripts de instalación de herramientas
docs/             Plan técnico y documentación del proyecto
.github/workflows Pipeline de CI
```

El plan técnico completo está en [docs/framework_desarrollo_seguro_v2.pdf](docs/framework_desarrollo_seguro_v2.pdf).

## Flujo de ramas

| Rama | Uso |
|---|---|
| `main` | Versión estable. Solo recibe cambios desde `test`. |
| `test` | Validación de lo integrado antes de pasar a `main`. |
| `dev` | Integración del trabajo diario. |
| `feature/*` | Una rama por tarea, creada desde `dev`. |

Todo cambio entra mediante **pull request revisado por el otro integrante**.

```bash
git checkout dev
git pull origin dev
git checkout -b feature/nombre-de-la-tarea
# ... cambios ...
git push -u origin feature/nombre-de-la-tarea
# Abrir pull request hacia dev en GitHub
```

## Instalación y uso

*Se completará a medida que avance el desarrollo.*

## Equipo

| Integrante | Responsabilidad |
|---|---|
| Marcelo Acuña  | Motor e IA: motor en Python, adaptador de LLM, base de conocimiento y Neo4j, políticas OPA, refinamiento, trazabilidad e informe de evidencia |
| Abner Arboleda | Plataforma y seguridad: microservicio NestJS de referencia y plantilla, CI/CD y Telegram, Security Gates, integración, pruebas, contenedores, DAST y dashboard |

Universidad de las Fuerzas Armadas – ESPE · Ingeniería de Software