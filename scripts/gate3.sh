#!/usr/bin/env bash
# Security Gate 3 (inicial): imagen de contenedor y análisis dinámico del servicio de referencia.
#   1. Exporta la imagen a un archivo, para analizarla sin dar acceso al socket de Docker.
#   2. Trivy image: vulnerabilidades del sistema operativo y de las librerías (SARIF).
#   3. Syft: SBOM en CycloneDX, el inventario verificable de componentes (sbom.json).
#   4. Levanta un entorno desechable (docker-compose.dast.yml) y comprueba la autenticación.
#   5. OWASP ZAP: ataca la API a partir de su contrato OpenAPI, con token y límite de tiempo.
#      Su reporte se convierte a SARIF (dast/zap-a-sarif.mjs).
#   6. Nuclei: plantillas de CVE conocidas, configuraciones erróneas y paneles expuestos.
# La decisión final la tomará OPA (gate3.rego).
# Requiere la imagen construida (fase 10), el contrato OpenAPI (fase 8) y Docker.
set +e
cd "$(git rev-parse --show-toplevel)" || exit 2

SVC=services/usuarios
IMAGEN=${IMAGEN:-fw-usuarios:ci}
SARIF=salida/security/sarif
SBOM=salida/sbom/sbom.json
DIR_IMAGEN=salida/imagen
ARCHIVO_IMAGEN=$DIR_IMAGEN/imagen.tar
CACHE=.trivy-cache
PAUSA=${PAUSA:-15}
TRIVY_IMG=aquasec/trivy:0.71.1
SYFT_IMG=anchore/syft:v1.54.1
ZAP_IMG=zaproxy/zap-stable:2.17.0
NUCLEI_IMG=projectdiscovery/nuclei:v3.11.1
HALLAZGO=10   # codigo de salida propio para "hay hallazgos"
COMPOSE_DAST=docker-compose.dast.yml
RED_DAST=framework-dast
OBJETIVO=http://usuarios:3000
DIR_DAST=salida/dast
CONTRATO=salida/openapi/usuarios.json
# Límite del escaneo activo de ZAP: menor que los 5 minutos de vida del token de Keycloak.
LIMITE_ZAP_MIN=4

mkdir -p "$SARIF" "$(dirname "$SBOM")" "$DIR_IMAGEN" "$CACHE" "$DIR_DAST"
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

# Para los escaneos DAST: tardan minutos y repetirlos agotaría el tiempo del job.
sin_reintento() {
  local nombre="$1" codigo estado
  shift
  "$@"
  codigo=$?
  if [ "$codigo" -eq 0 ]; then
    estado="OK"
  elif [ "$codigo" -eq "$HALLAZGO" ]; then
    estado="HALLAZGOS"
    FALLOS=$((FALLOS+1))
  else
    estado="ERROR DE LA HERRAMIENTA (codigo $codigo)"
    FALLOS=$((FALLOS+1))
  fi
  FILAS+=("| $nombre | $estado | 1 |")
}

trivy() { docker run --rm -v "$PWD:/work" -v "$PWD/$CACHE:/root/.cache/trivy" -w /work "$TRIVY_IMG" "$@"; }
syft() { docker run --rm -v "$PWD:/work" -w /work "$SYFT_IMG" "$@"; }
dc() { docker compose -f "$COMPOSE_DAST" "$@"; }

apagar_entorno() { dc down --volumes --remove-orphans >/dev/null 2>&1; }

# Entorno desechable: contraseñas nuevas en cada ejecución; no son secretos del proyecto.
levantar_entorno() {
  export DAST_DB_PASSWORD DAST_KEYCLOAK_ADMIN_PASSWORD KEYCLOAK_PRUEBA_PASSWORD
  DAST_DB_PASSWORD=$(openssl rand -hex 24)
  DAST_KEYCLOAK_ADMIN_PASSWORD=$(openssl rand -hex 24)
  KEYCLOAK_PRUEBA_PASSWORD=$(openssl rand -hex 24)
  if ! dc up -d --wait --wait-timeout 240; then
    dc logs --tail 30
    return 1
  fi
  cat "$SVC"/prisma/migrations/*/migration.sql \
    | dc exec -T usuarios-db psql -q -v ON_ERROR_STOP=1 -U usuarios -d usuarios
}

# Pide un token a Keycloak desde dentro de la red, para que su emisor coincida con el del
# servicio, y exige un 200: sin autenticación el escaneo solo vería 401 y saldría "limpio".
obtener_token() {
  local token
  token=$(dc exec -T -e "CLAVE=$KEYCLOAK_PRUEBA_PASSWORD" usuarios /nodejs/bin/node -e "
    (async () => {
      const r = await fetch('http://keycloak:8080/realms/framework/protocol/openid-connect/token', {
        method: 'POST',
        body: new URLSearchParams({ grant_type: 'password', client_id: 'usuarios-cli', username: 'ana', password: process.env.CLAVE }),
      });
      if (!r.ok) { console.error('Keycloak no entregó el token: HTTP ' + r.status); process.exit(1); }
      const { access_token: t } = await r.json();
      const c = await fetch('http://localhost:3000/api/usuarios', { headers: { Authorization: 'Bearer ' + t } });
      if (c.status !== 200) { console.error('El servicio rechazó el token: HTTP ' + c.status); process.exit(1); }
      console.log(t);
    })();
  ") || return 1
  echo "::add-mask::$token" >&2
  echo "$token"
}

# Copia del contrato con la dirección interna del servicio y la configuración de reglas.
preparar_zap() {
  node -e "
    const fs = require('fs');
    const d = JSON.parse(fs.readFileSync(process.argv[1], 'utf8'));
    d.servers = [{ url: process.argv[3] }];
    fs.writeFileSync(process.argv[2], JSON.stringify(d, null, 2));
  " "$CONTRATO" "$DIR_DAST/openapi-dast.json" "$OBJETIVO" || return 1
  cp dast/zap-reglas.conf "$DIR_DAST/"
  chmod -R a+rwX "$DIR_DAST"   # ZAP corre con su propio usuario, no con el del runner
}

# Devuelve 0 sin hallazgos, $HALLAZGO con un riesgo alto o una regla FAIL, otro valor si falla.
escanear_zap() {
  local codigo altos
  preparar_zap || return 2
  ZAP_AUTH_HEADER_VALUE="Bearer $(obtener_token)"
  if [ "$ZAP_AUTH_HEADER_VALUE" = "Bearer " ]; then return 2; fi
  export ZAP_AUTH_HEADER_VALUE
  timeout 8m docker run --rm --network "$RED_DAST" -v "$PWD/$DIR_DAST:/zap/wrk:rw" \
    -e ZAP_AUTH_HEADER=Authorization -e ZAP_AUTH_HEADER_VALUE -e ZAP_AUTH_HEADER_SITE=usuarios \
    "$ZAP_IMG" zap-api-scan.py -t openapi-dast.json -f openapi -c zap-reglas.conf \
    -J zap.json -r zap.html -I -T 3 \
    -z "-config scanner.maxScanDurationInMins=$LIMITE_ZAP_MIN -config scanner.maxRuleDurationInMins=1"
  codigo=$?
  unset ZAP_AUTH_HEADER_VALUE
  if [ ! -s "$DIR_DAST/zap.json" ]; then return 2; fi
  node dast/zap-a-sarif.mjs "$DIR_DAST/zap.json" "$SARIF/zap.sarif" dast/zap-reglas.conf || return 2
  altos=$(node -e "
    const z = JSON.parse(require('fs').readFileSync(process.argv[1], 'utf8'));
    const c = { 3: 0, 2: 0, 1: 0, 0: 0 };
    for (const s of z.site) for (const a of s.alerts) c[a.riskcode] += 1;
    console.error('ZAP: alto=' + c[3] + ' medio=' + c[2] + ' bajo=' + c[1] + ' informativo=' + c[0]);
    console.log(c[3]);
  " "$DIR_DAST/zap.json")
  if [ "$codigo" -eq 1 ] || [ "${altos:-0}" -gt 0 ]; then return "$HALLAZGO"; fi
  return "$codigo"
}

# Devuelve 0 sin hallazgos, $HALLAZGO con severidad alta o crítica, otro valor si falla.
escanear_nuclei() {
  local token codigo graves
  token=$(obtener_token) || return 2
  # -nmhe: por defecto, tras 30 errores Nuclei abandona el objetivo y aun así termina con
  # "0 matches" y código 0, como si hubiera escaneado todo.
  timeout 6m docker run --rm --network "$RED_DAST" -v "$PWD/$DIR_DAST:/out" "$NUCLEI_IMG" \
    -u "$OBJETIVO" -H "Authorization: Bearer $token" \
    -tags cve,misconfig,exposure,panel -severity low,medium,high,critical \
    -ni -nmhe -rl 100 -timeout 10 -retries 1 -stats -si 30 \
    -jsonl-export /out/nuclei.jsonl -sarif-export /out/nuclei.sarif 2>&1 | tee "$DIR_DAST/nuclei.log"
  codigo=${PIPESTATUS[0]}
  if [ "$codigo" -ne 0 ]; then return "$codigo"; fi
  if grep -q "Skipped ${OBJETIVO#http://}" "$DIR_DAST/nuclei.log"; then
    echo "::error::Nuclei abandonó el objetivo: el escaneo está incompleto y no cuenta como limpio"
    return 3
  fi
  # Nuclei solo crea el SARIF cuando hay coincidencias.
  if [ -s "$DIR_DAST/nuclei.sarif" ]; then cp "$DIR_DAST/nuclei.sarif" "$SARIF/"; fi
  graves=$(node -e "
    const fs = require('fs');
    const ruta = process.argv[1];
    const filas = fs.existsSync(ruta) ? fs.readFileSync(ruta, 'utf8').split('\n').filter(Boolean) : [];
    const c = {};
    for (const f of filas) { const s = JSON.parse(f).info.severity; c[s] = (c[s] || 0) + 1; }
    console.error('Nuclei: ' + filas.length + ' coincidencias ' + JSON.stringify(c));
    console.log((c.critical || 0) + (c.high || 0));
  " "$DIR_DAST/nuclei.jsonl")
  if [ "${graves:-0}" -gt 0 ]; then return "$HALLAZGO"; fi
}

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

echo "=== 0/6 Preparacion: descarga de las imagenes de las herramientas ==="
for img in "$TRIVY_IMG" "$SYFT_IMG" "$ZAP_IMG" "$NUCLEI_IMG"; do
  if ! reintentar docker pull --quiet "$img" >/dev/null; then
    echo "::error::No se pudo descargar $img"
    FALLOS=$((FALLOS+1))
    FILAS+=("| descarga de $img | ERROR DE LA HERRAMIENTA | 3 |")
  fi
done
echo "--- Pruebas del conversor de ZAP a SARIF ---"
ejecutar "Conversor ZAP a SARIF (pruebas)" 1 node --test dast/zap-a-sarif.test.mjs

echo "=== 1/6 Exportar la imagen $IMAGEN ==="
if docker save -o "$ARCHIVO_IMAGEN" "$IMAGEN"; then
  FILAS+=("| Exportar la imagen | OK | 1 |")
else
  echo "::error::No existe la imagen $IMAGEN; ejecuta antes la fase 10 (docker build)"
  FILAS+=("| Exportar la imagen | ERROR DE LA HERRAMIENTA | 1 |")
  FALLOS=$((FALLOS+1))
fi

if [ -s "$ARCHIVO_IMAGEN" ]; then
  echo "=== 2/6 Trivy image: vulnerabilidades del sistema operativo y de las librerias ==="
  # --table-mode detailed: solo las tablas con hallazgos, sin una fila por cada librería limpia.
  ejecutar "Trivy image" "$HALLAZGO" trivy image --input "$ARCHIVO_IMAGEN" --scanners vuln \
    --severity HIGH,CRITICAL --exit-code "$HALLAZGO" --timeout 10m --table-mode detailed
  reintentar trivy image --input "$ARCHIVO_IMAGEN" --scanners vuln --severity HIGH,CRITICAL \
    --timeout 10m --format sarif --output "$SARIF/trivy-image.sarif" >/dev/null \
    || echo "::warning::No se pudo generar trivy-image.sarif"
  contar_hallazgos

  echo "=== 3/6 Syft: SBOM en CycloneDX ==="
  ejecutar "Syft (SBOM en CycloneDX)" 99 syft "docker-archive:$ARCHIVO_IMAGEN" \
    --quiet --output "cyclonedx-json=$SBOM"
  if ! validar_sbom; then
    echo "::error::$SBOM no es un SBOM CycloneDX con componentes"
    FILAS+=("| Validar el SBOM | HALLAZGOS | 1 |")
    FALLOS=$((FALLOS+1))
  else
    FILAS+=("| Validar el SBOM | OK | 1 |")
  fi

  echo "=== 4/6 Entorno de prueba: servicio, PostgreSQL y Keycloak ==="
  trap apagar_entorno EXIT
  if levantar_entorno && obtener_token >/dev/null; then
    FILAS+=("| Entorno de prueba y autenticación | OK | 1 |")

    echo "=== 5/6 OWASP ZAP: escaneo activo de la API (limite: $LIMITE_ZAP_MIN min) ==="
    sin_reintento "OWASP ZAP (API scan con token)" escanear_zap

    echo "=== 6/6 Nuclei: CVE, configuraciones erroneas y paneles expuestos ==="
    sin_reintento "Nuclei (con token)" escanear_nuclei
  else
    echo "::error::El entorno de prueba no arrancó o el token no funciona: no se ejecuta el DAST"
    FILAS+=("| Entorno de prueba y autenticación | ERROR DE LA HERRAMIENTA | 1 |")
    FALLOS=$((FALLOS+1))
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
