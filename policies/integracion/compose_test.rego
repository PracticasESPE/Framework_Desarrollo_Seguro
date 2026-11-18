# Pruebas de las políticas: conftest verify --policy policies/integracion
package integracion.compose

import rego.v1

digest := "@sha256:0000000000000000000000000000000000000000000000000000000000000000"

compose_base := {"services": {"api": {
	"image": concat("", ["node:22", digest]),
	"ports": ["127.0.0.1:3000:3000"],
	"healthcheck": {"test": ["CMD", "true"]},
	"security_opt": ["no-new-privileges:true"],
}}}

con_servicio(extra) := {"services": {"api": object.union(compose_base.services.api, extra)}}

# ---- Un compose correcto no genera mensajes ----

test_compose_correcto_sin_deny if count(deny) == 0 with input as compose_base

test_compose_correcto_sin_warn if count(warn) == 0 with input as compose_base

# ---- deny ----

test_privileged if count(deny) == 1 with input as con_servicio({"privileged": true})

test_network_host if count(deny) == 1 with input as con_servicio({"network_mode": "host"})

test_docker_sock if count(deny) == 1 with input as con_servicio({"volumes": ["/var/run/docker.sock:/var/run/docker.sock"]})

test_montaje_de_raiz if count(deny) == 1 with input as con_servicio({"volumes": ["/:/host"]})

test_volumen_relativo_permitido if count(deny) == 0 with input as con_servicio({"volumes": ["./datos:/datos"]})

test_puerto_publico if count(deny) == 1 with input as con_servicio({"ports": ["3000:3000"]})

test_puerto_numerico if count(deny) == 1 with input as con_servicio({"ports": [3000]})

test_puerto_largo_sin_host_ip if count(deny) == 1 with input as con_servicio({"ports": [{"target": 3000, "published": 3000}]})

test_puerto_largo_loopback if count(deny) == 0 with input as con_servicio({"ports": [{"target": 3000, "published": 3000, "host_ip": "127.0.0.1"}]})

test_imagen_latest if count(deny) == 1 with input as con_servicio({"image": "node:latest"})

test_imagen_sin_etiqueta if count(deny) == 1 with input as con_servicio({"image": "node"})

test_imagen_de_registro_con_puerto_sin_etiqueta if count(deny) == 1 with input as con_servicio({"image": "localhost:5000/app"})

test_imagen_con_digest_permitida if count(deny) == 0 with input as con_servicio({"image": concat("", ["node", digest])})

test_secreto_escrito_en_el_archivo if count(deny) == 1 with input as con_servicio({"environment": {"DB_PASSWORD": "1234"}})

test_secreto_en_lista if count(deny) == 1 with input as con_servicio({"environment": ["API_TOKEN=abc"]})

test_secreto_interpolado_permitido if count(deny) == 0 with input as con_servicio({"environment": {"DB_PASSWORD": "${DB_PASSWORD:?falta}"}})

test_secreto_mezclado_permitido if count(deny) == 0 with input as con_servicio({"environment": {"NEO4J_AUTH": "neo4j/${NEO4J_PASSWORD:?falta}"}})

test_secreto_por_archivo_permitido if count(deny) == 0 with input as con_servicio({"environment": {"DB_PASSWORD_FILE": "/run/secrets/db"}})

test_capacidad_peligrosa if count(deny) == 1 with input as con_servicio({"cap_add": ["SYS_ADMIN"]})

test_seccomp_sin_restricciones if count(deny) == 1 with input as con_servicio({"security_opt": ["seccomp:unconfined"]})

test_base_de_otro_servicio if count(deny) == 1 with input as {"services": {
	"usuarios": object.union(compose_base.services.api, {"environment": {"DATABASE_URL": "postgresql://u:${P}@pagos-db:5432/x"}}),
	"usuarios-db": {"image": concat("", ["postgres:16", digest])},
	"pagos-db": {"image": concat("", ["postgres:16", digest])},
}}

test_base_propia_permitida if count(deny) == 0 with input as {"services": {
	"usuarios": object.union(compose_base.services.api, {"environment": {"DATABASE_URL": "postgresql://u:${P}@usuarios-db:5432/x"}}),
	"usuarios-db": {"image": concat("", ["postgres:16", digest])},
}}

# ---- warn ----

test_aviso_sin_healthcheck if {
	servicio := object.remove(compose_base.services.api, ["healthcheck"])
	count(warn) == 1 with input as {"services": {"api": servicio}}
}

test_aviso_sin_no_new_privileges if {
	servicio := object.remove(compose_base.services.api, ["security_opt"])
	count(warn) == 1 with input as {"services": {"api": servicio}}
}

test_aviso_imagen_sin_digest if count(warn) == 1 with input as con_servicio({"image": "node:22"})

test_aviso_keycloak_start_dev if {
	count(warn) == 1 with input as con_servicio({
		"image": concat("", ["quay.io/keycloak/keycloak:26.7.3", digest]),
		"command": ["start-dev"],
	})
}
