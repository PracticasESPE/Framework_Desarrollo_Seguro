#!/usr/bin/env bash
# Security Gate 2 (inicial): contrato OpenAPI (Spectral) y Docker Compose (Conftest).
#   1. Genera el contrato OpenAPI a partir del código (sin base de datos).
#   2. Autoprueba las reglas propias de Spectral con los ejemplos bueno/malo de spectral/pruebas.
#   3. Analiza el contrato con las reglas OWASP API Top 10 y deja un informe SARIF.
#   4. Conftest: prueba las políticas Rego de policies/integracion y las aplica al Docker Compose.
# Requiere el servicio compilado (fase 3), Spectral instalado (npm ci --prefix spectral) y Docker.
set +e
cd "$(git rev-parse --show-toplevel)" || exit 2

SVC=services/usuarios
SPEC=${SPEC:-salida/openapi/usuarios.json}
INFORME=salida/openapi/spectral.json
SARIF=salida/security/sarif
SPECTRAL=spectral/node_modules/.bin/spectral
REGLAS=spectral/.spectral.yaml
COMPOSE=(docker-compose.dev.yml docker-compose.dast.yml)
POLITICAS=policies/integracion
CONFTEST_IMG=openpolicyagent/conftest:v0.70.1
PAUSA=${PAUSA:-15}
FALLOS=0
FILAS=()

mkdir -p "$SARIF" "$(dirname "$SPEC")"

if [ ! -x "$SPECTRAL" ]; then
  echo "::error::Spectral no está instalado. Ejecuta antes: npm ci --ignore-scripts --prefix spectral"
  exit 2
fi

# registrar "Nombre" CODIGO_DE_SALIDA CODIGO_DE_HALLAZGOS
#   0 = OK; CODIGO_DE_HALLAZGOS = la herramienta funcionó y encontró problemas; otro = error.
registrar() {
  local estado
  if [ "$2" -eq 0 ]; then
    estado="OK"
  elif [ "$2" -eq "$3" ]; then
    estado="HALLAZGOS"
    FALLOS=$((FALLOS+1))
  else
    estado="ERROR DE LA HERRAMIENTA (codigo $2)"
    FALLOS=$((FALLOS+1))
  fi
  FILAS+=("| $1 | $estado |")
}

# Códigos de las reglas propias (fw-*) que activa un documento, ordenados y sin repetir.
reglas_propias() {
  "$SPECTRAL" lint "$1" --ruleset "$REGLAS" -f json --quiet 2>/dev/null \
    | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const r=JSON.parse(s||'[]');console.log([...new Set(r.map(x=>String(x.code)).filter(c=>c.startsWith('fw-')))].sort().join(' '))})"
}

conftest() { docker run --rm -v "$PWD:/project" -w /project "$CONFTEST_IMG" "$@"; }

echo "=== 1/4 Generar el contrato OpenAPI del servicio ==="
( cd "$SVC" && node dist/openapi/generar-openapi.js "$OLDPWD/$SPEC" )
registrar "Generar el contrato OpenAPI" $? 99

echo "=== 2/4 Autoprueba de las reglas propias (spectral/pruebas) ==="
ESPERADO="fw-respuesta-sin-campos-sensibles fw-ruta-con-prefijo-api fw-sin-secretos-en-query fw-version-semantica"
MALO=$(reglas_propias spectral/pruebas/malo.json)
BUENO=$(reglas_propias spectral/pruebas/bueno.json)
echo "malo.json activa : ${MALO:-ninguna}"
echo "bueno.json activa: ${BUENO:-ninguna}"
if [ "$MALO" = "$ESPERADO" ] && [ -z "$BUENO" ]; then
  registrar "Autoprueba de las reglas propias" 0 1
else
  echo "::error::Las reglas propias no detectan lo esperado. Esperado en malo.json: $ESPERADO"
  registrar "Autoprueba de las reglas propias" 1 1
fi

echo "=== 3/4 Spectral: reglas OWASP API Top 10 sobre el contrato ==="
if [ -s "$SPEC" ]; then
  "$SPECTRAL" lint "$SPEC" --ruleset "$REGLAS" -f stylish -f json --output.json "$INFORME"
  registrar "Spectral (OWASP API Top 10 y reglas propias)" $? 1
  if ! node spectral/convertir-a-sarif.mjs "$INFORME" "$SARIF/spectral.sarif"; then
    echo "::error::No se pudo generar spectral.sarif"
    FALLOS=$((FALLOS+1))
  fi
else
  echo "::error::No existe $SPEC; no se puede analizar el contrato"
  registrar "Spectral (OWASP API Top 10 y reglas propias)" 2 1
fi

echo "=== 4/4 Conftest: políticas de Docker Compose ($POLITICAS) ==="
for intento in 1 2 3; do
  docker pull --quiet "$CONFTEST_IMG" >/dev/null && break
  if [ "$intento" -lt 3 ]; then
    echo "::warning::Reintento $intento de 2 al descargar $CONFTEST_IMG"
    sleep "$PAUSA"
  fi
done
echo "--- Pruebas de las políticas (conftest verify) ---"
conftest verify --policy "$POLITICAS"
registrar "Conftest: pruebas de las políticas" $? 1
echo "--- Análisis de ${COMPOSE[*]} (conftest test) ---"
conftest test "${COMPOSE[@]}" --policy "$POLITICAS" --namespace integracion.compose
registrar "Conftest (Docker Compose)" $? 1
conftest test "${COMPOSE[@]}" --policy "$POLITICAS" --namespace integracion.compose \
  --output sarif --no-fail > "$SARIF/conftest.sarif" 2>/dev/null \
  || echo "::warning::No se pudo generar conftest.sarif"

# Los SARIF vacíos (herramienta caída) se eliminan: GitHub los rechaza.
find "$SARIF" -type f -empty -delete

{
  echo "## Security Gate 2 (inicial)"
  echo
  echo "| Comprobación | Resultado |"
  echo "|---|---|"
  printf '%s\n' "${FILAS[@]}"
  echo
  if [ "$FALLOS" -eq 0 ]; then echo "**Gate 2 aprobado**"; else echo "**Gate 2 con $FALLOS fallo(s)**"; fi
} | tee -a "${GITHUB_STEP_SUMMARY:-/dev/null}"

echo "=== Resultado del Gate 2: $FALLOS comprobación(es) con hallazgos o errores ==="
[ "$FALLOS" -eq 0 ]
