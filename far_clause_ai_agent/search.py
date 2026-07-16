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


def search_snippets_with_context(
    proposal_docs: list[dict[str, object]],
    queries: list[str],
    top_k: int = 5,
    context_window: int = 500,
) -> list[dict[str, object]]:
    snippets = search_snippets(proposal_docs, queries, top_k=top_k)
    enriched: list[dict[str, object]] = []
    for snippet in snippets:
        doc_id = snippet["doc_id"]
        start_char = int(snippet["start_char"])
        end_char = int(snippet["end_char"])
        quote = snippet["quote"]

        source_text = ""
        for doc in proposal_docs:
            if str(doc.get("doc_id", "")) == doc_id:
                source_text = str(doc.get("text", ""))
                break

        if source_text:
            context_start = max(0, start_char - context_window)
            context_end = min(len(source_text), end_char + context_window)
            quote = source_text[context_start:context_end]

        enriched.append(
            {
                **snippet,
                "quote": quote,
            }
        )
    return enriched
