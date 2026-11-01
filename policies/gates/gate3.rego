# Security Gate 3: decisión final sobre el sistema en ejecución (fase 11).
#
# Plan técnico (sección 7.10): OPA evalúa los resultados DAST junto con los de Trivy image y
# los de la fase 9. Si se aprueba, se genera el entregable; si no, el hallazgo vuelve al
# motor de refinamiento.
#
# Entrada (la arma el motor; los hallazgos ya normalizados por el lector SARIF):
#   {
#     "dast":          [hallazgos de OWASP ZAP y Nuclei contra los servicios desplegados],
#     "imagen":        [hallazgos de Trivy image sobre las imágenes de contenedor],
#     "sbom_generado": true,                         # Syft generó el SBOM en CycloneDX
#     "pruebas":       {"total": 16, "fallidas": 0}, # resultado de la fase 9
#     "herramientas":  [{"nombre": "zap", "estado": "ok" | "hallazgos" | "error"}]
#   }
#
# Salida: data.gates.gate3.decision. Además de los bloqueantes, incluye "criterios": la lista
# de reglas evaluadas con su resultado, de modo que también una aprobación queda justificada.
package gates.gate3

import rego.v1

import data.gates.comun

hallazgos := array.concat(object.get(input, "dast", []), object.get(input, "imagen", []))

default aprobado := false

aprobado if count(bloqueantes) == 0

# --- Bloqueantes ---------------------------------------------------------------------------

# Vulnerabilidad crítica o alta explotable en el sistema en marcha.
bloqueantes contains b if {
	some h in object.get(input, "dast", [])
	h.severidad in comun.severidades_bloqueantes
	b := {
		"regla": "gate3.dast",
		"motivo": sprintf("El análisis dinámico (%s) encontró %s de severidad %s en %s", [h.herramienta, h.regla_id, h.severidad, comun.ubicacion(h)]),
		"huella": h.huella,
	}
}

# Vulnerabilidad crítica o alta en el sistema operativo o las librerías de la imagen.
bloqueantes contains b if {
	some h in object.get(input, "imagen", [])
	h.severidad in comun.severidades_bloqueantes
	b := {
		"regla": "gate3.imagen",
		"motivo": sprintf("La imagen de contenedor tiene %s de severidad %s (%s)", [h.regla_id, h.severidad, comun.ubicacion(h)]),
		"huella": h.huella,
	}
}

# Sin SBOM no hay inventario verificable de componentes para el informe de evidencia.
bloqueantes contains b if {
	not sbom_ok
	b := {"regla": "gate3.sbom", "motivo": "No se generó el SBOM (inventario de componentes) de las imágenes"}
}

bloqueantes contains b if {
	not pruebas_ok
	b := {"regla": "gate3.pruebas", "motivo": motivo_pruebas}
}

bloqueantes contains b if {
	some nombre in comun.herramientas_caidas(input.herramientas)
	b := {
		"regla": "gate3.herramienta_caida",
		"motivo": sprintf("La herramienta %s no terminó; sin su resultado el gate no puede aprobarse", [nombre]),
	}
}

advertencias contains a if {
	some h in hallazgos
	h.severidad in comun.severidades_aviso
	a := {
		"regla": "gate3.aviso",
		"motivo": sprintf("Hallazgo %s de %s: %s en %s", [h.severidad, h.herramienta, h.regla_id, comun.ubicacion(h)]),
		"huella": h.huella,
	}
}

# --- Condiciones -----------------------------------------------------------------------------

sbom_ok if input.sbom_generado == true

# Las pruebas deben existir y pasar todas. Si falta el dato, no se aprueba (fallo seguro).
pruebas_ok if {
	input.pruebas.total > 0
	input.pruebas.fallidas == 0
}

motivo_pruebas := "No hay resultado de las pruebas de la fase 9" if not input.pruebas

motivo_pruebas := "La fase 9 no ejecutó ninguna prueba" if {
	input.pruebas
	not input.pruebas.total > 0
}

motivo_pruebas := sprintf("Fallaron %d de %d pruebas de la fase 9", [input.pruebas.fallidas, input.pruebas.total]) if {
	input.pruebas.total > 0
	input.pruebas.fallidas != 0
}

sin_bloqueantes_de(regla) if not regla in {b.regla | some b in bloqueantes}

sin_bloqueantes_de(regla) := false if regla in {b.regla | some b in bloqueantes}

# --- Justificación de la decisión ------------------------------------------------------------

# Cada regla evaluada, haya bloqueado o no: así se justifica tanto un rechazo como una aprobación.
criterios := [
	{
		"regla": "gate3.dast",
		"cumple": sin_bloqueantes_de("gate3.dast"),
		"detalle": "Sin vulnerabilidades críticas o altas en el análisis dinámico (ZAP y Nuclei)",
	},
	{
		"regla": "gate3.imagen",
		"cumple": sin_bloqueantes_de("gate3.imagen"),
		"detalle": "Sin vulnerabilidades críticas o altas en las imágenes de contenedor (Trivy image)",
	},
	{
		"regla": "gate3.sbom",
		"cumple": sin_bloqueantes_de("gate3.sbom"),
		"detalle": "SBOM en CycloneDX generado (Syft)",
	},
	{
		"regla": "gate3.pruebas",
		"cumple": sin_bloqueantes_de("gate3.pruebas"),
		"detalle": "Todas las pruebas de la fase 9 pasan",
	},
	{
		"regla": "gate3.herramienta_caida",
		"cumple": sin_bloqueantes_de("gate3.herramienta_caida"),
		"detalle": "Todas las herramientas del gate terminaron",
	},
]

justificacion := sprintf(
	"Gate 3 aprobado: se cumplen los %d criterios (sin vulnerabilidades críticas o altas en el sistema en marcha ni en las imágenes, SBOM generado y pruebas en verde)",
	[count(criterios)],
) if aprobado

justificacion := sprintf(
	"Gate 3 rechazado: incumple %d de %d criterios (%s)",
	[count(incumplidos), count(criterios), concat(", ", sort(incumplidos))],
) if not aprobado

incumplidos := {c.regla | some c in criterios; not c.cumple}

decision := {
	"gate": 3,
	"aprobado": aprobado,
	"bloqueantes": bloqueantes,
	"advertencias": advertencias,
	"criterios": criterios,
	"conteo": comun.conteo(hallazgos),
	"justificacion": justificacion,
}
