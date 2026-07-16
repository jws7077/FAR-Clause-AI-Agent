from __future__ import annotations

import argparse
import json
from pathlib import Path

from .audit_clauses_llm import llm_extract_clause_ids
from .config import load_config
from .conflicts import detect_conflicts
from .coverage_llm import decide_coverage_batch
from .corpus import lookup_clause_text
from .extract_clauses import extract_clause_mentions
from .ingest import chunk_text, load_docx, load_pdf, normalize_text
from .llm_client import LLMClient
from .obligations_llm import extract_obligations
from .render import render_markdown
from .scoring import assign_severity
from .search import search_snippets


def _load_document(path: Path) -> dict[str, object]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        text = load_docx(path)
    elif suffix == ".pdf":
        text = load_pdf(path)
    else:
        text = normalize_text(path.read_text(encoding="utf-8"))
    return {
        "doc_id": path.stem,
        "role": "solicitation" if "solic" in path.name.lower() else "proposal",
        "name": path.name,
        "text": text,
        "chunks": chunk_text(text),
    }


def _build_report(
    solicitation_docs: list[dict[str, object]],
    proposal_docs: list[dict[str, object]],
    config,
    client: LLMClient | None = None,
) -> dict[str, object]:
    solicitation_text = "\n".join(str(doc["text"]) for doc in solicitation_docs)

    rfp_clause_index = llm_extract_clause_ids([{"text": solicitation_text}], client=client)
    if not rfp_clause_index:
        rfp_clause_index = extract_clause_mentions(solicitation_text)

    canonical_clause_texts = []
    obligations = []
    coverage_results = []
    flags = []

    for mention in rfp_clause_index:
        clause_id = str(mention.get("clause_id_normalized", ""))
        canonical = lookup_clause_text(clause_id, date_guess=mention.get("date_guess"), corpus_root=config.corpus_root)
        canonical_clause_texts.append(canonical)
        if canonical.get("status") == "MISSING":
            flags.append(
                {
                    "type": "CanonicalMissing",
                    "clause_id_normalized": clause_id,
                    "obligation_id": None,
                    "severity": "High",
                    "citation": canonical["canonical_citation"],
                    "summary": f"No canonical text found for {clause_id}.",
                    "confidence": 1.0,
                }
            )
            continue
        if canonical.get("date_mismatch"):
            flags.append(
                {
                    "type": "DateMismatch",
                    "clause_id_normalized": clause_id,
                    "obligation_id": None,
                    "severity": "Medium",
                    "citation": canonical["canonical_citation"],
                    "summary": f"Requested date {mention.get('date_guess')} did not match corpus date {canonical.get('canonical_date')} for {clause_id}.",
                    "confidence": 0.5,
                }
            )
        clause_obligations = extract_obligations(clause_id, str(canonical["canonical_text"]), mention, client=client)
        obligations.extend(clause_obligations)
        for obligation in clause_obligations:
            if obligation.get("clause_quote") is None and obligation.get("raw_clause_quote"):
                flags.append(
                    {
                        "type": "UnverifiedQuote",
                        "clause_id_normalized": clause_id,
                        "obligation_id": obligation["obligation_id"],
                        "severity": "Medium",
                        "citation": {"doc_id": "", "start_char": 0, "end_char": 0, "quote": ""},
                        "summary": str(obligation.get("raw_clause_quote", ""))[:500],
                        "confidence": 0.3,
                    }
                )
        snippets_by_obligation = {}
        for obligation in clause_obligations:
            snippets_by_obligation[str(obligation["obligation_id"])] = search_snippets(proposal_docs, list(obligation.get("search_queries", [])), top_k=config.search_top_k)
        clause_results = decide_coverage_batch(clause_id, clause_obligations, snippets_by_obligation, client=client)
        for result in clause_results:
            obligation = next((item for item in clause_obligations if item["obligation_id"] == result["obligation_id"]), None)
            severity = assign_severity(obligation, result["status"], canonical_missing=False, date_mismatch=bool(canonical.get("date_mismatch")))
            result["severity"] = severity
            if result.get("proposal_quote") == "Not found" and result.get("raw_proposal_quote") not in (None, "Not found"):
                flags.append(
                    {
                        "type": "UnverifiedQuote",
                        "clause_id_normalized": clause_id,
                        "obligation_id": result["obligation_id"],
                        "severity": "Medium",
                        "citation": {"doc_id": "", "start_char": 0, "end_char": 0, "quote": ""},
                        "summary": str(result.get("raw_proposal_quote", ""))[:500],
                        "confidence": 0.3,
                    }
                )
            coverage_results.append(result)

        for obligation in clause_obligations:
            snippets = snippets_by_obligation.get(str(obligation["obligation_id"]), [])
            conflict = detect_conflicts(obligation, snippets, client=client)
            if conflict.get("conflict"):
                flags.append(
                    {
                        "type": "PotentialConflict",
                        "clause_id_normalized": clause_id,
                        "obligation_id": obligation["obligation_id"],
                        "severity": "Disqualifier" if float(conflict.get("confidence", 0.0)) >= 0.7 else "Medium",
                        "citation": snippets[0] if snippets else {"doc_id": "", "start_char": 0, "end_char": 0, "quote": ""},
                        "summary": str(conflict.get("rationale", "Potential conflict detected.")),
                        "confidence": float(conflict.get("confidence", 0.0)),
                    }
                )

    report = {
        "schema_version": "1.0",
        "documents": solicitation_docs + proposal_docs,
        "rfp_clause_index": rfp_clause_index,
        "canonical_clause_texts": canonical_clause_texts,
        "obligations": obligations,
        "coverage_results": coverage_results,
        "flags": flags,
    }
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="far-clause-ai-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--solicitation", nargs="+", required=True)
    run_parser.add_argument("--proposal", nargs="+", required=True)
    run_parser.add_argument("--out", required=True)
    run_parser.add_argument("--mock-llm", action="store_true")

    args = parser.parse_args(argv)
    if args.command != "run":
        parser.error("Unsupported command")

    config = load_config()
    config = type(config)(**{**config.__dict__, "mock_llm": config.mock_llm or bool(args.mock_llm)})
    client = LLMClient(config)

    solicitation_docs = [_load_document(Path(path)) for path in args.solicitation]
    proposal_docs = [_load_document(Path(path)) for path in args.proposal]
    report = _build_report(solicitation_docs, proposal_docs, config, client=client)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"LLM calls: {client.call_count}")
    print(f"Report written to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
