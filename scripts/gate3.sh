#!/usr/bin/env bash
# Security Gate 3 (inicial): imagen de contenedor del servicio de referencia.
#   1. Exporta la imagen a un archivo, para analizarla sin dar acceso al socket de Docker.
#   2. Trivy image: vulnerabilidades del sistema operativo y de las librerías (SARIF).
#   3. Syft: SBOM en CycloneDX, el inventario verificable de componentes (sbom.json).
# ZAP y Nuclei (DAST) se añaden a este Gate; la decisión final la tomará OPA (gate3.rego).
# Requiere la imagen construida (fase 10) y Docker.
set +e
cd "$(git rev-parse --show-toplevel)" || exit 2

IMAGEN=${IMAGEN:-fw-usuarios:ci}
SARIF=salida/security/sarif
SBOM=salida/sbom/sbom.json
DIR_IMAGEN=salida/imagen
ARCHIVO_IMAGEN=$DIR_IMAGEN/imagen.tar
CACHE=.trivy-cache
PAUSA=${PAUSA:-15}
TRIVY_IMG=aquasec/trivy:0.71.1
SYFT_IMG=anchore/syft:v1.54.1
HALLAZGO=10   # codigo de salida propio de Trivy para "hay hallazgos"

mkdir -p "$SARIF" "$(dirname "$SBOM")" "$DIR_IMAGEN" "$CACHE"
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
#   Cualquier otro codigo distinto de 0 es un error de la herramienta y se reintenta 2 veces.
ejecutar() {
  local nombre="$1" cod_hallazgos="$2" intento=1 codigo estado
  shift 2
  while true; do
    "$@"
    codigo=$?
    if [ "$codigo" -eq 0 ] || [ "$codigo" -eq "$cod_hallazgos" ]; then break; fi
    if [ "$intento" -ge 3 ]; then break; fi
    echo "::warning::$nombre fallo por un error de la herramienta (codigo $codigo). Reintento $intento de 2 en ${PAUSA} s"
    intento=$((intento+1))
    sleep "$PAUSA"
  done
  if [ "$codigo" -eq 0 ]; then
    estado="OK"
  elif [ "$codigo" -eq "$cod_hallazgos" ]; then
    estado="HALLAZGOS"
    FALLOS=$((FALLOS+1))
  else
    estado="ERROR DE LA HERRAMIENTA (codigo $codigo)"
    FALLOS=$((FALLOS+1))
  fi
  FILAS+=("| $nombre | $estado | $intento |")
}

trivy() { docker run --rm -v "$PWD:/work" -v "$PWD/$CACHE:/root/.cache/trivy" -w /work "$TRIVY_IMG" "$@"; }
syft() { docker run --rm -v "$PWD:/work" -w /work "$SYFT_IMG" "$@"; }

# Una línea con el total, porque la tabla de Trivy no se imprime cuando no hay hallazgos.
contar_hallazgos() {
  node -e "
    const s = JSON.parse(require('fs').readFileSync(process.argv[1], 'utf8'));
    console.log('Trivy image: ' + s.runs[0].results.length + ' vulnerabilidades HIGH o CRITICAL');
  " "$SARIF/trivy-image.sarif"
}

# Comprueba que el SBOM es CycloneDX de verdad y que describe componentes.
validar_sbom() {
  node -e "
    const s = JSON.parse(require('fs').readFileSync(process.argv[1], 'utf8'));
    const n = (s.components || []).length;
    if (s.bomFormat !== 'CycloneDX' || n === 0) process.exit(1);
    console.log('SBOM ' + s.bomFormat + ' ' + s.specVersion + ': ' + n + ' componentes');
  " "$SBOM"
}

echo "=== 0/3 Preparacion: descarga de las imagenes de las herramientas ==="
for img in "$TRIVY_IMG" "$SYFT_IMG"; do
  if ! reintentar docker pull --quiet "$img" >/dev/null; then
    echo "::error::No se pudo descargar $img"
    FALLOS=$((FALLOS+1))
    FILAS+=("| descarga de $img | ERROR DE LA HERRAMIENTA | 3 |")
  fi
done

echo "=== 1/3 Exportar la imagen $IMAGEN ==="
if docker save -o "$ARCHIVO_IMAGEN" "$IMAGEN"; then
  FILAS+=("| Exportar la imagen | OK | 1 |")
else
  echo "::error::No existe la imagen $IMAGEN; ejecuta antes la fase 10 (docker build)"
  FILAS+=("| Exportar la imagen | ERROR DE LA HERRAMIENTA | 1 |")
  FALLOS=$((FALLOS+1))
fi

if [ -s "$ARCHIVO_IMAGEN" ]; then
  echo "=== 2/3 Trivy image: vulnerabilidades del sistema operativo y de las librerias ==="
  # --table-mode detailed: solo las tablas con hallazgos, sin una fila por cada librería limpia.
  ejecutar "Trivy image" "$HALLAZGO" trivy image --input "$ARCHIVO_IMAGEN" --scanners vuln \
    --severity HIGH,CRITICAL --exit-code "$HALLAZGO" --timeout 10m --table-mode detailed
  reintentar trivy image --input "$ARCHIVO_IMAGEN" --scanners vuln --severity HIGH,CRITICAL \
    --timeout 10m --format sarif --output "$SARIF/trivy-image.sarif" >/dev/null \
    || echo "::warning::No se pudo generar trivy-image.sarif"
  contar_hallazgos

  echo "=== 3/3 Syft: SBOM en CycloneDX ==="
  ejecutar "Syft (SBOM en CycloneDX)" 99 syft "docker-archive:$ARCHIVO_IMAGEN" \
    --quiet --output "cyclonedx-json=$SBOM"
  if ! validar_sbom; then
    echo "::error::$SBOM no es un SBOM CycloneDX con componentes"
    FILAS+=("| Validar el SBOM | HALLAZGOS | 1 |")
    FALLOS=$((FALLOS+1))
  else
    FILAS+=("| Validar el SBOM | OK | 1 |")
  fi
fi

# El archivo de la imagen ocupa cientos de MB y no es una evidencia: no se conserva.
# Los contenedores corren como root: devolvemos la propiedad al usuario del runner
# y quitamos SARIF vacios (GitHub rechaza archivos vacios).
sudo chown -R "$(id -u):$(id -g)" salida "$CACHE" 2>/dev/null
rm -f "$ARCHIVO_IMAGEN"
find "$SARIF" -type f -empty -delete

{
  echo "## Security Gate 3 (inicial)"
  echo
  echo "| Comprobación | Resultado | Intentos |"
  echo "|---|---|---|"
  printf '%s\n' "${FILAS[@]}"
  echo
  if [ "$FALLOS" -eq 0 ]; then echo "**Gate 3 aprobado**"; else echo "**Gate 3 con $FALLOS fallo(s)**"; fi
} | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"

echo "=== Resultado del Gate 3: $FALLOS comprobación(es) con hallazgos o errores ==="
[ "$FALLOS" -eq 0 ]
