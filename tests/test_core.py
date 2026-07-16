from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from far_clause_ai_agent.main import main
from far_clause_ai_agent.extract_clauses import extract_clause_mentions
from far_clause_ai_agent.search import search_snippets_with_context
from far_clause_ai_agent.corpus import lookup_clause_text
from far_clause_ai_agent.coverage_llm import decide_coverage_batch
from far_clause_ai_agent.coverage_llm import _normalize_result_item


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

    def test_malformed_llm_result_is_safely_normalized(self) -> None:
        snippets = [
            {
                "quote": "We provide required reporting",
                "doc_id": "proposal",
                "start_char": 0,
                "end_char": 29,
                "score": 0.92,
            }
        ]
        normalized = _normalize_result_item(
            {
                "obligation_id": 7,
                "status": True,
                "proposal_quote": 123,
                "proposal_location": 456,
                "rationale": 789,
                "confidence": "bad",
            },
            snippets,
        )
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["obligation_id"], "7")
        self.assertEqual(normalized["status"], "Unclear")
        self.assertEqual(normalized["proposal_quote"], "Not found")
        self.assertEqual(normalized["proposal_location"], "Not found")
        self.assertEqual(normalized["confidence"], 0.3)


class CorpusLookupTests(unittest.TestCase):
    def test_date_mismatch_is_flagged(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            family_dir = root / "FAR" / "52.212-4"
            family_dir.mkdir(parents=True)
            (family_dir / "2024-01-01.txt").write_text("sample corpus text", encoding="utf-8")
            result = lookup_clause_text("52.212-4", date_guess="2023-01-01", corpus_root=root)
            self.assertEqual(result["canonical_date"], "2024-01-01")
            self.assertTrue(result["date_mismatch"])
            self.assertTrue(result["canonical_citation"]["doc_id"].endswith("2024-01-01.txt"))

    def test_family_latest_lookup(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            family_dir = root / "DFARS" / "252.204-7012"
            family_dir.mkdir(parents=True)
            (family_dir / "latest.txt").write_text("dfars clause text", encoding="utf-8")
            result = lookup_clause_text("252.204-7012", corpus_root=root)
            self.assertEqual(result["status"], "FOUND")
            self.assertEqual(result["canonical_text"], "dfars clause text")
            self.assertTrue(result["canonical_citation"]["doc_id"].endswith("latest.txt"))


class ExtractionTests(unittest.TestCase):
    def test_nested_clause_reference_and_numeric_date(self) -> None:
        text = "The offeror must comply with FAR 52.212-4(c)(1) dated 2024-01-01 and related instructions."
        mentions = extract_clause_mentions(text)
        self.assertTrue(any(item["clause_id_normalized"] == "52.212-4(C)(1)" for item in mentions))
        self.assertTrue(any(item["date_guess"] == "2024-01-01" for item in mentions))


class RetrievalTests(unittest.TestCase):
    def test_context_window_extends_past_500_chars(self) -> None:
        long_prefix = "A" * 550
        proposal_docs = [
            {
                "doc_id": "proposal",
                "text": long_prefix + " We provide required reporting in detail.",
                "chunks": [
                    {
                        "chunk_id": "C1",
                        "start_char": 0,
                        "end_char": len(long_prefix) + 41,
                        "text": long_prefix + " We provide required reporting in detail.",
                    }
                ],
            }
        ]
        snippets = search_snippets_with_context(proposal_docs, ["required reporting"], top_k=1, context_window=200)
        self.assertTrue(snippets)
        self.assertIn("required reporting", snippets[0]["quote"])
        self.assertGreater(len(snippets[0]["quote"]), 500)


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
            self.assertIsInstance(report["flags"], list)

    def test_cli_module_entrypoint_smoke(self) -> None:
        fixtures = Path(__file__).parent / "fixtures"
        solicitation = fixtures / "sample_solicitation.txt"
        proposal = fixtures / "sample_proposal.txt"

        with TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "far_clause_ai_agent",
                    "run",
                    "--solicitation",
                    str(solicitation),
                    "--proposal",
                    str(proposal),
                    "--out",
                    str(out_dir),
                    "--mock-llm",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("Report written to", completed.stdout)
            self.assertTrue((out_dir / "report.json").exists())
            self.assertTrue((out_dir / "report.md").exists())


if __name__ == "__main__":
    unittest.main()