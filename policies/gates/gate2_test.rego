package gates.gate2_test

import rego.v1

import data.gates.gate2

limpio := {
	"hallazgos": [],
	"contrato_ok": true,
	"herramientas": [{"nombre": "spectral", "estado": "ok"}, {"nombre": "conftest", "estado": "ok"}],
}

hallazgo(herramienta, severidad, mensaje) := {
	"herramienta": herramienta,
	"regla_id": "regla-x",
	"mensaje": mensaje,
	"severidad": severidad,
	"archivo": "docker-compose.dev.yml",
	"linea_inicio": null,
	"huella": sprintf("%s-%s", [herramienta, severidad]),
}

con_hallazgos(lista) := object.union(limpio, {"hallazgos": lista})

reglas(decision) := {b.regla | some b in decision.bloqueantes}

test_sin_hallazgos_se_aprueba if {
	d := gate2.decision with input as limpio
	d.aprobado
	d.gate == 2
	startswith(d.justificacion, "Gate 2 aprobado")
}

test_error_de_spectral_en_el_contrato_bloquea if {
	d := gate2.decision with input as con_hallazgos([hallazgo("spectral", "alta", "Operación sin seguridad declarada")])
	not d.aprobado
	reglas(d) == {"gate2.contrato_api"}
}

test_deny_de_conftest_bloquea_con_su_mensaje if {
	mensaje := "[usuarios] privileged: true da al contenedor acceso casi total al host"
	d := gate2.decision with input as con_hallazgos([hallazgo("conftest", "alta", mensaje)])
	not d.aprobado
	some b in d.bloqueantes
	b.regla == "gate2.politica_compose"
	contains(b.motivo, "privileged: true")
}

test_warn_de_conftest_solo_avisa if {
	d := gate2.decision with input as con_hallazgos([hallazgo("conftest", "media", "[neo4j] sin healthcheck")])
	d.aprobado
	count(d.advertencias) == 1
	some a in d.advertencias
	contains(a.motivo, "docker-compose.dev.yml")
}

test_otra_herramienta_con_hallazgo_alto_bloquea if {
	d := gate2.decision with input as con_hallazgos([hallazgo("otra", "critica", "x")])
	reglas(d) == {"gate2.severidad"}
}

test_sin_contrato_openapi_bloquea if {
	d := gate2.decision with input as object.union(limpio, {"contrato_ok": false})
	reglas(d) == {"gate2.contrato"}
}

test_sin_dato_del_contrato_bloquea_por_fallo_seguro if {
	d := gate2.decision with input as object.remove(limpio, ["contrato_ok"])
	not d.aprobado
}

test_herramienta_caida_bloquea if {
	caida := object.union(limpio, {"herramientas": [{"nombre": "conftest", "estado": "error"}]})
	d := gate2.decision with input as caida
	reglas(d) == {"gate2.herramienta_caida"}
}

test_conteo_por_severidad if {
	entrada := con_hallazgos([
		hallazgo("spectral", "alta", "a"),
		hallazgo("conftest", "media", "b"),
		hallazgo("conftest", "media", "c"),
	])
	d := gate2.decision with input as entrada
	d.conteo.alta == 1
	d.conteo.media == 2
}
