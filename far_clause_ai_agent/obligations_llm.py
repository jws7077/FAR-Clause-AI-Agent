from __future__ import annotations

import asyncio
from string import Template

from .llm_client import LLMClient, maybe_flag_parse_error, verify_quote
from .scoring import is_mandatory


OBLIGATIONS_PROMPT = Template(
    """SYSTEM:
You are a government proposal compliance reviewer. Use ONLY the text provided. Do not infer requirements beyond the provided clause text. Output JSON only.
USER:
Extract 3-10 proposal-relevant obligations from this clause. Each obligation must be testable.
For each obligation include:
- requirement (one sentence)
- clause_quote (exact quote from clause text supporting it)
- search_queries (3-6 phrases likely to appear in a proposal)
clause_id: $clause_id
family: $family
date: $date
clause_text:
$clause_text
Return JSON.
"""
)


def build_obligations_prompt(clause_id: str, family: str, date: str | None, clause_text: str) -> str:
    return OBLIGATIONS_PROMPT.safe_substitute(
        clause_id=clause_id,
        family=family,
        date=date or "",
        clause_text=clause_text,
    )


def extract_obligations(
    clause_id: str,
    canonical_text: str,
    metadata: dict[str, object] | None = None,
    client: LLMClient | None = None,
) -> list[dict[str, object]]:
    metadata = metadata or {}
    if client is not None:
        prompt = build_obligations_prompt(
            clause_id,
            str(metadata.get("family", "UNKNOWN")),
            str(metadata.get("date_guess") or ""),
            canonical_text,
        )
        response = asyncio.run(client.call_json(prompt, fixture_name="obligations.json"))
        if response.get("_error") == "LLMParseError":
            return [maybe_flag_parse_error(str(response.get("raw", "")), clause_id)]

        obligations: list[dict[str, object]] = []
        for item in response.get("obligations", []):
            original_quote = item.get("clause_quote")
            quote = original_quote
            if not verify_quote(str(quote) if quote is not None else None, canonical_text):
                quote = None
            obligations.append(
                {
                    "clause_id_normalized": clause_id,
                    "obligation_id": str(item.get("obligation_id", f"O{len(obligations) + 1}")),
                    "requirement": str(item.get("requirement", "")),
                    "clause_quote": quote,
                    "raw_clause_quote": original_quote,
                    "search_queries": list(item.get("search_queries", [])),
                }
            )
        return obligations

    quote = canonical_text[:180]
    obligation = {
        "clause_id_normalized": clause_id,
        "obligation_id": "O1",
        "requirement": "Comply with the clause requirements as written.",
        "clause_quote": quote if verify_quote(quote, canonical_text) else None,
        "raw_clause_quote": quote,
        "search_queries": ["comply", "requirements", clause_id],
    }
    if not obligation["clause_quote"]:
        obligation["clause_quote"] = None
    if is_mandatory(canonical_text):
        obligation["requirement"] = "Meet the mandatory requirement stated in the clause."
    return [obligation]
