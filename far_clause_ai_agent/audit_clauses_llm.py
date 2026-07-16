from __future__ import annotations

import asyncio

from string import Template

from .extract_clauses import classify_clause, extract_clause_mentions
from .llm_client import LLMClient


AUDIT_PROMPT = Template(
    """SYSTEM:
You are a government proposal compliance reviewer. Use ONLY the text provided. Do not infer requirements beyond the provided clause text. Output JSON only.
USER:
Extract clause identifiers mentioned in the text below. Do not infer applicability. Output JSON only.
text:
$text
Return JSON:
{ "clause_ids": ["52.212-4", "252.204-7012", "3052.204-71"] }
"""
)


def build_audit_prompt(text: str) -> str:
    return AUDIT_PROMPT.safe_substitute(text=text)


def llm_extract_clause_ids(chunks: list[dict[str, object]], client: LLMClient | None = None) -> list[dict[str, object]]:
    text = "\n".join(str(chunk.get("text", "")) for chunk in chunks)
    if client is None:
        return extract_clause_mentions(text)

    prompt = build_audit_prompt(text)
    response = asyncio.run(client.call_json(prompt, fixture_name="audit_clauses.json"))
    if response.get("_error") == "LLMParseError":
        return []

    clause_ids = response.get("clause_ids", [])
    mentions: list[dict[str, object]] = []
    for clause_id in clause_ids:
        clause_id_text = str(clause_id)
        mentions.append(
            {
                "clause_ref_raw": clause_id_text,
                "clause_id_normalized": clause_id_text,
                "family": classify_clause(clause_id_text),
                "title_guess": None,
                "date_guess": None,
                "alternate_guess": None,
                "citations": [{"doc_id": "", "start_char": 0, "end_char": 0, "quote": clause_id_text}],
            }
        )
    return mentions or extract_clause_mentions(text)
