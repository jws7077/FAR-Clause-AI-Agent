from __future__ import annotations

import asyncio
import re
from string import Template

from .llm_client import LLMClient, maybe_flag_parse_error, verify_quote


COVERAGE_PROMPT = Template(
    """SYSTEM:
You are a compliance checker. Use ONLY the obligations and proposal excerpts provided. If evidence is weak or indirect, mark Unclear. Output JSON only.
USER:
Clause: $clause_id
For EACH obligation below, decide coverage using only its own listed excerpts.
Obligations:
$obligations
Return JSON.
"""
)


def build_coverage_prompt(clause_id: str, obligations_block: str) -> str:
    return COVERAGE_PROMPT.safe_substitute(clause_id=clause_id, obligations=obligations_block)


def _tokenize(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9\-']+", text)}


def _evidence_is_strong(obligation: dict[str, object], snippets: list[dict[str, object]]) -> bool:
    if not snippets:
        return False
    top_snippet = snippets[0]
    score = float(top_snippet.get("score", 0.0))
    if score < 0.45:
        return False

    requirement_tokens = _tokenize(str(obligation.get("requirement", "")))
    quote_tokens = _tokenize(str(obligation.get("clause_quote", "")))
    snippet_tokens = _tokenize(str(top_snippet.get("quote", "")))

    important_tokens = {token for token in requirement_tokens | quote_tokens if len(token) > 3}
    overlap = important_tokens & snippet_tokens
    return len(overlap) >= max(2, min(3, len(important_tokens)))


def decide_coverage_batch(
    clause_id: str,
    obligations: list[dict[str, object]],
    snippets_by_obligation: dict[str, list[dict[str, object]]],
    client: LLMClient | None = None,
) -> list[dict[str, object]]:
    if client is not None:
        prompt_lines = []
        for obligation in obligations:
            obligation_id = str(obligation.get("obligation_id", "O1"))
            snippets = snippets_by_obligation.get(obligation_id, [])
            prompt_lines.append(
                f"{obligation_id}) obligation_id: {obligation_id}, requirement: {obligation.get('requirement', '')}, clause_quote: {obligation.get('clause_quote', '')}"
            )
            for index, snippet in enumerate(snippets[:3], start=1):
                prompt_lines.append(f"   excerpt {index}: {snippet.get('quote', '')}")
        prompt = build_coverage_prompt(clause_id, "\n".join(prompt_lines))
        response = asyncio.run(client.call_json(prompt, fixture_name="coverage.json"))
        if response.get("_error") == "LLMParseError":
            first_obligation = obligations[0]["obligation_id"] if obligations else None
            return [maybe_flag_parse_error(str(response.get("raw", "")), clause_id, str(first_obligation) if first_obligation else None)]

        results: list[dict[str, object]] = []
        for item in response.get("results", []):
            obligation_id = str(item.get("obligation_id", "O1"))
            snippets = snippets_by_obligation.get(obligation_id, [])
            original_quote = item.get("proposal_quote", "Not found")
            proposal_quote = original_quote
            source_text = str(snippets[0].get("quote", "")) if snippets else ""
            if proposal_quote != "Not found" and not verify_quote(str(proposal_quote), source_text):
                proposal_quote = "Not found"
            results.append(
                {
                    "clause_id_normalized": clause_id,
                    "obligation_id": obligation_id,
                    "status": str(item.get("status", "Unclear")),
                    "proposal_quote": proposal_quote,
                    "raw_proposal_quote": original_quote,
                    "proposal_location": str(item.get("proposal_location", "Not found")),
                    "rationale": str(item.get("rationale", "")),
                    "confidence": min(float(item.get("confidence", 0.3)), 0.3) if proposal_quote == "Not found" and original_quote != "Not found" else float(item.get("confidence", 0.3)),
                }
            )
        return results

    results: list[dict[str, object]] = []
    for obligation in obligations:
        obligation_id = str(obligation.get("obligation_id", "O1"))
        snippets = snippets_by_obligation.get(obligation_id, [])
        proposal_quote = snippets[0]["quote"] if snippets else "Not found"
        strong_evidence = _evidence_is_strong(obligation, snippets)
        if proposal_quote != "Not found" and not strong_evidence:
            proposal_quote = "Not found"
        results.append(
            {
                "clause_id_normalized": clause_id,
                "obligation_id": obligation_id,
                "status": "Covered" if strong_evidence else "Unclear",
                "proposal_quote": proposal_quote,
                "raw_proposal_quote": snippets[0]["quote"] if snippets else "Not found",
                "proposal_location": f"{snippets[0]['doc_id']}:{snippets[0]['start_char']}-{snippets[0]['end_char']}" if snippets else "Not found",
                "rationale": "Heuristic coverage result generated from retrieved snippets.",
                "confidence": 0.8 if strong_evidence else 0.3,
            }
        )
    return results
