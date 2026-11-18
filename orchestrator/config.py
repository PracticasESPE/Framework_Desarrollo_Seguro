"""Configuración del motor, leída de variables de entorno y del archivo .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

PROVEEDORES_LLM: tuple[str, ...] = ("gemini", "groq", "claude", "ollama")


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    llm_provider: str = "groq"
    gemini_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    ollama_host: str = "http://localhost:11434"
    # Si no se definen, cada adaptador usa sus modelos por defecto.
    llm_modelo_rapido: str | None = None
    llm_modelo_razonamiento: str | None = None
    llm_max_intentos: int = Field(default=3, ge=1, le=10)
    # Proveedores de respaldo, en orden, separados por comas (p. ej. "gemini,ollama"). Vacío: no
    # hay respaldo. La evaluación de la tesis debe correr sin respaldo (orchestrator/llm/README).
    llm_respaldo: str = ""
    # Caché en disco de las respuestas: repetir un documento no gasta cuota.
    llm_cache: bool = True
    llm_cache_dir: Path = Path(".cache/llm")
    # Esfuerzo de razonamiento de los modelos gpt-oss en Groq (low, medium o high). Vacío: el de
    # Groq. Menos esfuerzo gasta menos tokens de la cuota.
    llm_esfuerzo_razonamiento: Literal["low", "medium", "high"] | None = None

    # Modelo local de embeddings (fastembed) y carpeta donde se guarda tras descargarlo.
    embeddings_modelo: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embeddings_cache: Path = Path(".cache/fastembed")

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr | None = None
    neo4j_database: str = "neo4j"

    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    max_iteraciones: int = Field(default=5, ge=1, le=20)
    directorio_salida: Path = Path("salida")

    def resumen(self) -> dict[str, object]:
        """Valores visibles de la configuración; de los secretos solo indica si están definidos."""
        return {
            "llm_provider": self.llm_provider,
            "gemini_api_key_definida": self.gemini_api_key is not None,
            "anthropic_api_key_definida": self.anthropic_api_key is not None,
            "groq_api_key_definida": self.groq_api_key is not None,
            "ollama_host": self.ollama_host,
            # Solo los nombres reconocidos: el valor crudo podría ser una clave pegada por error.
            "llm_respaldo": [
                n
                for n in (p.strip().lower() for p in self.llm_respaldo.split(","))
                if n in PROVEEDORES_LLM
            ],
            "llm_cache": self.llm_cache,
            "llm_esfuerzo_razonamiento": self.llm_esfuerzo_razonamiento,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
            "neo4j_database": self.neo4j_database,
            "embeddings_modelo": self.embeddings_modelo,
            "neo4j_password_definida": self.neo4j_password is not None,
            "telegram_configurado": (
                self.telegram_bot_token is not None and self.telegram_chat_id is not None
            ),
            "max_iteraciones": self.max_iteraciones,
            "directorio_salida": str(self.directorio_salida),
        }


@lru_cache
def obtener_configuracion() -> Configuracion:
    return Configuracion()
