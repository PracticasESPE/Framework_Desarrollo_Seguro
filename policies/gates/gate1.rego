# Security Gate 1: decisión de aceptación del análisis estático (fase 4).
#
# Entrada (la arma el motor con los SARIF del Gate 1 ya normalizados):
#   {
#     "hallazgos":      [{"herramienta", "regla_id", "severidad", "archivo", "linea_inicio", "cwe", "huella"}],
#     "compilacion_ok": true,
#     "herramientas":   [{"nombre": "semgrep", "estado": "ok" | "hallazgos" | "error"}]
#   }
#
# Salida: data.gates.gate1.decision = {gate, aprobado, bloqueantes, advertencias, conteo, justificacion}.
# Cada bloqueante lleva la regla que lo justifica (principio P1: las reglas deciden, no el LLM).
package gates.gate1

import rego.v1

import data.gates.comun

default aprobado := false

aprobado if count(bloqueantes) == 0

# Hallazgos críticos o altos de cualquier herramienta.
bloqueantes contains b if {
	some h in input.hallazgos
	h.severidad in comun.severidades_bloqueantes
	b := {
		"regla": "gate1.severidad",
		"motivo": sprintf("Hallazgo %s de %s: %s en %s", [h.severidad, h.herramienta, h.regla_id, comun.ubicacion(h)]),
		"huella": h.huella,
	}
}

# Un secreto expuesto bloquea siempre, sea cual sea la severidad que le asigne la herramienta.
bloqueantes contains b if {
	some h in input.hallazgos
	h.herramienta == "gitleaks"
	b := {
		"regla": "gate1.secreto",
		"motivo": sprintf("Secreto expuesto detectado por Gitleaks en %s", [comun.ubicacion(h)]),
		"huella": h.huella,
	}
}

# Código que no compila no se analiza. Si el dato falta, se asume que no compila (fallo seguro).
bloqueantes contains b if {
	not input.compilacion_ok == true
	b := {"regla": "gate1.compilacion", "motivo": "El código no compila (tsc --noEmit falló o no se ejecutó)"}
}

bloqueantes contains b if {
	some nombre in comun.herramientas_caidas(input.herramientas)
	b := {
		"regla": "gate1.herramienta_caida",
		"motivo": sprintf("La herramienta %s no terminó; sin su resultado el gate no puede aprobarse", [nombre]),
	}
}

# Hallazgos medios y bajos: se informan pero no bloquean.
advertencias contains a if {
	some h in input.hallazgos
	h.severidad in comun.severidades_aviso
	a := {
		"regla": "gate1.aviso",
		"motivo": sprintf("Hallazgo %s de %s: %s en %s", [h.severidad, h.herramienta, h.regla_id, comun.ubicacion(h)]),
		"huella": h.huella,
	}
}

# Cada regla evaluada, haya bloqueado o no: justifica tanto un rechazo como una aprobación.
criterios := [
	{
		"regla": "gate1.severidad",
		"cumple": comun.cumple("gate1.severidad", bloqueantes),
		"detalle": "Sin hallazgos críticos o altos en el análisis estático",
	},
	{
		"regla": "gate1.secreto",
		"cumple": comun.cumple("gate1.secreto", bloqueantes),
		"detalle": "Sin secretos expuestos en el repositorio (Gitleaks)",
	},
	{
		"regla": "gate1.compilacion",
		"cumple": comun.cumple("gate1.compilacion", bloqueantes),
		"detalle": "El código compila (tsc --noEmit)",
	},
	{
		"regla": "gate1.herramienta_caida",
		"cumple": comun.cumple("gate1.herramienta_caida", bloqueantes),
		"detalle": "Todas las herramientas del gate terminaron",
	},
]

justificacion := "Gate 1 aprobado: sin hallazgos críticos o altos, sin secretos expuestos y el código compila" if aprobado

justificacion := sprintf(
	"Gate 1 rechazado: incumple %d de %d criterios (%s)",
	[count(incumplidos), count(criterios), concat(", ", sort(incumplidos))],
) if not aprobado

incumplidos := comun.criterios_incumplidos(criterios)

decision := {
	"gate": 1,
	"aprobado": aprobado,
	"bloqueantes": bloqueantes,
	"advertencias": advertencias,
	"criterios": criterios,
	"conteo": comun.conteo(input.hallazgos),
	"justificacion": justificacion,
}
