from __future__ import annotations

import re


MANDATORY_PATTERN = re.compile(r"\b(shall|must|will|required)\b", re.IGNORECASE)


def is_mandatory(clause_quote_or_sentence: str) -> bool:
    return bool(MANDATORY_PATTERN.search(clause_quote_or_sentence or ""))


def assign_severity(
    obligation: dict[str, object] | None,
    status: str,
    conflict: dict[str, object] | None = None,
    canonical_missing: bool = False,
    date_mismatch: bool = False,
) -> str:
    if canonical_missing:
        return "High"
    if conflict and float(conflict.get("confidence", 0.0)) >= 0.7:
        return "Disqualifier"
    quote = ""
    if obligation:
        quote = str(obligation.get("clause_quote") or obligation.get("requirement") or "")
    mandatory = is_mandatory(quote)
    if status == "NotCovered":
        return "Disqualifier" if mandatory else "Medium"
    if status == "Unclear":
        return "High" if mandatory else "Medium"
    if date_mismatch:
        return "Medium"
    return "Low"
