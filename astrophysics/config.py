from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    primary: str = Field(default="local", validation_alias=AliasChoices("ASTRO_PRIMARY", "PRIMARY"))
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL"),
    )
    ollama_model: str = Field(default="llama3.2", validation_alias=AliasChoices("OLLAMA_MODEL"))

    openai_api_key: str = Field(default="", validation_alias=AliasChoices("OPENAI_API_KEY"))
    openai_base_url: str = Field(
        default="https://api.openai.com/v1",
        validation_alias=AliasChoices("OPENAI_BASE_URL"),
    )
    openai_model: str = Field(default="gpt-4o-mini", validation_alias=AliasChoices("OPENAI_MODEL"))

    anthropic_api_key: str = Field(default="", validation_alias=AliasChoices("ANTHROPIC_API_KEY"))
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com",
        validation_alias=AliasChoices("ANTHROPIC_BASE_URL"),
    )
    anthropic_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        validation_alias=AliasChoices("ANTHROPIC_MODEL"),
    )

    enable_image_gen: bool = Field(
        default=False,
        validation_alias=AliasChoices("ASTRO_ENABLE_IMAGE_GEN", "ENABLE_IMAGE_GEN"),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


ASTRO_SYSTEM_PROMPT = """You are a careful astrophysics tutor. Explain concepts at the user's level,
use precise terminology, and distinguish established theory from speculative or uncertain areas when relevant.
Prefer short paragraphs and headings; when a diagram helps, suggest mermaid fenced blocks (flowchart/graph)
ONLY when confident in the notation. Mention that illustrative figures are interpretations, not data.
Never claim exclusive access to 'latest unpublished' results."""
