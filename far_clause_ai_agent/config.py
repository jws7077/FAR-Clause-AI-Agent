from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Config:
    corpus_root: Path = Path("data/corpus")
    fixtures_root: Path = Path("tests/fixtures")
    chunk_size: int = 2000
    overlap: int = 200
    clause_context_window: int = 600
    search_top_k: int = 5
    concurrency_limit: int = 5
    retry_attempts: int = 3
    retry_backoff_seconds: float = 0.5
    model_name: str = "gpt-5.4-mini"
    mock_llm: bool = False


def load_config() -> Config:
    return Config(
        corpus_root=Path(os.getenv("CORPUS_ROOT", "data/corpus")),
        fixtures_root=Path(os.getenv("FIXTURES_ROOT", "tests/fixtures")),
        chunk_size=int(os.getenv("CHUNK_SIZE", "2000")),
        overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
        clause_context_window=int(os.getenv("CLAUSE_CONTEXT_WINDOW", "600")),
        search_top_k=int(os.getenv("SEARCH_TOP_K", "5")),
        concurrency_limit=int(os.getenv("LLM_CONCURRENCY_LIMIT", "5")),
        retry_attempts=int(os.getenv("LLM_RETRY_ATTEMPTS", "3")),
        retry_backoff_seconds=float(os.getenv("LLM_RETRY_BACKOFF_SECONDS", "0.5")),
        model_name=os.getenv("LLM_MODEL", "gpt-5.4-mini"),
        mock_llm=os.getenv("MOCK_LLM", "0") == "1",
    )
