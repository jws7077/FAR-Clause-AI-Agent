from __future__ import annotations

import asyncio
from string import Template

from .llm_client import LLMClient, maybe_flag_parse_error


CONFLICT_PROMPT = Template(
    """SYSTEM:
Identify potential conflicts between a mandatory obligation and proposal language. Use ONLY the provided texts. Output JSON only.
USER:
Obligation:
$requirement
Clause quote:
$clause_quote
Proposal excerpts:
1) $snippet_1
2) $snippet_2
3) $snippet_3
Return JSON.
"""
)


RISK_PHRASES = [
    "TBD",
    "to be determined",
    "as available",
    "best effort",
    "if requested",
    "when possible",
    "may",
    "could",
    "anticipated",
    "target",
    "subject to",
    "as needed",
    "optional",
    "at our discretion",
]


def build_conflict_prompt(requirement: str, clause_quote: str, snippets: list[str]) -> str:
    padded = snippets + ["", "", ""]
    return CONFLICT_PROMPT.safe_substitute(
        requirement=requirement,
        clause_quote=clause_quote,
        snippet_1=padded[0],
        snippet_2=padded[1],
        snippet_3=padded[2],
    )


def detect_conflicts(obligation: dict[str, object], snippets: list[dict[str, object]], client: LLMClient | None = None) -> dict[str, object]:
    if client is not None:
        prompt = build_conflict_prompt(
            str(obligation.get("requirement", "")),
            str(obligation.get("clause_quote", "")),
            [str(snippet.get("quote", "")) for snippet in snippets[:3]],
        )
        response = asyncio.run(client.call_json(prompt, fixture_name="conflicts.json"))
        if response.get("_error") == "LLMParseError":
            return maybe_flag_parse_error(str(response.get("raw", "")), str(obligation.get("clause_id_normalized", "")), str(obligation.get("obligation_id")))
        return {
            "conflict": bool(response.get("conflict", False)),
            "conflict_quote": str(response.get("conflict_quote", "Not found")),
            "rationale": str(response.get("rationale", "")),
            "confidence": float(response.get("confidence", 0.0)),
        }

    combined = " ".join(str(snippet.get("quote", "")) for snippet in snippets).lower()
    conflict_phrase = next((phrase for phrase in RISK_PHRASES if phrase.lower() in combined), None)
    if conflict_phrase:
        return {
            "conflict": True,
            "conflict_quote": conflict_phrase,
            "rationale": "Proposal language includes a non-committal risk phrase.",
            "confidence": 0.7,
        }
    return {
        "conflict": False,
        "conflict_quote": "Not found",
        "rationale": "No obvious conflict phrase found.",
        "confidence": 0.2,
    }
