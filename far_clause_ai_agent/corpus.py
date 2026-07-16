from __future__ import annotations

import re
from pathlib import Path

from .extract_clauses import classify_clause


DATE_SUFFIX_PATTERN = re.compile(r"(\d{4}-\d{2}-\d{2})$")


def _extract_date_from_path(path: Path) -> str | None:
    match = DATE_SUFFIX_PATTERN.search(path.stem)
    return match.group(1) if match else None


def lookup_clause_text(clause_id: str, date_guess: str | None = None, corpus_root: str | Path = "data/corpus") -> dict[str, object]:
    corpus_root = Path(corpus_root)
    family = classify_clause(clause_id)
    family_dir = {
        "FAR": "FAR",
        "DFARS": "DFARS",
        "AGENCY": "AGENCY",
    }.get(family)
    candidate_paths = [
        corpus_root / family_dir / clause_id / "latest.txt" if family_dir else None,
        corpus_root / family_dir / clause_id / f"{date_guess}.txt" if family_dir and date_guess else None,
        corpus_root / f"{clause_id}.txt",
        corpus_root / clause_id / "latest.txt",
    ]
    candidate_paths = [path for path in candidate_paths if path is not None]
    if family_dir:
        clause_dir = corpus_root / family_dir / clause_id
        if clause_dir.exists():
            candidate_paths.extend(sorted(clause_dir.glob("*.txt")))
    candidate_paths.extend(sorted(corpus_root.glob(f"{clause_id}__*.txt")))
    clause_dir = corpus_root / clause_id
    if clause_dir.exists():
        candidate_paths.extend(sorted(clause_dir.glob("*.txt")))

    selected_path: Path | None = None
    if date_guess:
        for path in candidate_paths:
            if path.exists() and _extract_date_from_path(path) == date_guess:
                selected_path = path
                break
        if selected_path is None:
            dated_paths = [path for path in candidate_paths if path.exists() and _extract_date_from_path(path)]
            if dated_paths:
                selected_path = sorted(dated_paths, key=lambda path: _extract_date_from_path(path) or "")[-1]

    if selected_path is None:
        selected_path = next((path for path in candidate_paths if path.exists()), None)

    if selected_path is not None:
        text = selected_path.read_text(encoding="utf-8")
        canonical_date = _extract_date_from_path(selected_path) or date_guess
        if canonical_date is None:
            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", selected_path.stem)
            canonical_date = date_match.group(1) if date_match else date_guess
        date_mismatch = bool(date_guess and canonical_date and canonical_date != date_guess)
        if date_guess and canonical_date is None:
            date_mismatch = True
        return {
            "clause_id_normalized": clause_id,
            "family": family,
            "canonical_date": canonical_date,
            "canonical_text": text,
            "canonical_source": "FAR_CORPUS",
            "canonical_citation": {"doc_id": str(selected_path), "start_char": 0, "end_char": len(text), "quote": text[:500]},
            "status": "FOUND",
            "date_mismatch": date_mismatch,
        }

    for path in candidate_paths:
        if path.exists():
            text = path.read_text(encoding="utf-8")
            return {
                "clause_id_normalized": clause_id,
                "family": family,
                "canonical_date": date_guess,
                "canonical_text": text,
                "canonical_source": "FAR_CORPUS",
                "canonical_citation": {"doc_id": str(path), "start_char": 0, "end_char": len(text), "quote": text[:500]},
                "status": "FOUND",
                "date_mismatch": False,
            }

    return {
        "clause_id_normalized": clause_id,
        "family": family,
        "canonical_date": date_guess,
        "canonical_text": None,
        "canonical_source": None,
        "canonical_citation": {"doc_id": "", "start_char": 0, "end_char": 0, "quote": ""},
        "status": "MISSING",
        "date_mismatch": False,
    }
