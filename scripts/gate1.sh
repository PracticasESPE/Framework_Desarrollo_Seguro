#!/usr/bin/env bash
# Security Gate 1: analisis estatico del servicio de referencia.
# Distingue "hallazgos" (la herramienta funciono y encontro problemas) de
# "error de la herramienta" (red, descarga, caida): este ultimo se reintenta.
set +e
cd "$(git rev-parse --show-toplevel)" || exit 2

SVC=services/usuarios
SARIF=salida/security/sarif
CACHE=.trivy-cache
PAUSA=${PAUSA:-15}
SEMGREP=semgrep/semgrep:1.172.0
GITLEAKS=ghcr.io/gitleaks/gitleaks:v8.30.1
TRIVY_IMG=aquasec/trivy:0.71.1
HADOLINT=hadolint/hadolint:v2.15.1
HALLAZGO=10   # codigo de salida propio para "hay hallazgos" en Gitleaks y Trivy

mkdir -p "$SARIF" "$CACHE"
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

# ejecutar "Nombre" CODIGO_DE_HALLAZGOS comando...
#   CODIGO_DE_HALLAZGOS = codigo de salida que significa "hay hallazgos" ("*" = cualquiera).
#   Cualquier otro codigo distinto de 0 es un error de la herramienta y se reintenta 2 veces.
ejecutar() {
  local nombre="$1" cod_hallazgos="$2" intento=1 codigo estado
  shift 2
  while true; do
    "$@"
    codigo=$?
    if [ "$codigo" -eq 0 ]; then break; fi
    if [ "$cod_hallazgos" = "*" ] || [ "$codigo" -eq "$cod_hallazgos" ]; then break; fi
    if [ "$intento" -ge 3 ]; then break; fi
    echo "::warning::$nombre fallo por un error de la herramienta (codigo $codigo). Reintento $intento de 2 en ${PAUSA} s"
    intento=$((intento+1))
    sleep "$PAUSA"
  done
  if [ "$codigo" -eq 0 ]; then
    estado="OK"
  elif [ "$cod_hallazgos" = "*" ] || [ "$codigo" -eq "$cod_hallazgos" ]; then
    estado="HALLAZGOS"
    FALLOS=$((FALLOS+1))
  else
    estado="ERROR DE LA HERRAMIENTA (codigo $codigo)"
    FALLOS=$((FALLOS+1))
  fi
  FILAS+=("| $nombre | $estado | $intento |")
}

trivy() { docker run --rm -v "$PWD:/work" -v "$PWD/$CACHE:/root/.cache/trivy" -w /work "$TRIVY_IMG" "$@"; }
TRIVY_SKIP=(--skip-dirs "**/node_modules" --skip-dirs "$CACHE" --skip-dirs salida)

echo "=== 0/7 Preparacion: descarga de las imagenes de las herramientas ==="
for img in "$SEMGREP" "$GITLEAKS" "$TRIVY_IMG" "$HADOLINT"; do
  if ! reintentar docker pull --quiet "$img" >/dev/null; then
    echo "::error::No se pudo descargar $img"
    FALLOS=$((FALLOS+1))
    FILAS+=("| descarga de $img | ERROR DE LA HERRAMIENTA | 3 |")
  fi
done

echo "=== 1/7 tsc --noEmit (compilacion y tipos) ==="
ejecutar "tsc --noEmit" "*" bash -c "cd $SVC && npx tsc --noEmit"

echo "=== 2/7 ESLint + eslint-plugin-security ==="
ejecutar "ESLint + security" 1 bash -c "cd $SVC && npx eslint 'src/**/*.ts'"

echo "=== 3/7 Semgrep (SAST: reglas publicas y propias) ==="
ejecutar "Semgrep (reglas publicas y propias)" 1 docker run --rm -v "$PWD:/src" "$SEMGREP" \
  semgrep scan --config p/typescript --config p/nodejs --config semgrep_rules/ \
  --metrics=off --error --severity ERROR --severity WARNING \
  --sarif-output="$SARIF/semgrep.sarif" \
  --exclude generated --exclude "*.spec.ts" "$SVC/src"
echo "--- Pruebas de las reglas propias (semgrep --test) ---"
ejecutar "Semgrep --test (reglas propias)" 1 docker run --rm -v "$PWD:/src" "$SEMGREP" \
  semgrep --test semgrep_rules/

echo "=== 4/7 Gitleaks (secretos en el historial) ==="
ejecutar "Gitleaks (historial)" "$HALLAZGO" docker run --rm -v "$PWD:/repo" \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/repo \
  "$GITLEAKS" git --no-banner --redact --verbose --exit-code "$HALLAZGO" \
  --report-format sarif --report-path "/repo/$SARIF/gitleaks.sarif" /repo

echo "=== 5/7 Trivy fs (SCA: dependencias npm) ==="
ejecutar "Trivy fs (dependencias)" "$HALLAZGO" trivy fs --scanners vuln --severity HIGH,CRITICAL \
  --exit-code "$HALLAZGO" "${TRIVY_SKIP[@]}" .
reintentar trivy fs --scanners vuln --severity HIGH,CRITICAL "${TRIVY_SKIP[@]}" \
  --format sarif --output "$SARIF/trivy-fs.sarif" . >/dev/null \
  || echo "::warning::No se pudo generar trivy-fs.sarif"

echo "=== 6/7 Trivy config (Dockerfile y Compose) ==="
ejecutar "Trivy config (Dockerfile y Compose)" "$HALLAZGO" trivy config --severity HIGH,CRITICAL \
  --exit-code "$HALLAZGO" "${TRIVY_SKIP[@]}" .
reintentar trivy config --severity HIGH,CRITICAL "${TRIVY_SKIP[@]}" \
  --format sarif --output "$SARIF/trivy-config.sarif" . >/dev/null \
  || echo "::warning::No se pudo generar trivy-config.sarif"

echo "=== 7/7 Hadolint (buenas practicas del Dockerfile) ==="
ejecutar "Hadolint" 1 docker run --rm -v "$PWD:/work" -w /work "$HADOLINT" \
  hadolint --failure-threshold warning "$SVC/Dockerfile"
reintentar bash -c "docker run --rm -v \"$PWD:/work\" -w /work $HADOLINT hadolint --no-fail --format sarif $SVC/Dockerfile > \"$SARIF/hadolint.sarif\"" \
  || echo "::warning::No se pudo generar hadolint.sarif"

# Los contenedores corren como root: devolvemos la propiedad al usuario del runner
# y quitamos SARIF vacios (GitHub rechaza archivos vacios).
sudo chown -R "$(id -u):$(id -g)" salida "$CACHE" 2>/dev/null
find "$SARIF" -type f -empty -delete

echo "=== Archivos SARIF generados ==="
ls -l "$SARIF"

{
  echo "## Security Gate 1"
  echo
  echo "| Herramienta | Resultado | Intentos |"
  echo "|---|---|---|"
  printf '%s\n' "${FILAS[@]}"
  echo
  if [ "$FALLOS" -eq 0 ]; then echo "**Gate 1 aprobado**"; else echo "**Gate 1 con $FALLOS fallo(s)**"; fi
} | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"

echo "=== Resultado del Gate 1: $FALLOS herramienta(s) con hallazgos o errores ==="
[ "$FALLOS" -eq 0 ]
