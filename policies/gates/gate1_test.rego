package gates.gate1_test

import rego.v1

import data.gates.gate1

limpio := {
	"hallazgos": [],
	"compilacion_ok": true,
	"herramientas": [{"nombre": "semgrep", "estado": "ok"}, {"nombre": "gitleaks", "estado": "ok"}],
}

hallazgo(herramienta, severidad) := {
	"herramienta": herramienta,
	"regla_id": "regla-x",
	"severidad": severidad,
	"archivo": "services/usuarios/src/usuarios.service.ts",
	"linea_inicio": 42,
	"cwe": ["CWE-89"],
	"huella": sprintf("%s-%s", [herramienta, severidad]),
}

con_hallazgos(lista) := object.union(limpio, {"hallazgos": lista})

reglas(decision) := {b.regla | some b in decision.bloqueantes}

test_sin_hallazgos_se_aprueba if {
	d := gate1.decision with input as limpio
	d.aprobado
	count(d.bloqueantes) == 0
	startswith(d.justificacion, "Gate 1 aprobado")
}

test_hallazgo_critico_bloquea if {
	d := gate1.decision with input as con_hallazgos([hallazgo("trivy", "critica")])
	not d.aprobado
	reglas(d) == {"gate1.severidad"}
}

test_hallazgo_alto_bloquea_y_lleva_ubicacion if {
	d := gate1.decision with input as con_hallazgos([hallazgo("semgrep oss", "alta")])
	not d.aprobado
	some b in d.bloqueantes
	contains(b.motivo, "usuarios.service.ts:42")
	b.huella == "semgrep oss-alta"
}

test_hallazgos_medios_y_bajos_solo_avisan if {
	d := gate1.decision with input as con_hallazgos([hallazgo("hadolint", "media"), hallazgo("trivy", "baja")])
	d.aprobado
	count(d.advertencias) == 2
	d.conteo.media == 1
	d.conteo.baja == 1
}

test_un_secreto_bloquea_aunque_su_severidad_sea_media if {
	d := gate1.decision with input as con_hallazgos([hallazgo("gitleaks", "media")])
	not d.aprobado
	reglas(d) == {"gate1.secreto"}
}

test_codigo_que_no_compila_bloquea if {
	d := gate1.decision with input as object.union(limpio, {"compilacion_ok": false})
	not d.aprobado
	reglas(d) == {"gate1.compilacion"}
}

test_sin_dato_de_compilacion_bloquea_por_fallo_seguro if {
	d := gate1.decision with input as object.remove(limpio, ["compilacion_ok"])
	not d.aprobado
	reglas(d) == {"gate1.compilacion"}
}

test_herramienta_caida_bloquea if {
	caida := object.union(limpio, {"herramientas": [{"nombre": "trivy fs", "estado": "error"}]})
	d := gate1.decision with input as caida
	not d.aprobado
	some b in d.bloqueantes
	b.regla == "gate1.herramienta_caida"
	contains(b.motivo, "trivy fs")
}

test_varios_bloqueantes_se_cuentan_en_la_justificacion if {
	entrada := object.union(con_hallazgos([hallazgo("trivy", "alta")]), {"compilacion_ok": false})
	d := gate1.decision with input as entrada
	reglas(d) == {"gate1.severidad", "gate1.compilacion"}
	d.justificacion == "Gate 1 rechazado: 2 bloqueante(s)"
}

test_hallazgo_sin_ubicacion if {
	sin_archivo := object.union(hallazgo("trivy", "alta"), {"archivo": null, "linea_inicio": null})
	d := gate1.decision with input as con_hallazgos([sin_archivo])
	some b in d.bloqueantes
	contains(b.motivo, "sin ubicación")
}

test_conteo_incluye_todas_las_severidades if {
	d := gate1.decision with input as limpio
	d.conteo == {"critica": 0, "alta": 0, "media": 0, "baja": 0, "info": 0}
}
