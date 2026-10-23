# Políticas de integración para Docker Compose (Gate 2, Conftest).
# Uso: conftest test docker-compose.dev.yml --policy policies/integracion --namespace integracion.compose
#   deny = bloquea el pipeline; warn = aviso (no bloquea).
package integracion.compose

import rego.v1

# ---------- Utilidades ----------

# Variables de entorno de un servicio como mapa nombre -> valor (admite lista "K=V" y mapa).
variables(svc) := vars if {
	is_object(svc.environment)
	vars := {k: sprintf("%v", [v]) | some k, v in svc.environment}
}

variables(svc) := vars if {
	is_array(svc.environment)
	vars := {k: v |
		some entrada in svc.environment
		partes := split(entrada, "=")
		k := partes[0]
		v := concat("=", array.slice(partes, 1, count(partes)))
	}
}

variables(svc) := {} if not svc.environment

nombre_variable_sensible(k) if regex.match(`(pass|pwd|secret|token|api[_-]?key|private[_-]?key|auth)`, lower(k))

# Origen de un volumen: "ruta:destino[:modo]" o {source: ruta}.
origen_volumen(v) := split(v, ":")[0] if is_string(v)

origen_volumen(v) := v.source if is_object(v)

texto_puerto(p) := sprintf("%v", [p])

# ---------- Reglas que bloquean ----------

deny contains msg if {
	some nombre, svc in input.services
	svc.privileged == true
	msg := sprintf("[%s] privileged: true da al contenedor acceso casi total al host", [nombre])
}

deny contains msg if {
	some nombre, svc in input.services
	svc.network_mode == "host"
	msg := sprintf("[%s] network_mode: host elimina el aislamiento de red", [nombre])
}

rutas_prohibidas := {"/", "/etc", "/proc", "/sys", "/root", "/var/run", "/var/lib/docker"}

deny contains msg if {
	some nombre, svc in input.services
	some v in svc.volumes
	origen := origen_volumen(v)
	prohibido_el_montaje(origen)
	msg := sprintf("[%s] monta '%s' del host dentro del contenedor", [nombre, origen])
}

prohibido_el_montaje(origen) if origen in rutas_prohibidas

prohibido_el_montaje(origen) if endswith(origen, "docker.sock")

# Los puertos publicados solo escuchan en el equipo local (127.0.0.1 o ::1).
deny contains msg if {
	some nombre, svc in input.services
	some p in svc.ports
	is_string(p)
	not startswith(p, "127.0.0.1:")
	not startswith(p, "[::1]:")
	msg := sprintf("[%s] el puerto '%s' queda abierto a toda la red; usa '127.0.0.1:%s'", [nombre, p, p])
}

deny contains msg if {
	some nombre, svc in input.services
	some p in svc.ports
	is_number(p)
	msg := sprintf("[%s] el puerto '%s' queda abierto a toda la red; usa '127.0.0.1:%s:%s'", [nombre, texto_puerto(p), texto_puerto(p), texto_puerto(p)])
}

deny contains msg if {
	some nombre, svc in input.services
	some p in svc.ports
	is_object(p)
	not escucha_solo_en_local(p)
	msg := sprintf("[%s] el puerto %v queda abierto a toda la red; define host_ip: 127.0.0.1", [nombre, p.target])
}

# Se niega con una función: si host_ip no existe, la función no se cumple y "not" la detecta.
escucha_solo_en_local(p) if p.host_ip in {"127.0.0.1", "::1"}

# Imágenes con versión explícita.
deny contains msg if {
	some nombre, svc in input.services
	imagen := svc.image
	not contains(imagen, "@sha256:")
	etiqueta_prohibida(imagen)
	msg := sprintf("[%s] la imagen '%s' no tiene una versión fija (usa una etiqueta distinta de latest)", [nombre, imagen])
}

etiqueta_prohibida(imagen) if endswith(imagen, ":latest")

etiqueta_prohibida(imagen) if {
	segmentos := split(imagen, "/")
	not contains(segmentos[count(segmentos) - 1], ":")
}

# Secretos solo por interpolación (${VAR} desde .env), nunca escritos en el archivo.
deny contains msg if {
	some nombre, svc in input.services
	some k, v in variables(svc)
	nombre_variable_sensible(k)
	not endswith(upper(k), "_FILE")
	v != ""
	not contains(v, "${")
	msg := sprintf("[%s] la variable %s tiene un valor escrito en el archivo; usa ${%s} desde .env", [nombre, k, k])
}

# Capacidades y perfiles de seguridad peligrosos.
capacidades_prohibidas := {"ALL", "SYS_ADMIN", "SYS_PTRACE", "SYS_MODULE", "NET_ADMIN"}

deny contains msg if {
	some nombre, svc in input.services
	some c in svc.cap_add
	upper(c) in capacidades_prohibidas
	msg := sprintf("[%s] cap_add %s concede privilegios del kernel que no necesita", [nombre, c])
}

deny contains msg if {
	some nombre, svc in input.services
	some o in svc.security_opt
	contains(o, "unconfined")
	msg := sprintf("[%s] security_opt '%s' desactiva el aislamiento del contenedor", [nombre, o])
}

# Patrón Database per Service: un servicio solo habla con su propia base "<servicio>-db".
deny contains msg if {
	some nombre, svc in input.services
	not endswith(nombre, "-db")
	some bd, _ in input.services
	endswith(bd, "-db")
	bd != sprintf("%s-db", [nombre])
	some k, v in variables(svc)
	regex.match(sprintf(`@%s[:/]`, [bd]), v)
	msg := sprintf("[%s] la variable %s apunta a la base '%s' de otro servicio (Database per Service)", [nombre, k, bd])
}

# ---------- Avisos (no bloquean) ----------

warn contains msg if {
	some nombre, svc in input.services
	not svc.healthcheck
	msg := sprintf("[%s] sin healthcheck: Compose no sabe cuándo el servicio está listo", [nombre])
}

warn contains msg if {
	some nombre, svc in input.services
	not "no-new-privileges:true" in {x | some x in svc.security_opt}
	msg := sprintf("[%s] sin 'no-new-privileges:true' en security_opt", [nombre])
}

warn contains msg if {
	some nombre, svc in input.services
	svc.image
	not contains(svc.image, "@sha256:")
	msg := sprintf("[%s] imagen sin digest sha256: la etiqueta puede cambiar de contenido", [nombre])
}

warn contains msg if {
	some nombre, svc in input.services
	contains(svc.image, "keycloak")
	contains(sprintf("%v", [svc.command]), "start-dev")
	msg := sprintf("[%s] Keycloak en modo start-dev: solo para desarrollo local", [nombre])
}
