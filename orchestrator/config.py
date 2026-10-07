"""Configuración del motor, leída de variables de entorno y del archivo .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Configuracion(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    llm_provider: str = "gemini"
    gemini_api_key: SecretStr | None = None

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr | None = None

    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    max_iteraciones: int = Field(default=5, ge=1, le=20)
    directorio_salida: Path = Path("salida")

    def resumen(self) -> dict[str, object]:
        """Valores visibles de la configuración; de los secretos solo indica si están definidos."""
        return {
            "llm_provider": self.llm_provider,
            "llm_api_key_definida": self.gemini_api_key is not None,
            "neo4j_uri": self.neo4j_uri,
            "neo4j_user": self.neo4j_user,
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
