# FAR-Clause-AI-Agent
AI agent that reviews input documents for federal RFP/solicitation compliance and produces a reviewer-oriented report.

## Current Scaffold

The starter implementation now includes:

- `far_clause_ai_agent.main` CLI entrypoint
- document ingestion helpers for `.txt`, `.docx`, and `.pdf`
- clause extraction, scoring, search, rendering, and shared LLM-client modules
- `report.json` and `report.md` output generation

## Run

```bash
python -m far_clause_ai_agent run --solicitation path/to/solicitation.docx --proposal path/to/proposal.docx --out out/
```

Use `--mock-llm` or `MOCK_LLM=1` for fixture-driven runs.

## Corpus Layout

Clause texts live under `data/corpus/` using family and clause id folders:

```text
data/corpus/
	FAR/52.212-4/latest.txt
	FAR/52.212-4/2024-01-01.txt
	DFARS/252.204-7012/latest.txt
	AGENCY/HHSAR-352.222-70/latest.txt
```

Use `latest.txt` for the default canonical text and add dated files when the solicitation references a specific effective date.
