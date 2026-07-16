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
