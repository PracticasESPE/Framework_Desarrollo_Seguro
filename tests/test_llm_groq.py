"""Pruebas del adaptador de Groq con un cliente simulado (sin llamadas de red)."""

from types import SimpleNamespace

import httpx
import openai
import pytest
from pydantic import BaseModel

from orchestrator.config import Configuracion
from orchestrator.llm import ErrorLLM, ErrorProveedorLLM, ProveedorLLM, crear_proveedor
from orchestrator.llm.groq import ProveedorGroq


class Requisito(BaseModel):
    id: str
    tipo: str


VALIDO = '{"id": "RF-01", "tipo": "funcional"}'
ESPERADO = Requisito(id="RF-01", tipo="funcional")


def _cliente(*contenidos):
    llamadas: list[dict] = []
    pendientes = list(contenidos)

    def create(**kwargs):
        llamadas.append(kwargs)
        contenido = pendientes.pop(0)
        if isinstance(contenido, Exception):
            raise contenido
        mensaje = SimpleNamespace(content=contenido)
        return SimpleNamespace(choices=[SimpleNamespace(message=mensaje)])

    cliente = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    return cliente, llamadas


def test_groq_devuelve_el_esquema_validado():
    cliente, llamadas = _cliente(VALIDO)
    proveedor = ProveedorGroq(cliente=cliente)
    resultado = proveedor.generar_estructurado(
        "extrae", Requisito, nivel="razonamiento", sistema="Eres analista"
    )

    assert isinstance(proveedor, ProveedorLLM)
    assert resultado == ESPERADO
    llamada = llamadas[0]
    assert llamada["model"] == "openai/gpt-oss-120b"
    assert llamada["temperature"] == 0.1
    assert llamada["max_completion_tokens"] == 16384
    assert llamada["messages"] == [
        {"role": "system", "content": "Eres analista"},
        {"role": "user", "content": "extrae"},
    ]
    assert llamada["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "Requisito", "schema": Requisito.model_json_schema()},
    }


def test_groq_reintenta_si_la_salida_no_cumple_el_esquema():
    cliente, llamadas = _cliente('{"id": "RF-01"}', VALIDO)
    assert ProveedorGroq(cliente=cliente).generar_estructurado("x", Requisito) == ESPERADO
    assert len(llamadas) == 2
    assert llamadas[0]["model"] == "openai/gpt-oss-20b"


def _json_rechazado(generado: str) -> openai.BadRequestError:
    """El error 400 que da Groq cuando el JSON del modelo no cumple el esquema."""
    peticion = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    cuerpo = {
        "message": "Failed to validate JSON.",
        "type": "invalid_request_error",
        "code": "json_validate_failed",
        "failed_generation": generado,
    }
    return openai.BadRequestError(
        "Error code: 400", response=httpx.Response(400, request=peticion), body=cuerpo
    )


def test_groq_reintenta_si_rechaza_el_json_del_modelo():
    cliente, llamadas = _cliente(_json_rechazado(""), _json_rechazado('{"id": 1}'), VALIDO)
    assert ProveedorGroq(cliente=cliente).generar_estructurado("x", Requisito) == ESPERADO
    assert len(llamadas) == 3


def test_groq_json_rechazado_en_todos_los_intentos():
    cliente, _ = _cliente(*[_json_rechazado("")] * 3)
    with pytest.raises(ErrorLLM, match="no cumplió el esquema"):
        ProveedorGroq(cliente=cliente).generar_estructurado("x", Requisito)


def test_groq_otro_error_400_no_se_reintenta():
    peticion = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    error = openai.BadRequestError(
        "modelo inexistente",
        response=httpx.Response(400, request=peticion),
        body={"code": "model_not_found"},
    )
    cliente, llamadas = _cliente(error, VALIDO)
    with pytest.raises(ErrorProveedorLLM, match="error 400"):
        ProveedorGroq(cliente=cliente).generar_estructurado("x", Requisito)
    assert len(llamadas) == 1


def test_groq_respuesta_vacia():
    cliente, _ = _cliente(None)
    with pytest.raises(ErrorProveedorLLM, match="vacía"):
        ProveedorGroq(cliente=cliente).generar_estructurado("x", Requisito)


def test_groq_error_de_conexion():
    peticion = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    cliente, _ = _cliente(openai.APIConnectionError(request=peticion))
    with pytest.raises(ErrorProveedorLLM, match="conectar"):
        ProveedorGroq(cliente=cliente).generar_estructurado("x", Requisito)


def test_fabrica_crea_groq_y_exige_su_clave(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    con_clave = Configuracion(_env_file=None, llm_provider="groq", groq_api_key="k")
    assert isinstance(crear_proveedor(configuracion=con_clave), ProveedorGroq)

    sin_clave = Configuracion(_env_file=None, llm_provider="groq")
    with pytest.raises(ErrorLLM, match="GROQ_API_KEY"):
        crear_proveedor(configuracion=sin_clave)
