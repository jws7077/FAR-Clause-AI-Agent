from __future__ import annotations

import math
import re
from collections import Counter


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-']+")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_PATTERN.findall(text)]


def search_snippets(proposal_docs: list[dict[str, object]], queries: list[str], top_k: int = 5) -> list[dict[str, object]]:
    query_tokens = Counter()
    for query in queries:
        query_tokens.update(_tokenize(query))

    scored: list[dict[str, object]] = []
    for doc in proposal_docs:
        doc_id = str(doc.get("doc_id", "doc"))
        for chunk in doc.get("chunks", []):
            text = str(chunk.get("text", ""))
            chunk_tokens = Counter(_tokenize(text))
            if not chunk_tokens:
                continue
            overlap = sum(min(query_tokens[token], chunk_tokens[token]) for token in query_tokens)
            if not overlap:
                continue
            score = overlap / math.sqrt(sum(chunk_tokens.values()))
            scored.append(
                {
                    "doc_id": doc_id,
                    "start_char": int(chunk.get("start_char", 0)),
                    "end_char": int(chunk.get("end_char", 0)),
                    "quote": text[:500],
                    "score": round(score, 4),
                }
            )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return scored[:top_k]
