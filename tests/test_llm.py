"""Pruebas de los adaptadores de LLM con clientes simulados (sin llamadas de red)."""

from types import SimpleNamespace

import anthropic
import httpx2
import ollama
import pytest
from google.genai import errors as errores_gemini
from pydantic import BaseModel

from orchestrator.config import Configuracion
from orchestrator.llm import (
    ErrorLLM,
    ErrorProveedorLLM,
    ErrorSalidaEstructurada,
    ProveedorLLM,
    crear_proveedor,
)
from orchestrator.llm.claude import ProveedorClaude
from orchestrator.llm.gemini import ProveedorGemini
from orchestrator.llm.ollama import ProveedorOllama


class Requisito(BaseModel):
    id: str
    tipo: str
    etiquetas: list[str]


VALIDO = '{"id": "RF-01", "tipo": "funcional", "etiquetas": ["autenticacion"]}'
INCOMPLETO = '{"id": "RF-01"}'
ESPERADO = Requisito(id="RF-01", tipo="funcional", etiquetas=["autenticacion"])


class Grabadora:
    """Devuelve las respuestas en orden y guarda los argumentos de cada llamada."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas: list[dict] = []

    def __call__(self, **kwargs):
        self.llamadas.append(kwargs)
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, Exception):
            raise respuesta
        return respuesta


# --- Claude -----------------------------------------------------------------------------


def _respuesta_claude(parsed=ESPERADO, stop_reason="end_turn"):
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason)


def _cliente_claude(*respuestas):
    normal, beta = Grabadora(*respuestas), Grabadora(*respuestas)
    cliente = SimpleNamespace(
        messages=SimpleNamespace(parse=normal),
        beta=SimpleNamespace(messages=SimpleNamespace(parse=beta)),
    )
    return cliente, normal, beta


def test_claude_nivel_rapido_usa_haiku_sin_fallbacks():
    cliente, normal, beta = _cliente_claude(_respuesta_claude())
    resultado = ProveedorClaude(cliente=cliente).generar_estructurado("extrae", Requisito)

    assert resultado == ESPERADO
    assert beta.llamadas == []
    llamada = normal.llamadas[0]
    assert llamada["model"] == "claude-haiku-4-5"
    assert llamada["output_format"] is Requisito
    assert "temperature" not in llamada


def test_claude_nivel_razonamiento_usa_opus_con_fallbacks():
    cliente, normal, beta = _cliente_claude(_respuesta_claude())
    ProveedorClaude(cliente=cliente).generar_estructurado(
        "propón", Requisito, nivel="razonamiento", sistema="Eres arquitecto"
    )

    assert normal.llamadas == []
    llamada = beta.llamadas[0]
    assert llamada["model"] == "claude-opus-5-5"
    assert llamada["fallbacks"] == "default"
    assert llamada["betas"] == ["server-side-fallback-2026-07-01"]
    assert llamada["system"] == "Eres arquitecto"


def test_claude_rechazo_del_modelo():
    cliente, _, _ = _cliente_claude(_respuesta_claude(parsed=None, stop_reason="refusal"))
    with pytest.raises(ErrorProveedorLLM, match="rechazó"):
        ProveedorClaude(cliente=cliente).generar_estructurado("x", Requisito)


def test_claude_respuesta_cortada():
    cliente, _, _ = _cliente_claude(_respuesta_claude(parsed=None, stop_reason="max_tokens"))
    with pytest.raises(ErrorProveedorLLM, match="límite de tokens"):
        ProveedorClaude(cliente=cliente).generar_estructurado("x", Requisito)


def test_claude_error_de_conexion():
    error = anthropic.APIConnectionError(
        request=httpx2.Request("POST", "https://api.anthropic.com")
    )
    cliente, _, _ = _cliente_claude(error)
    with pytest.raises(ErrorProveedorLLM, match="conectar"):
        ProveedorClaude(cliente=cliente).generar_estructurado("x", Requisito)


# --- Gemini -----------------------------------------------------------------------------


def _cliente_gemini(*textos):
    respuestas = [t if isinstance(t, Exception) else SimpleNamespace(text=t) for t in textos]
    generar = Grabadora(*respuestas)
    return SimpleNamespace(models=SimpleNamespace(generate_content=generar)), generar


def test_gemini_devuelve_el_esquema_validado():
    cliente, generar = _cliente_gemini(VALIDO)
    resultado = ProveedorGemini(cliente=cliente).generar_estructurado(
        "extrae", Requisito, sistema="Eres analista"
    )

    assert resultado == ESPERADO
    llamada = generar.llamadas[0]
    assert llamada["model"] == "gemini-3.5-flash-lite"
    assert llamada["contents"] == "extrae"
    assert llamada["config"]["response_mime_type"] == "application/json"
    assert llamada["config"]["response_schema"] is Requisito
    assert llamada["config"]["temperature"] == 0.1
    assert llamada["config"]["system_instruction"] == "Eres analista"


def test_gemini_reintenta_si_la_salida_no_cumple_el_esquema():
    cliente, generar = _cliente_gemini(INCOMPLETO, "no es json", VALIDO)
    resultado = ProveedorGemini(cliente=cliente).generar_estructurado("extrae", Requisito)

    assert resultado == ESPERADO
    assert len(generar.llamadas) == 3


def test_gemini_agota_los_intentos():
    cliente, generar = _cliente_gemini(INCOMPLETO, INCOMPLETO)
    proveedor = ProveedorGemini(cliente=cliente, max_intentos=2)
    with pytest.raises(ErrorSalidaEstructurada, match="2 intento"):
        proveedor.generar_estructurado("extrae", Requisito)
    assert len(generar.llamadas) == 2


def test_gemini_respuesta_vacia():
    cliente, _ = _cliente_gemini(None)
    with pytest.raises(ErrorProveedorLLM, match="vacía"):
        ProveedorGemini(cliente=cliente).generar_estructurado("x", Requisito)


def test_gemini_error_de_la_api():
    error = errores_gemini.APIError(429, {"error": {"message": "cuota agotada"}})
    cliente, _ = _cliente_gemini(error)
    with pytest.raises(ErrorProveedorLLM, match="429"):
        ProveedorGemini(cliente=cliente).generar_estructurado("x", Requisito)


# --- Ollama -----------------------------------------------------------------------------


def _cliente_ollama(*contenidos):
    respuestas = [
        c if isinstance(c, Exception) else SimpleNamespace(message=SimpleNamespace(content=c))
        for c in contenidos
    ]
    chat = Grabadora(*respuestas)
    return SimpleNamespace(chat=chat), chat


def test_ollama_devuelve_el_esquema_validado():
    cliente, chat = _cliente_ollama(VALIDO)
    resultado = ProveedorOllama(cliente=cliente).generar_estructurado(
        "extrae", Requisito, nivel="razonamiento", sistema="Eres analista"
    )

    assert resultado == ESPERADO
    llamada = chat.llamadas[0]
    assert llamada["model"] == "qwen2.5-coder"
    assert llamada["format"] == Requisito.model_json_schema()
    assert llamada["options"] == {"temperature": 0.1}
    assert llamada["messages"] == [
        {"role": "system", "content": "Eres analista"},
        {"role": "user", "content": "extrae"},
    ]


def test_ollama_reintenta_si_la_salida_no_cumple_el_esquema():
    cliente, chat = _cliente_ollama(INCOMPLETO, VALIDO)
    assert ProveedorOllama(cliente=cliente).generar_estructurado("x", Requisito) == ESPERADO
    assert len(chat.llamadas) == 2


def test_ollama_servidor_apagado():
    cliente, _ = _cliente_ollama(ConnectionError("sin servidor"))
    with pytest.raises(ErrorProveedorLLM, match="conectar"):
        ProveedorOllama(cliente=cliente).generar_estructurado("x", Requisito)


def test_ollama_error_del_servidor():
    cliente, _ = _cliente_ollama(ollama.ResponseError("modelo no encontrado", 404))
    with pytest.raises(ErrorProveedorLLM, match="modelo no encontrado"):
        ProveedorOllama(cliente=cliente).generar_estructurado("x", Requisito)


# --- Comportamiento común y fábrica -----------------------------------------------------


@pytest.mark.parametrize("clase", [ProveedorClaude, ProveedorGemini, ProveedorOllama])
def test_los_adaptadores_cumplen_la_interfaz(clase):
    assert isinstance(clase(cliente=SimpleNamespace()), ProveedorLLM)


def test_nivel_desconocido():
    cliente, _ = _cliente_gemini(VALIDO)
    with pytest.raises(ValueError, match="Nivel desconocido"):
        ProveedorGemini(cliente=cliente).generar_estructurado("x", Requisito, nivel="otro")


def test_modelos_incompletos():
    with pytest.raises(ValueError, match="razonamiento"):
        ProveedorGemini(cliente=SimpleNamespace(), modelos={"rapido": "gemini-3.5-flash-lite"})


def _config(**valores) -> Configuracion:
    return Configuracion(_env_file=None, **valores)


def test_fabrica_crea_cada_proveedor():
    assert isinstance(
        crear_proveedor(configuracion=_config(llm_provider="gemini", gemini_api_key="k")),
        ProveedorGemini,
    )
    assert isinstance(
        crear_proveedor(configuracion=_config(llm_provider="claude", anthropic_api_key="k")),
        ProveedorClaude,
    )
    assert isinstance(
        crear_proveedor(configuracion=_config(llm_provider="ollama")), ProveedorOllama
    )


def test_fabrica_aplica_los_modelos_configurados():
    proveedor = crear_proveedor(
        configuracion=_config(
            llm_provider="ollama", llm_modelo_rapido="a", llm_modelo_razonamiento="b"
        )
    )
    assert proveedor.modelos == {"rapido": "a", "razonamiento": "b"}


def test_fabrica_exige_la_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ErrorLLM, match="GEMINI_API_KEY"):
        crear_proveedor(configuracion=_config(llm_provider="gemini"))


def test_fabrica_rechaza_proveedor_desconocido():
    with pytest.raises(ErrorLLM, match="desconocido"):
        crear_proveedor(configuracion=_config(llm_provider="otro"))
