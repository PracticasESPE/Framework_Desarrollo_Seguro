# Fase 2: reglas arquitectónicas e inferencia de patrones (plan técnico 7.2, paso 2).
#
# El LLM propone la arquitectura (arquitectura.json); estas reglas deciden si se acepta y qué
# patrones de la base de conocimiento aplican, con su justificación (principio P1).
#
# Entrada (la arma el motor, orchestrator/architecture/validacion.py):
#   {
#     "arquitectura": <arquitectura.json>,
#     "patrones": [{"id", "patron", "descripcion", "implementacion", "controles_asociados",
#                   "cwe_mitigadas", "aplica_cuando": [{"etiqueta"} | {"numero_servicios_minimo"}]}]
#   }
#
# Inferencia: de la arquitectura se deducen sus rasgos (p. ej. "comunicacion_asincrona"). Un patrón
# aplica si la arquitectura tiene el mínimo de servicios que pide y al menos uno de sus rasgos.
#
# Salida: data.arquitectura.decision =
#   {aprobado, bloqueantes, advertencias, criterios, rasgos, patrones, justificacion}
package arquitectura

import rego.v1

servicios := object.get(input, ["arquitectura", "servicios"], [])

nombres := {s.nombre | some s in servicios}

numero_servicios := count(servicios)

dependencias(nombre) := {d.servicio |
	some s in servicios
	s.nombre == nombre
	some d in object.get(s, "depende_de", [])
}

dependencias_sincronas(nombre) := {d.servicio |
	some s in servicios
	s.nombre == nombre
	some d in object.get(s, "depende_de", [])
	d.tipo == "sincrona"
}

# Grafo de dependencias por nombre de servicio, sin las del servicio consigo mismo.
grafo := {nombre: vecinos |
	some nombre in nombres
	vecinos := dependencias(nombre) - {nombre}
}

# --- Reglas que bloquean ------------------------------------------------------------------------

default aprobado := false

aprobado if count(bloqueantes) == 0

# Database per Service: cada servicio es dueño de su base de datos.
bloqueantes contains b if {
	some base in {s.base_datos | some s in servicios}
	usuarios := sort([s.nombre | some s in servicios; s.base_datos == base])
	count(usuarios) > 1
	b := {
		"regla": "arquitectura.base_datos_propia",
		"motivo": sprintf(
			"Los servicios %s comparten la base de datos %s; cada servicio debe tener la suya",
			[concat(", ", usuarios), base],
		),
	}
}

# Sin dependencias circulares: un servicio no puede depender, directa o indirectamente, de sí mismo.
en_ciclo contains nombre if {
	some nombre in nombres
	some vecino in grafo[nombre]
	nombre in graph.reachable(grafo, {vecino})
}

bloqueantes contains b if {
	count(en_ciclo) > 0
	b := {
		"regla": "arquitectura.sin_ciclos",
		"motivo": sprintf(
			"Dependencias circulares entre %s: rompe el ciclo con un evento asíncrono o moviendo la responsabilidad",
			[concat(", ", sort(en_ciclo))],
		),
	}
}

bloqueantes contains b if {
	some s in servicios
	some d in object.get(s, "depende_de", [])
	not d.servicio in nombres
	b := {
		"regla": "arquitectura.dependencias_conocidas",
		"motivo": sprintf("%s depende de %s, que no está en la arquitectura", [s.nombre, d.servicio]),
	}
}

bloqueantes contains b if {
	some s in servicios
	some d in object.get(s, "depende_de", [])
	d.servicio == s.nombre
	b := {
		"regla": "arquitectura.dependencias_conocidas",
		"motivo": sprintf("%s depende de sí mismo", [s.nombre]),
	}
}

bloqueantes contains b if {
	some nombre in nombres
	count([s | some s in servicios; s.nombre == nombre]) > 1
	b := {
		"regla": "arquitectura.servicios_unicos",
		"motivo": sprintf("Hay más de un servicio llamado %s", [nombre]),
	}
}

bloqueantes contains b if {
	numero_servicios == 0
	b := {"regla": "arquitectura.servicios_unicos", "motivo": "La arquitectura no tiene servicios"}
}

# --- Advertencias (no bloquean) -----------------------------------------------------------------

total_requisitos := sum([count(s.requisitos) | some s in servicios])

# Un servicio con más de la mitad de los requisitos suele mezclar varios bounded contexts.
advertencias contains a if {
	numero_servicios > 1
	some s in servicios
	count(s.requisitos) * 2 > total_requisitos
	a := {
		"regla": "arquitectura.servicio_concentrado",
		"motivo": sprintf(
			"%s concentra %d de %d requisitos; conviene revisar si mezcla varios contextos",
			[s.nombre, count(s.requisitos), total_requisitos],
		),
	}
}

# Tres servicios encadenados por llamadas síncronas: un fallo o una demora se propaga.
advertencias contains a if {
	some primero in nombres
	some segundo in dependencias_sincronas(primero)
	some tercero in dependencias_sincronas(segundo)
	not tercero in {primero, segundo}
	a := {
		"regla": "arquitectura.cadena_sincrona",
		"motivo": sprintf(
			"Cadena de llamadas síncronas %s -> %s -> %s: si %s falla o tarda, arrastra a los demás; considera eventos",
			[primero, segundo, tercero, tercero],
		),
	}
}

# --- Rasgos de la arquitectura ------------------------------------------------------------------
#
# Son las etiquetas que usan las condiciones "aplica_cuando" de los patrones de la base de
# conocimiento. Cada rasgo lleva el motivo por el que se dedujo.

etiquetas_de_requisitos := {e | some s in servicios; some e in s.etiquetas} | {e |
	some e in object.get(input, ["arquitectura", "etiquetas_transversales"], [])
}

pares(tipo) := sort([sprintf("%s -> %s", [s.nombre, d.servicio]) |
	some s in servicios
	some d in object.get(s, "depende_de", [])
	d.tipo == tipo
])

rasgos contains {
	"etiqueta": "punto_unico_acceso",
	"motivo": "Hay requisitos de punto único de entrada o de límite de peticiones",
} if {
	some etiqueta in {"punto_unico_acceso", "limite_peticiones"}
	etiqueta in etiquetas_de_requisitos
}

rasgos contains {
	"etiqueta": "autenticacion_centralizada",
	"motivo": "Hay requisitos de autenticación y varios servicios: se autentica una sola vez, en la entrada",
} if {
	"autenticacion" in etiquetas_de_requisitos
	numero_servicios > 1
}

rasgos contains {
	"etiqueta": "autonomia_de_datos",
	"motivo": "Cada servicio tiene su propia base de datos",
} if {
	numero_servicios > 1
	count({s.base_datos | some s in servicios}) == numero_servicios
}

rasgos contains {
	"etiqueta": "comunicacion_asincrona",
	"motivo": sprintf("Dependencias por eventos: %s", [concat(", ", pares("asincrona"))]),
} if {
	count(pares("asincrona")) > 0
}

rasgos contains {
	"etiqueta": "dependencia_sincrona_externa",
	"motivo": sprintf("Llamadas síncronas entre servicios: %s", [concat(", ", pares("sincrona"))]),
} if {
	count(pares("sincrona")) > 0
}

# Un servicio que llama a otro y depende además de un tercero coordina una operación entre
# varios servicios: si un paso falla, los anteriores deben compensarse.
coordinadores contains s.nombre if {
	some s in servicios
	count(dependencias(s.nombre) - {s.nombre}) >= 2
	count(dependencias_sincronas(s.nombre) - {s.nombre}) >= 1
}

rasgos contains {
	"etiqueta": "transaccion_entre_servicios",
	"motivo": sprintf(
		"%s coordina operaciones que involucran a otros servicios",
		[concat(", ", sort(coordinadores))],
	),
} if {
	count(coordinadores) > 0
}

etiquetas_de_rasgos := {r.etiqueta | some r in rasgos}

# --- Inferencia de patrones ---------------------------------------------------------------------

minimos(patron) := [m |
	some condicion in patron.aplica_cuando
	m := object.get(condicion, "numero_servicios_minimo", null)
	is_number(m)
]

# Sin condición de número de servicios, o con servicios suficientes.
cumple_minimo(patron) if count(minimos(patron)) == 0

cumple_minimo(patron) if numero_servicios >= max(minimos(patron))

patrones contains p if {
	some patron in object.get(input, "patrones", [])
	cumple_minimo(patron)
	coincidencias := {e |
		some condicion in patron.aplica_cuando
		e := object.get(condicion, "etiqueta", null)
		e in etiquetas_de_rasgos
	}
	count(coincidencias) > 0
	p := {
		"id": patron.id,
		"patron": patron.patron,
		"implementacion": patron.implementacion,
		"controles": patron.controles_asociados,
		"cwe": patron.cwe_mitigadas,
		"por": sort(coincidencias),
		"motivo": concat("; ", sort({r.motivo | some r in rasgos; r.etiqueta in coincidencias})),
	}
}

# --- Decisión ------------------------------------------------------------------------------------

cumple(regla) if not regla in {b.regla | some b in bloqueantes}

cumple(regla) := false if regla in {b.regla | some b in bloqueantes}

criterios := [
	{
		"regla": "arquitectura.base_datos_propia",
		"cumple": cumple("arquitectura.base_datos_propia"),
		"detalle": "Cada servicio tiene su propia base de datos (Database per Service)",
	},
	{
		"regla": "arquitectura.sin_ciclos",
		"cumple": cumple("arquitectura.sin_ciclos"),
		"detalle": "Las dependencias entre servicios no forman ciclos",
	},
	{
		"regla": "arquitectura.dependencias_conocidas",
		"cumple": cumple("arquitectura.dependencias_conocidas"),
		"detalle": "Cada dependencia apunta a otro servicio de la arquitectura",
	},
	{
		"regla": "arquitectura.servicios_unicos",
		"cumple": cumple("arquitectura.servicios_unicos"),
		"detalle": "Hay al menos un servicio y no hay nombres repetidos",
	},
]

incumplidos := {c.regla | some c in criterios; not c.cumple}

default lista_de_patrones := "ninguno"

lista_de_patrones := concat(", ", sort({p.patron | some p in patrones})) if count(patrones) > 0

justificacion := sprintf(
	"Arquitectura aprobada: cumple los %d criterios; patrones inferidos: %s",
	[count(criterios), lista_de_patrones],
) if aprobado

justificacion := sprintf(
	"Arquitectura rechazada: incumple %d de %d criterios (%s)",
	[count(incumplidos), count(criterios), concat(", ", sort(incumplidos))],
) if not aprobado

decision := {
	"aprobado": aprobado,
	"bloqueantes": bloqueantes,
	"advertencias": advertencias,
	"criterios": criterios,
	"rasgos": rasgos,
	"patrones": patrones,
	"justificacion": justificacion,
}
