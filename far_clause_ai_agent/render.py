from __future__ import annotations

SEVERITY_ORDER = {
    "Disqualifier": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
}


def _recommended_fix(status: str, severity: str) -> str:
    if severity == "Disqualifier":
        return "Revise the proposal to address the mandatory requirement directly."
    if status == "NotCovered":
        return "Add explicit proposal language that satisfies the clause requirement."
    if status == "Unclear":
        return "Clarify the commitment so the reviewer can trace it to the clause text."
    return "No immediate fix required."


def render_markdown(report_json: dict[str, object]) -> str:
    lines = ["# Compliance Review", ""]

    coverage = list(report_json.get("coverage_results", []))
    clauses = {str(item.get("clause_id_normalized")): item for item in report_json.get("rfp_clause_index", [])}
    canonical = {str(item.get("clause_id_normalized")): item for item in report_json.get("canonical_clause_texts", [])}
    obligations = {(str(item.get("clause_id_normalized")), str(item.get("obligation_id"))): item for item in report_json.get("obligations", [])}

    lines.append("## Findings")
    if not coverage:
        lines.append("No findings were generated.")
    else:
        for result in sorted(
            coverage,
            key=lambda item: (
                SEVERITY_ORDER.get(str(item.get("severity", "Low")), 99),
                str(item.get("clause_id_normalized", "")),
                str(item.get("obligation_id", "")),
            ),
        ):
            clause_id = str(result.get("clause_id_normalized", ""))
            obligation_id = str(result.get("obligation_id", ""))
            obligation = obligations.get((clause_id, obligation_id), {})
            mention = clauses.get(clause_id, {})
            canonical_item = canonical.get(clause_id, {})
            lines.extend(
                [
                    f"### {clause_id} / {obligation_id}",
                    f"Severity: {result.get('severity')} | Status: {result.get('status')} | Family: {mention.get('family', 'UNKNOWN')}",
                    f"Solicitation citation: {mention.get('citations', [{}])[0].get('quote', clause_id)}",
                    f"Canonical source: {canonical_item.get('canonical_source', 'UNKNOWN')}",
                    f"Obligation: {obligation.get('requirement', '')}",
                    f"Clause quote: {obligation.get('clause_quote') or obligation.get('raw_clause_quote', 'Not found')}",
                    f"Proposal quote: {result.get('proposal_quote', 'Not found')}",
                    f"Proposal citation: {result.get('proposal_location', 'Not found')}",
                    f"Recommended fix: {_recommended_fix(str(result.get('status', 'Unclear')), str(result.get('severity', 'Low')))}",
                    "",
                ]
            )

    flags = list(report_json.get("flags", []))
    lines.append("## Flags")
    if not flags:
        lines.append("No flags were generated.")
    else:
        for flag in flags:
            lines.append(
                f"- {flag.get('severity')} | {flag.get('type')} | {flag.get('clause_id_normalized', '')} | {flag.get('summary', '')}"
            )

    return "\n".join(lines).rstrip() + "\n"
