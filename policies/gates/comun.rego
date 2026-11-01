# Utilidades compartidas por las políticas de los Security Gates.
package gates.comun

import rego.v1

severidades := ["critica", "alta", "media", "baja", "info"]

severidades_bloqueantes := {"critica", "alta"}

severidades_aviso := {"media", "baja"}

# Ubicación legible de un hallazgo: "archivo:linea", solo "archivo" o "sin ubicación".
ubicacion(h) := sprintf("%s:%d", [h.archivo, h.linea_inicio]) if {
	is_string(h.archivo)
	is_number(h.linea_inicio)
}

ubicacion(h) := h.archivo if {
	is_string(h.archivo)
	not is_number(h.linea_inicio)
}

ubicacion(h) := "sin ubicación" if not is_string(h.archivo)

# Hallazgos por severidad, con todas las severidades aunque tengan 0.
conteo(hallazgos) := {s: n |
	some s in severidades
	n := count([h | some h in hallazgos; h.severidad == s])
}

# Una herramienta que no terminó impide aprobar: sin su resultado no se sabe si hay problemas.
herramientas_caidas(herramientas) := {t.nombre | some t in herramientas; t.estado == "error"}

# true si ningún bloqueante viene de la regla indicada.
cumple(regla, bloqueantes) if not regla in {b.regla | some b in bloqueantes}

cumple(regla, bloqueantes) := false if regla in {b.regla | some b in bloqueantes}

# Texto de la justificación de un rechazo: cuántos criterios falla y cuáles.
criterios_incumplidos(criterios) := {c.regla | some c in criterios; not c.cumple}
