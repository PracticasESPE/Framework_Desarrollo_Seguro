#!/usr/bin/env bash
# Security Gate 1 sobre los servicios generados (fase 4, #71).
#
# El mismo análisis estático que scripts/gate1.sh aplica al servicio de referencia, servicio por
# servicio, sobre el código que generan la plantilla y el LLM:
#   1. tsc --noEmit (compilación y tipos)
#   2. ESLint + eslint-plugin-security, con la configuración del framework (eslint/): el código
#      generado no puede desactivar ni relajar sus reglas
#   3. Semgrep: reglas públicas de TypeScript y Node.js y las propias (semgrep_rules/)
#   4. Gitleaks: secretos en la carpeta del servicio (el código generado no está en Git)
#   5. Trivy fs: vulnerabilidades de sus dependencias (package-lock.json)
#   6. Trivy config: configuración del Dockerfile
#   7. Hadolint: buenas prácticas del Dockerfile
#
# Uso: bash scripts/gate1-servicios.sh [carpeta de los servicios]   (por defecto salida/servicios)
#
# Deja los SARIF de cada servicio en salida/security/sarif/servicios/<servicio>/, con los nombres
# que lee el motor (la decisión de OPA es `framework gates servicios`), y una copia de todos en
# salida/security/sarif/servicios-github/ con su categoría para GitHub code scanning.
# Como en gate1.sh, distingue «hallazgos» de «error de la herramienta», que se reintenta.
set +e
cd "$(git rev-parse --show-toplevel)" || exit 2
RAIZ=$PWD
# Node necesita la ruta nativa: en Git Bash de Windows, /d/... sería D:\d\... (en Linux, igual).
RAIZ_NODE=$RAIZ
if command -v cygpath >/dev/null 2>&1; then RAIZ_NODE=$(cygpath -m "$RAIZ"); fi

SERVICIOS=${1:-salida/servicios}
SARIF_RAIZ=salida/security/sarif/servicios
PUBLICAR=salida/security/sarif/servicios-github
CACHE=.trivy-cache
PAUSA=${PAUSA:-15}
# Las mismas versiones que scripts/gate1.sh (lo comprueba tests/test_gate1_servicios.py).
SEMGREP=semgrep/semgrep:1.172.0
GITLEAKS=ghcr.io/gitleaks/gitleaks:v8.30.1
TRIVY_IMG=aquasec/trivy:0.71.1
HADOLINT=hadolint/hadolint:v2.15.1
HALLAZGO=10
ESLINT_JS=eslint/node_modules/eslint/bin/eslint.js
# Un Python que funcione: en Windows, «python3» puede ser el alias de la Microsoft Store.
PYTHON=""
for candidato in python3 python; do
  if "$candidato" -c "import sys" >/dev/null 2>&1; then PYTHON=$candidato; break; fi
done

if [ ! -d "$SERVICIOS" ]; then
  echo "::error::No existe $SERVICIOS: genera antes los servicios"
  exit 2
fi
# Sin Docker, cada herramienta fallaría con el código 1, que Semgrep, ESLint y Hadolint usan para
# «hay hallazgos»: se detiene aquí con un error claro en lugar de dar un resultado engañoso.
if ! docker info >/dev/null 2>&1; then
  echo "::error::Docker no responde: el Gate 1 necesita Docker para Semgrep, Gitleaks, Trivy y Hadolint"
  exit 2
fi
if [ -z "$PYTHON" ]; then
  echo "::error::No hay un intérprete de Python para preparar los SARIF"
  exit 2
fi
rm -rf "$SARIF_RAIZ" "$PUBLICAR"
mkdir -p "$SARIF_RAIZ" "$PUBLICAR" "$CACHE"
FALLOS=0
FILAS=()

reintentar() {
  local n=1
  until "$@"; do
    if [ "$n" -ge 3 ]; then return 1; fi
    echo "::warning::Reintento $n de 2 para: $*"
    n=$((n+1))
    sleep "$PAUSA"
  done
}

# ejecutar "Servicio" "Herramienta" CODIGO_DE_HALLAZGOS comando...  (como en gate1.sh)
ejecutar() {
  local servicio="$1" nombre="$2" cod_hallazgos="$3" intento=1 codigo estado
  shift 3
  while true; do
    "$@"
    codigo=$?
    if [ "$codigo" -eq 0 ]; then break; fi
    if [ "$cod_hallazgos" = "*" ] || [ "$codigo" -eq "$cod_hallazgos" ]; then break; fi
    if [ "$intento" -ge 3 ]; then break; fi
    echo "::warning::$servicio: $nombre falló por un error de la herramienta (código $codigo). Reintento $intento de 2 en ${PAUSA} s"
    intento=$((intento+1))
    sleep "$PAUSA"
  done
  if [ "$codigo" -eq 0 ]; then
    estado="OK"
  elif [ "$cod_hallazgos" = "*" ] || [ "$codigo" -eq "$cod_hallazgos" ]; then
    estado="HALLAZGOS"
    FALLOS=$((FALLOS+1))
  else
    estado="ERROR DE LA HERRAMIENTA (código $codigo)"
    FALLOS=$((FALLOS+1))
  fi
  FILAS+=("| $servicio | $nombre | $estado | $intento |")
  return "$codigo"
}

# Cada contenedor monta solo lo que analiza: la carpeta del servicio (solo lectura), sus reglas o
# su configuración y la carpeta donde deja el SARIF. Montar el repositorio entero hacía cada
# herramienta muchas veces más lenta en Windows. Las rutas relativas que dejan así las corrige
# después sarif_servicio.py.
trivy_servicio() {
  docker run --rm -v "$RAIZ/$dir:/servicio:ro" -v "$RAIZ/$out:/salida" \
    -v "$RAIZ/$CACHE:/root/.cache/trivy" "$TRIVY_IMG" "$@"
}

echo "=== Preparación: imágenes de las herramientas y ESLint del framework ==="
for img in "$SEMGREP" "$GITLEAKS" "$TRIVY_IMG" "$HADOLINT"; do
  if ! reintentar docker pull --quiet "$img" >/dev/null; then
    echo "::error::No se pudo descargar $img"
    FALLOS=$((FALLOS+1))
    FILAS+=("| (todos) | descarga de $img | ERROR DE LA HERRAMIENTA | 3 |")
  fi
done
if [ ! -f "$ESLINT_JS" ]; then
  reintentar npm ci --ignore-scripts --no-audit --no-fund --prefix eslint >/dev/null
fi
# Sin ESLint, node terminaría con código 1, el mismo que «hay hallazgos»: se marca como caída.
ESLINT_OK=1
if [ ! -f "$ESLINT_JS" ]; then
  echo "::error::No se pudo instalar el ESLint del framework (eslint/)"
  ESLINT_OK=0
fi

SERVICIOS_ANALIZADOS=()
for dir in "$SERVICIOS"/*/; do
  dir=${dir%/}
  [ -f "$dir/.copier-answers.yml" ] || continue  # solo lo que generó la plantilla
  svc=$(basename "$dir")
  out="$SARIF_RAIZ/$svc"
  mkdir -p "$out"
  SERVICIOS_ANALIZADOS+=("$svc")
  echo
  echo "################ $svc ($dir) ################"

  # Lo necesario para compilar: dependencias exactas del lock, sin scripts, y el cliente de Prisma.
  if [ ! -d "$dir/node_modules" ]; then
    ejecutar "$svc" "Preparación (npm ci)" "*" \
      bash -c "cd '$dir' && npm ci --ignore-scripts --no-audit --no-fund >/dev/null"
  fi
  if [ ! -d "$dir/src/generated" ]; then
    ejecutar "$svc" "Preparación (prisma generate)" "*" bash -c \
      "cd '$dir' && DATABASE_URL=postgresql://gate1:gate1@localhost:5432/gate1 npm run --silent prisma:generate >/dev/null"
  fi

  echo "=== $svc 1/7 tsc --noEmit ==="
  if ejecutar "$svc" "tsc --noEmit" "*" bash -c "cd '$dir' && npx tsc --noEmit"; then
    echo ok > "$out/compilacion.txt"
  else
    echo error > "$out/compilacion.txt"
  fi

  echo "=== $svc 2/7 ESLint + eslint-plugin-security (configuración del framework) ==="
  # Código 1: hay errores de las reglas; 2: ESLint no pudo analizar (error de la herramienta).
  if [ "$ESLINT_OK" -eq 1 ]; then
    ejecutar "$svc" "ESLint + security" 1 bash -c \
      "cd '$dir' && node '$RAIZ_NODE/$ESLINT_JS' --config '$RAIZ_NODE/eslint/eslint.config.mjs' \
         --format json --output-file '$RAIZ_NODE/$out/eslint.json' 'src/**/*.ts'"
    # El conversor imprime cada resultado (archivo:línea regla mensaje) para el log.
    if [ -s "$out/eslint.json" ]; then
      node eslint/convertir-a-sarif.mjs "$out/eslint.json" "$out/eslint.sarif" "$RAIZ_NODE"
    fi
    rm -f "$out/eslint.json"
  else
    FALLOS=$((FALLOS+1))
    FILAS+=("| $svc | ESLint + security | ERROR DE LA HERRAMIENTA (sin instalar) | 0 |")
  fi

  echo "=== $svc 3/7 Semgrep (reglas públicas y propias) ==="
  # --no-git-ignore: el código generado no está en Git; sin la opción, Semgrep no lo vería.
  # Las reglas propias se montan en semgrep_rules/, como en gate1.sh: mismos ids de regla.
  ejecutar "$svc" "Semgrep" 1 docker run --rm -w /src \
    -v "$RAIZ/$dir/src:/src/src:ro" -v "$RAIZ/semgrep_rules:/src/semgrep_rules:ro" \
    -v "$RAIZ/$out:/salida" "$SEMGREP" \
    semgrep scan --config p/typescript --config p/nodejs --config semgrep_rules/ \
    --metrics=off --error --severity ERROR --severity WARNING --no-git-ignore \
    --sarif-output=/salida/semgrep.sarif \
    --exclude generated --exclude "*.spec.ts" src

  echo "=== $svc 4/7 Gitleaks (secretos en el servicio) ==="
  ejecutar "$svc" "Gitleaks" "$HALLAZGO" docker run --rm \
    -v "$RAIZ/$dir:/servicio:ro" -v "$RAIZ/scripts/gitleaks-servicios.toml:/gitleaks.toml:ro" \
    -v "$RAIZ/$out:/salida" "$GITLEAKS" \
    dir --no-banner --redact --verbose --exit-code "$HALLAZGO" --config /gitleaks.toml \
    --report-format sarif --report-path /salida/gitleaks.sarif /servicio

  echo "=== $svc 5/7 Trivy fs (dependencias) ==="
  ejecutar "$svc" "Trivy fs" "$HALLAZGO" trivy_servicio fs --quiet --scanners vuln \
    --severity HIGH,CRITICAL --exit-code "$HALLAZGO" --skip-dirs "**/node_modules" /servicio
  reintentar trivy_servicio fs --quiet --scanners vuln --severity HIGH,CRITICAL \
    --skip-dirs "**/node_modules" --format sarif --output /salida/trivy-fs.sarif /servicio \
    || echo "::warning::$svc: no se pudo generar trivy-fs.sarif"

  echo "=== $svc 6/7 Trivy config (Dockerfile) ==="
  ejecutar "$svc" "Trivy config" "$HALLAZGO" trivy_servicio config --quiet \
    --severity HIGH,CRITICAL --exit-code "$HALLAZGO" --skip-dirs "**/node_modules" /servicio
  reintentar trivy_servicio config --quiet --severity HIGH,CRITICAL \
    --skip-dirs "**/node_modules" --format sarif --output /salida/trivy-config.sarif /servicio \
    || echo "::warning::$svc: no se pudo generar trivy-config.sarif"

  echo "=== $svc 7/7 Hadolint (Dockerfile) ==="
  ejecutar "$svc" "Hadolint" 1 docker run --rm -v "$RAIZ/$dir:/servicio:ro" -w /servicio \
    "$HADOLINT" hadolint --failure-threshold warning Dockerfile
  reintentar bash -c "docker run --rm -v '$RAIZ/$dir:/servicio:ro' -w /servicio $HADOLINT hadolint --no-fail --format sarif Dockerfile > '$out/hadolint.sarif'" \
    || echo "::warning::$svc: no se pudo generar hadolint.sarif"

  # Los contenedores escriben como root; GitHub rechaza los SARIF vacíos (y el motor trata un
  # SARIF ausente como herramienta caída).
  sudo chown -R "$(id -u):$(id -g)" "$out" 2>/dev/null
  find "$out" -type f -empty -delete
  "$PYTHON" orchestrator/gates/sarif_servicio.py "$out" "$dir" "$svc" "$PUBLICAR"
done

if [ "${#SERVICIOS_ANALIZADOS[@]}" -eq 0 ]; then
  echo "::error::No hay servicios generados en $SERVICIOS (ninguno tiene .copier-answers.yml)"
  exit 2
fi

{
  echo "## Security Gate 1 sobre los servicios generados"
  echo
  echo "Servicios: ${SERVICIOS_ANALIZADOS[*]}"
  echo
  echo "| Servicio | Herramienta | Resultado | Intentos |"
  echo "|---|---|---|---|"
  printf '%s\n' "${FILAS[@]}"
  echo
  if [ "$FALLOS" -eq 0 ]; then echo "**Gate 1 sin hallazgos en ningún servicio**"; else echo "**Gate 1 con $FALLOS fallo(s)**"; fi
} | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"

echo "=== SARIF para GitHub ($PUBLICAR) ==="
ls -l "$PUBLICAR"
echo "=== Resultado: $FALLOS herramienta(s) con hallazgos o errores en ${#SERVICIOS_ANALIZADOS[@]} servicio(s) ==="
[ "$FALLOS" -eq 0 ]
