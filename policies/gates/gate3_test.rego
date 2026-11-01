package gates.gate3_test

import rego.v1

import data.gates.gate3

limpio := {
	"dast": [],
	"imagen": [],
	"sbom_generado": true,
	"pruebas": {"total": 16, "fallidas": 0},
	"herramientas": [
		{"nombre": "zap", "estado": "ok"},
		{"nombre": "nuclei", "estado": "ok"},
		{"nombre": "trivy image", "estado": "ok"},
	],
}

hallazgo(herramienta, severidad, archivo) := {
	"herramienta": herramienta,
	"regla_id": "regla-x",
	"severidad": severidad,
	"archivo": archivo,
	"linea_inicio": null,
	"huella": sprintf("%s-%s", [herramienta, severidad]),
}

reglas(decision) := {b.regla | some b in decision.bloqueantes}

criterio(decision, regla) := c if {
	some c in decision.criterios
	c.regla == regla
}

test_sistema_limpio_se_aprueba_con_todos_los_criterios if {
	d := gate3.decision with input as limpio
	d.aprobado
	count(d.bloqueantes) == 0
	count(d.criterios) == 5
	every c in d.criterios { c.cumple }
	startswith(d.justificacion, "Gate 3 aprobado: se cumplen los 5 criterios")
}

test_vulnerabilidad_alta_en_dast_bloquea if {
	entrada := object.union(limpio, {"dast": [hallazgo("zap", "alta", "/api/usuarios")]})
	d := gate3.decision with input as entrada
	not d.aprobado
	reglas(d) == {"gate3.dast"}
	some b in d.bloqueantes
	contains(b.motivo, "zap")
	contains(b.motivo, "/api/usuarios")
	not criterio(d, "gate3.dast").cumple
	criterio(d, "gate3.imagen").cumple
}

test_vulnerabilidad_critica_en_la_imagen_bloquea if {
	entrada := object.union(limpio, {"imagen": [hallazgo("trivy", "critica", "fw-usuarios:ci (debian 12)")]})
	d := gate3.decision with input as entrada
	reglas(d) == {"gate3.imagen"}
	d.conteo.critica == 1
}

test_hallazgos_medios_solo_avisan if {
	entrada := object.union(limpio, {
		"dast": [hallazgo("nuclei", "media", "/api/usuarios")],
		"imagen": [hallazgo("trivy", "baja", "fw-usuarios:ci")],
	})
	d := gate3.decision with input as entrada
	d.aprobado
	count(d.advertencias) == 2
}

test_sin_sbom_bloquea if {
	d := gate3.decision with input as object.union(limpio, {"sbom_generado": false})
	reglas(d) == {"gate3.sbom"}
	not criterio(d, "gate3.sbom").cumple
}

test_sin_dato_de_sbom_bloquea_por_fallo_seguro if {
	d := gate3.decision with input as object.remove(limpio, ["sbom_generado"])
	reglas(d) == {"gate3.sbom"}
}

test_pruebas_fallidas_bloquean_con_el_detalle if {
	d := gate3.decision with input as object.union(limpio, {"pruebas": {"total": 16, "fallidas": 2}})
	reglas(d) == {"gate3.pruebas"}
	some b in d.bloqueantes
	b.motivo == "Fallaron 2 de 16 pruebas de la fase 9"
}

test_sin_pruebas_ejecutadas_bloquea if {
	d := gate3.decision with input as object.union(limpio, {"pruebas": {"total": 0, "fallidas": 0}})
	some b in d.bloqueantes
	b.motivo == "La fase 9 no ejecutó ninguna prueba"
}

test_sin_resultado_de_pruebas_bloquea_por_fallo_seguro if {
	d := gate3.decision with input as object.remove(limpio, ["pruebas"])
	some b in d.bloqueantes
	b.motivo == "No hay resultado de las pruebas de la fase 9"
}

test_herramienta_caida_bloquea if {
	entrada := object.union(limpio, {"herramientas": [{"nombre": "zap", "estado": "error"}]})
	d := gate3.decision with input as entrada
	reglas(d) == {"gate3.herramienta_caida"}
}

test_sin_listas_de_hallazgos_no_falla if {
	d := gate3.decision with input as object.remove(limpio, ["dast", "imagen"])
	d.aprobado
	d.conteo.alta == 0
}

test_el_rechazo_nombra_los_criterios_incumplidos if {
	entrada := object.union(limpio, {
		"dast": [hallazgo("zap", "alta", "/api")],
		"sbom_generado": false,
	})
	d := gate3.decision with input as entrada
	d.justificacion == "Gate 3 rechazado: incumple 2 de 5 criterios (gate3.dast, gate3.sbom)"
}
