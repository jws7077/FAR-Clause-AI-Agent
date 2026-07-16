from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from far_clause_ai_agent.main import main
from far_clause_ai_agent.corpus import lookup_clause_text
from far_clause_ai_agent.coverage_llm import decide_coverage_batch


class CoverageGatingTests(unittest.TestCase):
    def test_strong_evidence_can_be_covered(self) -> None:
        obligation = {
            "obligation_id": "O1",
            "requirement": "Provide required reporting.",
            "clause_quote": "shall provide required reporting",
        }
        snippets_by_obligation = {
            "O1": [
                {
                    "quote": "We provide required reporting",
                    "doc_id": "proposal",
                    "start_char": 0,
                    "end_char": 29,
                    "score": 0.92,
                }
            ]
        }
        result = decide_coverage_batch("52.212-4", [obligation], snippets_by_obligation)[0]
        self.assertEqual(result["status"], "Covered")
        self.assertEqual(result["proposal_quote"], "We provide required reporting")

    def test_weak_evidence_stays_unclear(self) -> None:
        obligation = {
            "obligation_id": "O1",
            "requirement": "Provide required reporting.",
            "clause_quote": "shall provide required reporting",
        }
        snippets_by_obligation = {
            "O1": [
                {
                    "quote": "We will assist as needed",
                    "doc_id": "proposal",
                    "start_char": 0,
                    "end_char": 24,
                    "score": 0.12,
                }
            ]
        }
        result = decide_coverage_batch("52.212-4", [obligation], snippets_by_obligation)[0]
        self.assertEqual(result["status"], "Unclear")
        self.assertEqual(result["proposal_quote"], "Not found")


class CorpusLookupTests(unittest.TestCase):
    def test_date_mismatch_is_flagged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "52.212-4__2024-01-01.txt").write_text("sample corpus text", encoding="utf-8")
            result = lookup_clause_text("52.212-4", date_guess="2023-01-01", corpus_root=root)
            self.assertEqual(result["canonical_date"], "2024-01-01")
            self.assertTrue(result["date_mismatch"])
            self.assertTrue(result["canonical_citation"]["doc_id"].endswith("52.212-4__2024-01-01.txt"))


class CliIntegrationTests(unittest.TestCase):
    def test_mock_run_writes_reports(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        solicitation = fixtures / "sample_solicitation.txt"
        proposal = fixtures / "sample_proposal.txt"

        with TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            exit_code = main(
                [
                    "run",
                    "--solicitation",
                    str(solicitation),
                    "--proposal",
                    str(proposal),
                    "--out",
                    str(out_dir),
                    "--mock-llm",
                ]
            )

            self.assertEqual(exit_code, 0)
            report_json_path = out_dir / "report.json"
            report_md_path = out_dir / "report.md"
            self.assertTrue(report_json_path.exists())
            self.assertTrue(report_md_path.exists())

            report = json.loads(report_json_path.read_text(encoding="utf-8"))
            self.assertIn("coverage_results", report)
            self.assertTrue(report["coverage_results"])
            self.assertTrue(any(item["status"] == "Covered" for item in report["coverage_results"]))
            self.assertTrue(any(flag["type"] == "CanonicalMissing" for flag in report["flags"]))


if __name__ == "__main__":
    unittest.main()