"""Gestión de los proveedores de LLM: límites de uso, caché, respaldo entre proveedores y uso.

Ninguna prueba llama a la red: los clientes de los SDK y los proveedores se simulan.
"""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import anthropic
import httpx
import openai
import pytest
from pydantic import BaseModel
from typer.testing import CliRunner

from orchestrator.cli import app
from orchestrator.config import Configuracion
from orchestrator.ingest import segmentar
from orchestrator.ingest.clasificacion import clasificar_unidades
from orchestrator.llm import (
    ErrorLimiteLLM,
    ErrorLLM,
    ErrorProveedorLLM,
    ErrorSalidaEstructurada,
    ProveedorConCache,
    ProveedorEnCadena,
    UsoLLM,
    crear_proveedor,
    describir_uso,
    uso_por_proveedor,
)
from orchestrator.llm.base import error_de_limite
from orchestrator.llm.cache import estadisticas, normalizar_prompt, vaciar
from orchestrator.llm.claude import ProveedorClaude
from orchestrator.llm.gemini import ProveedorGemini
from orchestrator.llm.groq import ProveedorGroq
from orchestrator.llm.ollama import ProveedorOllama

runner = CliRunner()


class Requisito(BaseModel):
    id: str
    tipo: str


VALIDO = '{"id": "RF-01", "tipo": "funcional"}'
ESPERADO = Requisito(id="RF-01", tipo="funcional")


def _config(**valores) -> Configuracion:
    return Configuracion(_env_file=None, **valores)


# --- Errores de límite -------------------------------------------------------------------------


def test_limite_por_minuto_con_retry_after():
    error = error_de_limite("groq", "Rate limit reached on tokens per minute (TPM)", "7")
    assert isinstance(error, ErrorProveedorLLM)
    assert (error.espera_s, error.diario) == (7.0, False)
    assert str(error) == "groq: límite de peticiones alcanzado"


def test_cuota_diaria_con_la_espera_en_el_texto():
    detalle = (
        "Rate limit reached for model `openai/gpt-oss-20b` in organization `org_secreto` on "
        "tokens per day (TPD): Limit 200000, Used 199624. Please try again in 7m12.5s."
    )
    error = error_de_limite("groq", detalle, None)
    assert (error.espera_s, error.diario) == (432.5, True)
    assert str(error) == "groq: cuota diaria agotada; se renueva en 7 min"
    assert "org_secreto" not in str(error)  # el texto del proveedor no llega al usuario


@pytest.mark.parametrize(
    ("retry_after", "detalle", "espera"),
    [("abc", "", None), (None, "sin indicación", None), (None, "Please retry in 31s", 31.0)],
)
def test_espera_que_no_se_puede_leer(retry_after, detalle, espera):
    assert error_de_limite("x", detalle, retry_after).espera_s == espera


def _rate_limit_openai(mensaje: str, retry_after: str | None) -> openai.RateLimitError:
    peticion = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    cabeceras = {"retry-after": retry_after} if retry_after else {}
    respuesta = httpx.Response(429, request=peticion, headers=cabeceras)
    return openai.RateLimitError(mensaje, response=respuesta, body=None)


def _cliente_groq(*respuestas):
    llamadas: list[dict] = []
    pendientes = list(respuestas)

    def create(**kwargs):
        llamadas.append(kwargs)
        respuesta = pendientes.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        mensaje = SimpleNamespace(content=respuesta)
        uso = SimpleNamespace(prompt_tokens=120, completion_tokens=30)
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)], usage=uso)

    cliente = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return cliente, llamadas


def test_groq_429_indica_la_espera_y_si_es_diario():
    cliente, _ = _cliente_groq(_rate_limit_openai("on tokens per day (TPD)", "3600"))
    with pytest.raises(ErrorLimiteLLM) as capturado:
        ProveedorGroq(cliente=cliente).generar_estructurado("x", Requisito)
    assert (capturado.value.espera_s, capturado.value.diario) == (3600.0, True)


def test_groq_cuenta_tokens_y_aplica_el_esfuerzo_solo_a_gpt_oss():
    cliente, llamadas = _cliente_groq(VALIDO, VALIDO)
    groq = ProveedorGroq(
        cliente=cliente,
        esfuerzo_razonamiento="low",
        modelos={"rapido": "openai/gpt-oss-20b", "razonamiento": "llama-3.3-70b-versatile"},
    )
    groq.generar_estructurado("x", Requisito, nivel="rapido")
    groq.generar_estructurado("x", Requisito, nivel="razonamiento")
    assert llamadas[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in llamadas[1]
    assert groq.uso == UsoLLM(llamadas=2, tokens_entrada=240, tokens_salida=60)


def test_groq_sin_esfuerzo_configurado_no_envia_el_parametro():
    cliente, llamadas = _cliente_groq(VALIDO)
    ProveedorGroq(cliente=cliente).generar_estructurado("x", Requisito)
    assert "reasoning_effort" not in llamadas[0]


def test_claude_429_y_tokens():
    peticion = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    respuesta = httpx.Response(429, request=peticion, headers={"retry-after": "12"})
    limite = anthropic.RateLimitError("rate limited", response=respuesta, body=None)
    correcta = SimpleNamespace(
        parsed_output=ESPERADO,
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=50, output_tokens=8),
    )
    pendientes = [limite, correcta]

    def parse(**_):
        siguiente = pendientes.pop(0)
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    cliente = SimpleNamespace(messages=SimpleNamespace(parse=parse))
    claude = ProveedorClaude(cliente=cliente)
    with pytest.raises(ErrorLimiteLLM) as capturado:
        claude.generar_estructurado("x", Requisito)
    assert capturado.value.espera_s == 12.0
    assert claude.generar_estructurado("x", Requisito) == ESPERADO
    assert claude.uso == UsoLLM(llamadas=1, tokens_entrada=50, tokens_salida=8)


def test_gemini_y_ollama_cuentan_tokens():
    gemini_respuesta = SimpleNamespace(
        text=VALIDO,
        usage_metadata=SimpleNamespace(
            prompt_token_count=70, candidates_token_count=10, thoughts_token_count=5
        ),
    )
    gemini = ProveedorGemini(
        cliente=SimpleNamespace(
            models=SimpleNamespace(generate_content=lambda **_: gemini_respuesta)
        )
    )
    gemini.generar_estructurado("x", Requisito)
    assert gemini.uso == UsoLLM(llamadas=1, tokens_entrada=70, tokens_salida=15)

    ollama_respuesta = SimpleNamespace(
        message=SimpleNamespace(content=VALIDO), prompt_eval_count=40, eval_count=9
    )
    ollama = ProveedorOllama(cliente=SimpleNamespace(chat=lambda **_: ollama_respuesta))
    ollama.generar_estructurado("x", Requisito)
    assert ollama.uso == UsoLLM(llamadas=1, tokens_entrada=40, tokens_salida=9)


# --- Caché -------------------------------------------------------------------------------------


class Simulado:
    """Proveedor simulado: responde en orden y cuenta sus llamadas."""

    def __init__(self, nombre="simulado", *respuestas, modelos=None, **ajustes):
        self.nombre = nombre
        self.modelos = modelos or {"rapido": "modelo-a", "razonamiento": "modelo-b"}
        self.respuestas = list(respuestas) or [ESPERADO]
        self.prompts: list[str] = []
        self.uso = UsoLLM()
        for clave, valor in ajustes.items():
            setattr(self, clave, valor)

    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        self.prompts.append(prompt)
        respuesta = self.respuestas.pop(0) if len(self.respuestas) > 1 else self.respuestas[0]
        if isinstance(respuesta, Exception):
            raise respuesta
        self.uso.llamadas += 1
        self.uso.tokens_entrada += 100
        return respuesta


def test_la_cache_responde_la_misma_pregunta_sin_llamar_al_proveedor(tmp_path: Path):
    simulado = Simulado()
    con_cache = ProveedorConCache(simulado, tmp_path)

    assert con_cache.generar_estructurado("p", Requisito, sistema="s") == ESPERADO
    assert con_cache.generar_estructurado("p", Requisito, sistema="s") == ESPERADO
    assert len(simulado.prompts) == 1
    assert con_cache.uso_total() == UsoLLM(llamadas=1, desde_cache=1, tokens_entrada=100)
    assert estadisticas(tmp_path)[0] == 1
    assert not list(tmp_path.rglob("*.tmp"))


def test_la_cache_ignora_el_codigo_aleatorio_de_las_marcas(tmp_path: Path):
    simulado = Simulado()
    con_cache = ProveedorConCache(simulado, tmp_path)
    con_cache.generar_estructurado(
        '<unidad-1a2b3c4d ubicacion="3.1">x</unidad-1a2b3c4d>', Requisito
    )
    con_cache.generar_estructurado(
        '<unidad-9f8e7d6c ubicacion="3.1">x</unidad-9f8e7d6c>', Requisito
    )
    assert len(simulado.prompts) == 1
    assert normalizar_prompt("<contexto-abcdef01>t</contexto-abcdef01>") == (
        "<contexto-00000000>t</contexto-00000000>"
    )


@pytest.mark.parametrize(
    "cambio",
    [
        {"prompt": "otro"},
        {"sistema": "otras instrucciones"},
        {"nivel": "razonamiento"},
        {"esquema": "otro"},
    ],
)
def test_la_cache_no_se_usa_si_cambia_algo_de_la_pregunta(tmp_path: Path, cambio):
    class Otro(BaseModel):
        id: str
        tipo: str
        extra: str = ""

    simulado = Simulado()
    con_cache = ProveedorConCache(simulado, tmp_path)
    con_cache.generar_estructurado("p", Requisito, nivel="rapido", sistema="s")
    con_cache.generar_estructurado(
        cambio.get("prompt", "p"),
        Otro if "esquema" in cambio else Requisito,
        nivel=cambio.get("nivel", "rapido"),
        sistema=cambio.get("sistema", "s"),
    )
    assert len(simulado.prompts) == 2


def test_la_cache_separa_proveedores_modelos_y_ajustes(tmp_path: Path):
    variantes = [
        Simulado("groq"),
        Simulado("gemini"),
        Simulado("groq", modelos={"rapido": "otro", "razonamiento": "b"}),
        Simulado("groq", esfuerzo_razonamiento="low"),
    ]
    for simulado in variantes:
        ProveedorConCache(simulado, tmp_path).generar_estructurado("p", Requisito)
    assert all(len(s.prompts) == 1 for s in variantes)
    assert estadisticas(tmp_path)[0] == 4


def test_una_entrada_danada_se_ignora_y_se_reemplaza(tmp_path: Path):
    simulado = Simulado()
    con_cache = ProveedorConCache(simulado, tmp_path)
    con_cache.generar_estructurado("p", Requisito)
    (archivo,) = tmp_path.rglob("*.json")
    archivo.write_text('{"id": "RF-01"}', encoding="utf-8")  # no cumple el esquema

    assert con_cache.generar_estructurado("p", Requisito) == ESPERADO
    assert len(simulado.prompts) == 2
    assert json.loads(archivo.read_text(encoding="utf-8")) == ESPERADO.model_dump()


def test_los_errores_no_se_guardan(tmp_path: Path):
    simulado = Simulado("x", ErrorProveedorLLM("caído"), ESPERADO)
    con_cache = ProveedorConCache(simulado, tmp_path)
    with pytest.raises(ErrorProveedorLLM):
        con_cache.generar_estructurado("p", Requisito)
    assert estadisticas(tmp_path) == (0, 0)
    assert con_cache.generar_estructurado("p", Requisito) == ESPERADO


def test_vaciar_solo_borra_respuestas_de_la_cache(tmp_path: Path):
    ProveedorConCache(Simulado(), tmp_path).generar_estructurado("p", Requisito)
    ajeno = tmp_path / "ab" / "notas.json"
    ajeno.parent.mkdir(exist_ok=True)
    ajeno.write_text("{}", encoding="utf-8")

    assert vaciar(tmp_path) == 1
    assert ajeno.exists()
    assert vaciar(tmp_path / "no-existe") == 0


# --- Cadena de respaldo ------------------------------------------------------------------------


class Reloj:
    def __init__(self) -> None:
        self.ahora = 1000.0

    def __call__(self) -> float:
        return self.ahora


def test_el_respaldo_responde_cuando_el_principal_llega_a_su_limite():
    reloj = Reloj()
    groq = Simulado("groq", ErrorLimiteLLM("groq: límite", espera_s=40), ESPERADO)
    gemini = Simulado("gemini")
    cadena = ProveedorEnCadena([groq, gemini], reloj=reloj)
    cambios: list[tuple[str, str, str]] = []
    cadena.al_cambiar = lambda de, a, motivo: cambios.append((de, a, motivo))

    assert cadena.generar_estructurado("p1", Requisito) == ESPERADO
    assert cambios == [("groq", "gemini", "groq: límite")]

    # Apartado los 40 s que pidió: no se le vuelve a llamar.
    cadena.generar_estructurado("p2", Requisito)
    assert groq.prompts == ["p1"]
    assert gemini.prompts == ["p1", "p2"]

    reloj.ahora += 41  # pasado el tiempo, el principal vuelve a responder
    cadena.generar_estructurado("p3", Requisito)
    assert groq.prompts == ["p1", "p3"]
    assert cadena.respuestas_por_proveedor == {"gemini": 2, "groq": 1}


def test_un_fallo_de_red_aparta_al_proveedor_un_minuto():
    reloj = Reloj()
    groq = Simulado("groq", ErrorProveedorLLM("groq: no se pudo conectar"), ESPERADO)
    ollama = Simulado("ollama")
    cadena = ProveedorEnCadena([groq, ollama], reloj=reloj)

    cadena.generar_estructurado("p1", Requisito)
    reloj.ahora += 59
    cadena.generar_estructurado("p2", Requisito)
    assert groq.prompts == ["p1"]
    reloj.ahora += 2
    cadena.generar_estructurado("p3", Requisito)
    assert groq.prompts == ["p1", "p3"]


def test_si_todos_llegan_al_limite_se_indica_la_espera_mas_corta():
    reloj = Reloj()
    cadena = ProveedorEnCadena(
        [
            Simulado("groq", ErrorLimiteLLM("a", espera_s=600, diario=True)),
            Simulado("gemini", ErrorLimiteLLM("b", espera_s=25)),
        ],
        reloj=reloj,
    )
    with pytest.raises(ErrorLimiteLLM, match="todos los proveedores") as capturado:
        cadena.generar_estructurado("p", Requisito)
    assert (capturado.value.espera_s, capturado.value.diario) == (25.0, False)

    # Sin llamar a nadie mientras siguen apartados.
    reloj.ahora += 10
    with pytest.raises(ErrorLimiteLLM) as capturado:
        cadena.generar_estructurado("p", Requisito)
    assert capturado.value.espera_s == 15.0


def test_si_todos_fallan_por_red_no_se_presenta_como_limite():
    cadena = ProveedorEnCadena(
        [Simulado("groq", ErrorProveedorLLM("caído")), Simulado("ollama", ErrorProveedorLLM("x"))],
        reloj=Reloj(),
    )
    with pytest.raises(ErrorProveedorLLM, match="ningún proveedor") as capturado:
        cadena.generar_estructurado("p", Requisito)
    assert not isinstance(capturado.value, ErrorLimiteLLM)


def test_una_salida_invalida_no_cambia_de_proveedor():
    respaldo = Simulado("gemini")
    cadena = ProveedorEnCadena(
        [Simulado("groq", ErrorSalidaEstructurada("no cumple")), respaldo], reloj=Reloj()
    )
    with pytest.raises(ErrorSalidaEstructurada):
        cadena.generar_estructurado("p", Requisito)
    assert respaldo.prompts == []


def test_la_cadena_necesita_proveedores():
    with pytest.raises(ValueError):
        ProveedorEnCadena([])


# --- Fábrica -----------------------------------------------------------------------------------


def test_la_fabrica_activa_la_cache_por_defecto(tmp_path: Path):
    proveedor = crear_proveedor(
        configuracion=_config(llm_provider="ollama", llm_cache_dir=tmp_path)
    )
    assert isinstance(proveedor, ProveedorConCache)
    assert isinstance(proveedor.proveedor, ProveedorOllama)
    assert proveedor.carpeta == tmp_path


def test_la_fabrica_monta_el_respaldo_con_una_cache_por_proveedor(tmp_path: Path):
    config = _config(
        llm_provider="groq",
        groq_api_key="k",
        llm_respaldo=" Ollama, groq, ollama ,",
        llm_cache_dir=tmp_path,
        llm_modelo_rapido="openai/gpt-oss-120b",
        llm_modelo_razonamiento="openai/gpt-oss-120b",
        llm_esfuerzo_razonamiento="low",
    )
    cadena = crear_proveedor(configuracion=config)
    assert isinstance(cadena, ProveedorEnCadena)
    assert cadena.nombres == ["groq", "ollama"]  # sin repetir y sin el principal
    groq, ollama = (p.proveedor for p in cadena.proveedores)
    assert isinstance(groq, ProveedorGroq) and isinstance(ollama, ProveedorOllama)
    assert groq.modelos["rapido"] == "openai/gpt-oss-120b"
    assert groq.esfuerzo_razonamiento == "low"
    assert ollama.modelos["rapido"] == "llama3.1"  # LLM_MODELO_* es solo del principal


def test_la_fabrica_sin_cache_ni_respaldo():
    proveedor = crear_proveedor(configuracion=_config(llm_provider="ollama", llm_cache=False))
    assert isinstance(proveedor, ProveedorOllama)


def test_la_fabrica_rechaza_un_respaldo_desconocido_o_sin_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ErrorLLM, match="LLM_RESPALDO solo admite nombres"):
        crear_proveedor(configuracion=_config(llm_provider="ollama", llm_respaldo="otro"))
    with pytest.raises(ErrorLLM, match="GEMINI_API_KEY"):
        crear_proveedor(configuracion=_config(llm_provider="ollama", llm_respaldo="gemini"))


def test_la_configuracion_rechaza_un_esfuerzo_no_valido():
    with pytest.raises(ValueError):
        _config(llm_esfuerzo_razonamiento="maximo")


def test_uso_por_proveedor_suma_cache_y_cadena(tmp_path: Path):
    groq = Simulado("groq", ErrorLimiteLLM("límite", espera_s=5), ESPERADO)
    gemini = Simulado("gemini")
    cadena = ProveedorEnCadena(
        [ProveedorConCache(groq, tmp_path / "a"), ProveedorConCache(gemini, tmp_path / "b")],
        reloj=Reloj(),
    )
    cadena.generar_estructurado("p", Requisito)
    cadena.generar_estructurado("p", Requisito)  # gemini ya lo tiene en caché
    uso = uso_por_proveedor(cadena)
    assert uso["gemini"] == UsoLLM(llamadas=1, desde_cache=1, tokens_entrada=100)
    assert uso["groq"] == UsoLLM()
    assert describir_uso(cadena) == (
        "gemini: 1 llamadas al proveedor, 1 desde caché, 100 tokens (100 de entrada y 0 de salida)"
    )
    assert describir_uso(Simulado()) == "sin llamadas al LLM"


# --- Clasificación ante el límite ----------------------------------------------------------------

TEXTO = "# Tienda\n\n## 3. Cuenta\n\n1. El cliente se registra con su correo.\n"


class LLMQueClasifica(Simulado):
    def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
        if self.respuestas and isinstance(self.respuestas[0], Exception):
            self.prompts.append(prompt)
            raise self.respuestas.pop(0)
        ubicaciones = re.findall(r'<unidad-[0-9a-f]{8} ubicacion="([^"]+)">', prompt)
        return esquema.model_validate(
            {
                "clasificaciones": [
                    {
                        "ubicacion": u,
                        "es_requisito": True,
                        "tipo": "funcional",
                        "actor": "cliente",
                        "accion": "registrarse",
                        "entidades": ["Cliente"],
                        "servicio_sugerido": "usuarios",
                        "etiquetas": [],
                    }
                    for u in ubicaciones
                ]
            }
        )


def test_la_clasificacion_espera_lo_que_pide_el_proveedor():
    esperas: list[float] = []
    llm = LLMQueClasifica("groq", ErrorLimiteLLM("groq: límite", espera_s=7.5))
    pares = clasificar_unidades(segmentar(TEXTO), llm, dormir=esperas.append)
    assert esperas == [7.5]
    assert len(pares) == 1


@pytest.mark.parametrize(
    "error",
    [
        ErrorLimiteLLM("groq: cuota diaria agotada; se renueva en 7 min", 432, diario=True),
        ErrorLimiteLLM("groq: límite de peticiones alcanzado", espera_s=600),
    ],
)
def test_la_clasificacion_no_espera_si_la_cuota_no_vuelve_pronto(error):
    with pytest.raises(ErrorLimiteLLM) as capturado:
        clasificar_unidades(segmentar(TEXTO), LLMQueClasifica("groq", error), dormir=pytest.fail)
    assert capturado.value is error


# --- CLI ---------------------------------------------------------------------------------------


def test_llm_estado_no_muestra_las_claves(monkeypatch, tmp_path: Path):
    config = _config(
        llm_provider="groq",
        groq_api_key="clave-super-secreta",
        llm_respaldo="ollama",
        llm_cache_dir=tmp_path,
    )
    monkeypatch.setattr("orchestrator.cli.obtener_configuracion", lambda: config)
    resultado = runner.invoke(app, ["llm", "estado"])
    assert resultado.exit_code == 0, resultado.output
    assert "clave-super-secreta" not in resultado.output
    assert "groq: clave definida" in resultado.output
    assert "Respaldo: ollama" in resultado.output
    assert "0 respuestas" in resultado.output


def test_llm_probar_informa_cada_proveedor(monkeypatch):
    config = _config(llm_provider="groq", groq_api_key="k", llm_respaldo="ollama")
    monkeypatch.setattr("orchestrator.cli.obtener_configuracion", lambda: config)
    adaptadores = {
        "groq": Simulado("groq", ErrorLimiteLLM("groq: cuota diaria agotada", 60, diario=True)),
        "ollama": Simulado("ollama", ErrorProveedorLLM("ollama: no se pudo conectar")),
    }
    monkeypatch.setattr(
        "orchestrator.llm.crear_adaptador", lambda nombre, *_, **__: adaptadores[nombre]
    )
    resultado = runner.invoke(app, ["llm", "probar"])
    assert resultado.exit_code == 1
    assert "groq: sin cuota ahora mismo (groq: cuota diaria agotada)" in resultado.output
    assert "ollama: no responde (ollama: no se pudo conectar)" in resultado.output


def test_llm_vaciar_cache(monkeypatch, tmp_path: Path):
    ProveedorConCache(Simulado(), tmp_path).generar_estructurado("p", Requisito)
    monkeypatch.setattr(
        "orchestrator.cli.obtener_configuracion", lambda: _config(llm_cache_dir=tmp_path)
    )
    resultado = runner.invoke(app, ["llm", "vaciar-cache"])
    assert "Respuestas borradas" in resultado.output and ": 1" in resultado.output
    assert estadisticas(tmp_path) == (0, 0)


def test_el_esquema_para_gemini_quita_max_items_y_conserva_lo_demas():
    from orchestrator.ingest.clasificacion import ClasificacionSeccion
    from orchestrator.llm.gemini import esquema_para_gemini

    original = json.dumps(ClasificacionSeccion.model_json_schema())
    enviado = json.dumps(esquema_para_gemini(ClasificacionSeccion))
    assert '"maxItems"' in original and '"maxItems"' not in enviado
    assert enviado.count('"additionalProperties": false') == original.count(
        '"additionalProperties": false'
    )
    assert '"enum"' in enviado and '"$ref"' in enviado


CLAVE_PEGADA = "AQ.Ab8RN6iwFalsaParaLaPrueba_0123456789abcdef"


def test_una_clave_pegada_en_una_variable_de_proveedor_nunca_se_muestra(monkeypatch):
    """Caso real: la clave de Gemini acabó también en LLM_RESPALDO."""
    for config in (
        _config(llm_provider="groq", groq_api_key="k", llm_respaldo=CLAVE_PEGADA),
        _config(llm_provider=CLAVE_PEGADA),
    ):
        with pytest.raises(ErrorLLM) as capturado:
            crear_proveedor(configuracion=config)
        assert CLAVE_PEGADA.lower() not in str(capturado.value).lower()

        monkeypatch.setattr("orchestrator.cli.obtener_configuracion", lambda c=config: c)
        for comando in (["llm", "estado"], ["llm", "probar"]):
            salida = runner.invoke(app, comando).output
            assert CLAVE_PEGADA.lower() not in salida.lower(), comando

    resumen = _config(llm_respaldo=f"gemini,{CLAVE_PEGADA}").resumen()
    assert resumen["llm_respaldo"] == ["gemini"]
    assert CLAVE_PEGADA.lower() not in str(resumen).lower()


def test_la_clasificacion_acepta_ubicaciones_con_entidades_html():
    """Gemini devolvió «11, p&aacute;rrafo 1» en vez de «11, párrafo 1»."""

    class LLMQueEscapa(LLMQueClasifica):
        def generar_estructurado(self, prompt, esquema, nivel="rapido", sistema=None):
            respuesta = super().generar_estructurado(prompt, esquema, nivel, sistema)
            for clasificacion in respuesta.clasificaciones:
                clasificacion.ubicacion = clasificacion.ubicacion.replace("á", "&aacute;")
            return respuesta

    texto = "# Tienda\n\n## 11. Fuera del alcance\n\nLa tienda no vende fuera del país.\n"
    pares = clasificar_unidades(segmentar(texto), LLMQueEscapa("gemini"))
    assert [u.ubicacion for u, _ in pares] == ["11, párrafo 1"]


def test_una_clave_invalida_se_explica_sin_el_cuerpo_del_proveedor():
    peticion = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    error = openai.AuthenticationError(
        "Error code: 401 - {'error': {'message': 'Invalid API Key'}}",
        response=httpx.Response(401, request=peticion),
        body=None,
    )
    cliente, _ = _cliente_groq(error)
    with pytest.raises(ErrorProveedorLLM) as capturado:
        ProveedorGroq(cliente=cliente).generar_estructurado("x", Requisito)
    assert str(capturado.value) == "groq: la clave GROQ_API_KEY no es válida (401)"
