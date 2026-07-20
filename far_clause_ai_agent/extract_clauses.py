from __future__ import annotations

import re
from typing import Iterable


CLAUSE_PATTERN = re.compile(
    r"\b(?:(FAR|DFARS|GSAM|HHSAR|VAAR|agency|agency supplement)\s+)?(?P<id>(?:\d{1,4}\.)?\d{1,3}(?:-\d{1,4})?(?:\([a-z0-9]+\))*)(?=\s|$|[.,;:])",
    re.IGNORECASE,
)


def normalize_clause_id(raw: str) -> str:
    cleaned = raw.upper().strip()
    cleaned = cleaned.replace("FAR ", "").replace("DFARS ", "")
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned


def classify_clause(clause_id: str) -> str:
    clause_id = normalize_clause_id(clause_id)
    if clause_id.startswith("252."):
        return "DFARS"
    if clause_id.startswith("48.") or clause_id.startswith("52."):
        return "FAR"
    if clause_id.startswith(("30", "31", "32", "33", "34", "36", "37", "38", "40", "45", "70", "75", "90")):
        return "AGENCY"
    return "UNKNOWN"


def parse_metadata_from_context(text: str) -> dict[str, str | None]:
    date_match = re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4}\b|\b\d{4}-\d{2}-\d{2}\b",
        text,
        re.IGNORECASE,
    )
    title_match = re.search(r"\b(?:Clause|Provision|Section)\s+([A-Za-z0-9 ,./-]{3,80})", text)
    alternate_match = re.search(r"\bAlternate\s+[A-Z0-9]+\b", text, re.IGNORECASE)
    return {
        "title_guess": title_match.group(1).strip() if title_match else None,
        "date_guess": date_match.group(0) if date_match else None,
        "alternate_guess": alternate_match.group(0) if alternate_match else None,
    }


def extract_clause_mentions(text: str) -> list[dict[str, object]]:
    mentions: list[dict[str, object]] = []
    for match in CLAUSE_PATTERN.finditer(text):
        clause_id = normalize_clause_id(match.group("id"))

        if classify_clause(clause_id) == "UNKNOWN":
            continue

        citation = {
            "start_char": match.start(),
            "end_char": match.end(),
            "quote": text[match.start():match.end()],
        }
        metadata = parse_metadata_from_context(text[max(0, match.start() - 200): match.end() + 200])
        title_guess = metadata["title_guess"]
        if not title_guess and match.end() < len(text):
            trailing_text = text[match.end(): match.end() + 80]
            title_match = re.match(r"[\s:\-–—]*([A-Za-z0-9 ,./()&'\-]{3,80})", trailing_text)
            if title_match:
                title_guess = title_match.group(1).strip()
        mentions.append(
            {
                "clause_ref_raw": match.group(0),
                "clause_id_normalized": clause_id,
                "family": classify_clause(clause_id),
                "title_guess": title_guess,
                "date_guess": metadata["date_guess"],
                "alternate_guess": metadata["alternate_guess"],
                "citation": citation,
            }
        )
    return merge_dedupe_mentions(mentions)


def merge_dedupe_mentions(mentions: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    merged: dict[tuple[str, int, int], dict[str, object]] = {}
    for mention in mentions:
        citation = mention.get("citation") or {}
        key = (
            str(mention.get("clause_id_normalized", "")),
            int(citation.get("start_char", 0)),
            int(citation.get("end_char", 0)),
        )
        if key not in merged:
            merged[key] = {
                "clause_ref_raw": mention.get("clause_ref_raw"),
                "clause_id_normalized": mention.get("clause_id_normalized"),
                "family": mention.get("family", "UNKNOWN"),
                "title_guess": mention.get("title_guess"),
                "date_guess": mention.get("date_guess"),
                "alternate_guess": mention.get("alternate_guess"),
                "citations": [citation],
            }
        else:
            merged[key]["citations"].append(citation)
    return list(merged.values())
