# Security Gate 2: decisión de aceptación de la seguridad de integración (fase 8).
#
# Entrada (la arma el motor con los SARIF de Spectral y Conftest ya normalizados):
#   {
#     "hallazgos":    [{"herramienta", "regla_id", "severidad", "archivo", "linea_inicio", "huella"}],
#     "contrato_ok":  true,     # se pudo generar el contrato OpenAPI del servicio
#     "herramientas": [{"nombre": "spectral", "estado": "ok" | "hallazgos" | "error"}]
#   }
#
# En los SARIF, un "deny" de Conftest y un error de Spectral llegan como severidad alta;
# un "warn" de Conftest y un aviso de Spectral, como media.
#
# Salida: data.gates.gate2.decision = {gate, aprobado, bloqueantes, advertencias, conteo, justificacion}.
package gates.gate2

import rego.v1

import data.gates.comun

default aprobado := false

aprobado if count(bloqueantes) == 0

# Regla de seguridad del contrato OpenAPI incumplida (OWASP API Top 10 o reglas propias).
bloqueantes contains b if {
	some h in input.hallazgos
	h.herramienta == "spectral"
	h.severidad in comun.severidades_bloqueantes
	b := {
		"regla": "gate2.contrato_api",
		"motivo": sprintf("El contrato OpenAPI incumple %s en %s", [h.regla_id, comun.ubicacion(h)]),
		"huella": h.huella,
	}
}

# Política de Docker Compose incumplida (privilegios, red, secretos, Database per Service...).
bloqueantes contains b if {
	some h in input.hallazgos
	h.herramienta == "conftest"
	h.severidad in comun.severidades_bloqueantes
	b := {
		"regla": "gate2.politica_compose",
		"motivo": sprintf("La configuración de despliegue incumple una política: %s", [h.mensaje]),
		"huella": h.huella,
	}
}

# Cualquier otra herramienta de integración con hallazgos críticos o altos.
bloqueantes contains b if {
	some h in input.hallazgos
	not h.herramienta in {"spectral", "conftest"}
	h.severidad in comun.severidades_bloqueantes
	b := {
		"regla": "gate2.severidad",
		"motivo": sprintf("Hallazgo %s de %s: %s en %s", [h.severidad, h.herramienta, h.regla_id, comun.ubicacion(h)]),
		"huella": h.huella,
	}
}

# Sin contrato OpenAPI no se puede revisar la API. Si el dato falta, se asume que falló.
bloqueantes contains b if {
	not input.contrato_ok == true
	b := {"regla": "gate2.contrato", "motivo": "No se pudo generar el contrato OpenAPI del servicio"}
}

bloqueantes contains b if {
	some nombre in comun.herramientas_caidas(input.herramientas)
	b := {
		"regla": "gate2.herramienta_caida",
		"motivo": sprintf("La herramienta %s no terminó; sin su resultado el gate no puede aprobarse", [nombre]),
	}
}

advertencias contains a if {
	some h in input.hallazgos
	h.severidad in comun.severidades_aviso
	a := {
		"regla": "gate2.aviso",
		"motivo": sprintf("Hallazgo %s de %s: %s en %s", [h.severidad, h.herramienta, h.regla_id, comun.ubicacion(h)]),
		"huella": h.huella,
	}
}

justificacion := "Gate 2 aprobado: el contrato OpenAPI y la configuración de despliegue cumplen las políticas" if aprobado

justificacion := sprintf("Gate 2 rechazado: %d bloqueante(s)", [count(bloqueantes)]) if not aprobado

decision := {
	"gate": 2,
	"aprobado": aprobado,
	"bloqueantes": bloqueantes,
	"advertencias": advertencias,
	"conteo": comun.conteo(input.hallazgos),
	"justificacion": justificacion,
}
