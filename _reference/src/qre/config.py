from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_prefix="",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://localhost:5432/qre"

    openai_api_key: str | None = None
    answer_model: str = Field(default="gpt-4o-mini", alias="QRE_ANSWER_MODEL")

    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5", alias="QRE_EMBEDDING_MODEL")
    rerank_model: str = Field(default="BAAI/bge-reranker-base", alias="QRE_RERANK_MODEL")
    embedding_dim: int = 384

    retrieval_top_k: int = Field(default=25, alias="QRE_RETRIEVAL_TOP_K")
    rerank_top_n: int = Field(default=5, alias="QRE_RERANK_TOP_N")
    min_confidence: float = Field(default=0.45, alias="QRE_MIN_CONFIDENCE")


@lru_cache
def get_settings() -> Settings:
    return Settings()
