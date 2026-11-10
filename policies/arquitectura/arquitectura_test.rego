package arquitectura_test

import rego.v1

import data.arquitectura

# Patrones como los de knowledge_base/patrones (el motor los lee de ahí; aquí van fijos).
patrones_kb := [
	{
		"id": "arq.gateway.001", "patron": "api_gateway", "implementacion": "traefik",
		"controles_asociados": ["ASVS-V4.1.1"], "cwe_mitigadas": ["CWE-284"],
		"aplica_cuando": [
			{"etiqueta": "punto_unico_acceso"}, {"etiqueta": "autenticacion_centralizada"},
			{"numero_servicios_minimo": 2},
		],
	},
	{
		"id": "arq.bff.001", "patron": "bff", "implementacion": "nestjs",
		"controles_asociados": ["ASVS-V4.1.1"], "cwe_mitigadas": ["CWE-200"],
		"aplica_cuando": [
			{"etiqueta": "varios_tipos_de_cliente"}, {"etiqueta": "agregacion_de_datos"},
			{"numero_servicios_minimo": 2},
		],
	},
	{
		"id": "arq.resiliencia.001", "patron": "circuit_breaker",
		"implementacion": "nestjs_interceptor_con_reintentos_y_timeout",
		"controles_asociados": ["ASVS-V11.1.4"], "cwe_mitigadas": ["CWE-400"],
		"aplica_cuando": [
			{"etiqueta": "dependencia_sincrona_externa"}, {"etiqueta": "alta_disponibilidad"},
			{"numero_servicios_minimo": 2},
		],
	},
	{
		"id": "arq.basedatos.001", "patron": "database_per_service",
		"implementacion": "prisma_postgresql",
		"controles_asociados": ["ASVS-V4.1.3"], "cwe_mitigadas": ["CWE-668"],
		"aplica_cuando": [
			{"etiqueta": "autonomia_de_datos"}, {"etiqueta": "acoplamiento_bajo"},
			{"numero_servicios_minimo": 2},
		],
	},
	{
		"id": "arq.eventos.001", "patron": "event_driven", "implementacion": "rabbitmq",
		"controles_asociados": ["ASVS-V5.1.3"], "cwe_mitigadas": ["CWE-20"],
		"aplica_cuando": [
			{"etiqueta": "comunicacion_asincrona"}, {"etiqueta": "desacoplamiento_temporal"},
			{"numero_servicios_minimo": 2},
		],
	},
	{
		"id": "arq.transaccion.001", "patron": "saga", "implementacion": "rabbitmq",
		"controles_asociados": ["ASVS-V11.1.1"], "cwe_mitigadas": ["CWE-362"],
		"aplica_cuando": [
			{"etiqueta": "transaccion_entre_servicios"}, {"etiqueta": "consistencia_eventual"},
			{"numero_servicios_minimo": 2},
		],
	},
]

servicio(nombre, requisitos, dependencias, etiquetas) := {
	"nombre": nombre,
	"contexto": nombre,
	"responsabilidad": "Responsabilidad de prueba del servicio.",
	"entidades": [],
	"requisitos": requisitos,
	"base_datos": sprintf("%s_db", [nombre]),
	"depende_de": [{"servicio": s, "tipo": t, "motivo": "Motivo de prueba."} | some [s, t] in dependencias],
	"etiquetas": etiquetas,
}

# La arquitectura que propuso el LLM para el documento 1 del dataset (tienda en línea).
tienda := {
	"servicios": [
		servicio("usuarios", ["RF-01", "RF-02", "RNF-01"], [], ["autenticacion", "limite_peticiones"]),
		servicio("catalogo", ["RF-03", "RF-04"], [], ["validacion_entrada"]),
		servicio("pedidos", ["RF-05", "RF-06", "RF-07"], [["catalogo", "sincrona"], ["pagos", "asincrona"]], ["control_acceso_recursos"]),
		servicio("pagos", ["RF-08"], [], ["validacion_entrada"]),
		servicio("notificaciones", ["RF-09"], [["pedidos", "asincrona"]], []),
	],
	"transversales": ["RNF-02"],
	"etiquetas_transversales": ["cifrado_transito"],
}

entrada(arq) := {"arquitectura": arq, "patrones": patrones_kb}

con_servicios(lista) := object.union(tienda, {"servicios": lista})

decision(arq) := d if {
	d := arquitectura.decision with input as entrada(arq)
}

reglas(conjunto) := {x.regla | some x in conjunto}

# --- Reglas que bloquean ------------------------------------------------------------------------

test_la_arquitectura_de_la_tienda_se_aprueba if {
	d := decision(tienda)
	d.aprobado
	count(d.bloqueantes) == 0
	every c in d.criterios { c.cumple }
	startswith(d.justificacion, "Arquitectura aprobada: cumple los 4 criterios")
}

test_dos_servicios_no_comparten_base_de_datos if {
	pagos := object.union(servicio("pagos", ["RF-08"], [], []), {"base_datos": "pedidos_db"})
	d := decision(con_servicios([tienda.servicios[2], pagos]))
	not d.aprobado
	some b in d.bloqueantes
	b.regla == "arquitectura.base_datos_propia"
	b.motivo == "Los servicios pagos, pedidos comparten la base de datos pedidos_db; cada servicio debe tener la suya"
	some c in d.criterios
	c.regla == "arquitectura.base_datos_propia"
	not c.cumple
	contains(d.justificacion, "incumple 2 de 4 criterios")
}

test_un_ciclo_de_dos_servicios_bloquea if {
	arq := con_servicios([
		servicio("pedidos", ["RF-01"], [["pagos", "sincrona"]], []),
		servicio("pagos", ["RF-02"], [["pedidos", "asincrona"]], []),
		servicio("catalogo", ["RF-03"], [], []),
	])
	d := decision(arq)
	not d.aprobado
	"arquitectura.sin_ciclos" in reglas(d.bloqueantes)
	arquitectura.en_ciclo == {"pagos", "pedidos"} with input as entrada(arq)
}

test_un_ciclo_de_tres_servicios_bloquea if {
	arq := con_servicios([
		servicio("a", ["RF-01"], [["b", "sincrona"]], []),
		servicio("b", ["RF-02"], [["c", "asincrona"]], []),
		servicio("c", ["RF-03"], [["a", "asincrona"]], []),
		servicio("d", ["RF-04"], [["a", "sincrona"]], []),
	])
	some b in decision(arq).bloqueantes
	b.regla == "arquitectura.sin_ciclos"
	startswith(b.motivo, "Dependencias circulares entre a, b, c:")
}

test_sin_ciclo_no_bloquea_aunque_dos_dependan_del_mismo if {
	arq := con_servicios([
		servicio("a", ["RF-01"], [["c", "sincrona"]], []),
		servicio("b", ["RF-02"], [["c", "sincrona"]], []),
		servicio("c", ["RF-03"], [], []),
	])
	decision(arq).aprobado
}

test_depender_de_un_servicio_inexistente_o_de_si_mismo_bloquea if {
	d := decision(con_servicios([
		servicio("pedidos", ["RF-01"], [["inventario", "sincrona"], ["pedidos", "asincrona"]], []),
		servicio("pagos", ["RF-02"], [], []),
	]))
	not d.aprobado
	motivos := {b.motivo | some b in d.bloqueantes; b.regla == "arquitectura.dependencias_conocidas"}
	motivos == {
		"pedidos depende de inventario, que no está en la arquitectura",
		"pedidos depende de sí mismo",
	}

	# Depender de sí mismo no cuenta además como ciclo.
	not "arquitectura.sin_ciclos" in reglas(d.bloqueantes)
}

test_nombres_repetidos_bloquean_sin_romper_la_politica if {
	d := decision(con_servicios([servicio("pagos", ["RF-01"], [], []), servicio("pagos", ["RF-02"], [], [])]))
	not d.aprobado
	"arquitectura.servicios_unicos" in reglas(d.bloqueantes)
}

test_una_arquitectura_vacia_bloquea if {
	d := decision(con_servicios([]))
	not d.aprobado
	"arquitectura.servicios_unicos" in reglas(d.bloqueantes)
	count(d.patrones) == 0
}

# --- Advertencias -------------------------------------------------------------------------------

test_un_servicio_con_la_mayoria_de_los_requisitos_avisa if {
	d := decision(con_servicios([
		servicio("todo", ["RF-01", "RF-02", "RF-03"], [], []),
		servicio("pagos", ["RF-04"], [], []),
	]))
	d.aprobado
	some a in d.advertencias
	a.regla == "arquitectura.servicio_concentrado"
	a.motivo == "todo concentra 3 de 4 requisitos; conviene revisar si mezcla varios contextos"
}

test_la_mitad_exacta_no_avisa if {
	d := decision(con_servicios([servicio("a", ["RF-01"], [], []), servicio("b", ["RF-02"], [], [])]))
	not "arquitectura.servicio_concentrado" in reglas(d.advertencias)
}

test_una_cadena_de_tres_llamadas_sincronas_avisa if {
	d := decision(con_servicios([
		servicio("a", ["RF-01"], [["b", "sincrona"]], []),
		servicio("b", ["RF-02"], [["c", "sincrona"]], []),
		servicio("c", ["RF-03"], [], []),
	]))
	d.aprobado
	some a in d.advertencias
	a.regla == "arquitectura.cadena_sincrona"
	startswith(a.motivo, "Cadena de llamadas síncronas a -> b -> c")
}

test_una_cadena_con_un_evento_no_avisa if {
	d := decision(con_servicios([
		servicio("a", ["RF-01"], [["b", "sincrona"]], []),
		servicio("b", ["RF-02"], [["c", "asincrona"]], []),
		servicio("c", ["RF-03"], [], []),
	]))
	not "arquitectura.cadena_sincrona" in reglas(d.advertencias)
}

# --- Inferencia de patrones ---------------------------------------------------------------------

patrones_de(arq) := {p.patron | some p in decision(arq).patrones}

test_la_tienda_infiere_los_cinco_patrones_de_la_referencia if {
	patrones_de(tienda) == {"api_gateway", "database_per_service", "event_driven", "saga", "circuit_breaker"}
}

test_cada_patron_trae_su_justificacion_y_sus_controles if {
	some p in decision(tienda).patrones
	p.patron == "saga"
	p.id == "arq.transaccion.001"
	p.por == ["transaccion_entre_servicios"]
	p.motivo == "pedidos coordina operaciones que involucran a otros servicios"
	p.controles == ["ASVS-V11.1.1"]
	p.cwe == ["CWE-362"]
	p.implementacion == "rabbitmq"
}

test_el_gateway_se_infiere_por_la_autenticacion_y_el_limite_de_peticiones if {
	some p in decision(tienda).patrones
	p.patron == "api_gateway"
	p.por == ["autenticacion_centralizada", "punto_unico_acceso"]
}

test_sin_dependencias_no_hay_eventos_ni_saga_ni_circuit_breaker if {
	arq := con_servicios([
		servicio("a", ["RF-01"], [], ["autenticacion"]),
		servicio("b", ["RF-02"], [], []),
	])
	patrones_de(arq) == {"api_gateway", "database_per_service"}
}

test_solo_eventos_no_es_una_saga if {
	# auditoria escucha a varios servicios, pero no llama a ninguno: no coordina nada.
	arq := con_servicios([
		servicio("a", ["RF-01"], [], []),
		servicio("b", ["RF-02"], [], []),
		servicio("auditoria", ["RF-03"], [["a", "asincrona"], ["b", "asincrona"]], []),
	])
	patrones_de(arq) == {"database_per_service", "event_driven"}
}

test_un_solo_servicio_no_infiere_patrones_de_varios_servicios if {
	d := decision(con_servicios([servicio("monolito", ["RF-01"], [], ["autenticacion", "punto_unico_acceso"])]))
	d.aprobado
	count(d.patrones) == 0
	d.justificacion == "Arquitectura aprobada: cumple los 4 criterios; patrones inferidos: ninguno"
}

test_un_patron_sin_minimo_de_servicios_solo_pide_el_rasgo if {
	sin_minimo := {
		"id": "arq.prueba.001", "patron": "prueba", "implementacion": "x",
		"controles_asociados": [], "cwe_mitigadas": [],
		"aplica_cuando": [{"etiqueta": "punto_unico_acceso"}],
	}
	arq := con_servicios([servicio("monolito", ["RF-01"], [], ["limite_peticiones"])])
	d := arquitectura.decision with input as {"arquitectura": arq, "patrones": [sin_minimo]}
	{p.patron | some p in d.patrones} == {"prueba"}
}

test_compartir_base_de_datos_quita_la_autonomia_de_datos if {
	pagos := object.union(servicio("pagos", ["RF-08"], [], []), {"base_datos": "pedidos_db"})
	arq := con_servicios([servicio("pedidos", ["RF-01"], [], []), pagos])
	not "database_per_service" in patrones_de(arq)
}

test_sin_patrones_en_la_entrada_no_falla if {
	d := arquitectura.decision with input as {"arquitectura": tienda}
	d.aprobado
	count(d.patrones) == 0
	count(d.rasgos) > 0
}
