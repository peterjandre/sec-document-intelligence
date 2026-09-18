from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rag.pipeline import (
    ANSWER_SYSTEM_INSTRUCTION,
    GENERATION_UNAVAILABLE_ANSWER,
    NO_EVIDENCE_ANSWER,
    _document_meta,
    build_answer_prompt,
    complete_answer,
    format_numbered_excerpts,
    retrieve_answer,
)


class FakeRpc:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def execute(self) -> SimpleNamespace:
        return SimpleNamespace(data=self._rows)


class FakeSupabase:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows
        self.last_rpc: tuple[str, dict] | None = None

    def rpc(self, name: str, params: dict) -> FakeRpc:
        self.last_rpc = (name, params)
        return FakeRpc(self.rows)


def _chunk(
    document_id: str = "aapl-20250927",
    section: str = "Risk Factors",
    text: str = "The Company relies on a limited number of suppliers.",
    similarity: float = 0.72,
) -> dict:
    return {
        "document_id": document_id,
        "section": section,
        "text": text,
        "similarity": similarity,
    }


class NumberedExcerptTests(unittest.TestCase):
    def test_numbers_document_and_section(self) -> None:
        formatted = format_numbered_excerpts(
            [
                {
                    "document_id": "aapl-20250927",
                    "section": "Risk Factors",
                    "text": "Supply chain concentration is a material risk.",
                },
                {
                    "document_id": "amzn-20251231",
                    "section": "Business",
                    "excerpt": "We fulfill customer orders through our networks.",
                },
            ]
        )
        self.assertIn("[1] aapl-20250927 / Risk Factors", formatted)
        self.assertIn("Supply chain concentration is a material risk.", formatted)
        self.assertIn("[2] amzn-20251231 / Business", formatted)
        self.assertIn("We fulfill customer orders through our networks.", formatted)

    def test_user_prompt_includes_question_and_excerpts(self) -> None:
        prompt = build_answer_prompt(
            "How does Apple describe supplier risk?",
            [
                {
                    "document_id": "aapl-20250927",
                    "section": "Risk Factors",
                    "text": "The Company relies on a limited number of suppliers.",
                }
            ],
        )
        self.assertIn("Question:\nHow does Apple describe supplier risk?", prompt)
        self.assertIn("Excerpts:\n[1] aapl-20250927 / Risk Factors", prompt)

    def test_system_instruction_has_10k_guardrails(self) -> None:
        lowered = ANSWER_SYSTEM_INSTRUCTION.lower()
        self.assertIn("only the numbered excerpts", lowered)
        self.assertIn("[n]", ANSWER_SYSTEM_INSTRUCTION)
        self.assertIn("do not support", lowered)
        self.assertIn("never invent numbers", lowered)
        self.assertIn("quoting figures", lowered)
        self.assertIn("never mix companies", lowered)


class CompleteAnswerTests(unittest.TestCase):
    def test_missing_key_does_not_guess(self) -> None:
        with patch.dict("os.environ", {"OPENAI_API_KEY": ""}, clear=False):
            answer = complete_answer("What are Apple's risks?", [_chunk()])
        self.assertIn("OPENAI_API_KEY", answer)
        self.assertNotIn("synthesized response", answer.lower())

    def test_uses_model_text_not_invented_sources(self) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="Apple relies on a limited number of suppliers [1]."
                    )
                )
            ]
        )
        evidence = [_chunk()]
        with patch("rag.pipeline._openai_client", return_value=mock_client):
            answer = complete_answer("How does Apple describe supplier risk?", evidence)
        self.assertEqual(answer, "Apple relies on a limited number of suppliers [1].")
        kwargs = mock_client.chat.completions.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-4.1-nano")
        self.assertEqual(kwargs["messages"][0]["content"], ANSWER_SYSTEM_INSTRUCTION)
        self.assertIn("[1] aapl-20250927 / Risk Factors", kwargs["messages"][1]["content"])

    def test_503_unavailable_becomes_standard_message(self) -> None:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception(
            "503 UNAVAILABLE. {'error': {'code': 503, 'message': "
            "'This model is currently experiencing high demand.', "
            "'status': 'UNAVAILABLE'}}"
        )
        with patch("rag.pipeline._openai_client", return_value=mock_client):
            answer = complete_answer("How does Apple describe supplier risk?", [_chunk()])
        self.assertEqual(answer, GENERATION_UNAVAILABLE_ANSWER)
        self.assertNotIn("503", answer)
        self.assertNotIn("high demand", answer)

    def test_503_status_code_attribute_is_mapped(self) -> None:
        class BusyError(Exception):
            status_code = 503

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = BusyError("unavailable")
        with patch("rag.pipeline._openai_client", return_value=mock_client):
            answer = complete_answer("How does Apple describe supplier risk?", [_chunk()])
        self.assertEqual(answer, GENERATION_UNAVAILABLE_ANSWER)


class RetrieveAnswerLlmTests(unittest.TestCase):
    @patch("rag.pipeline._embedding_for_text", return_value=[0.1] * 8)
    @patch("rag.pipeline.complete_answer")
    @patch("rag.pipeline._supabase_client")
    def test_skips_llm_when_no_rows(
        self,
        mock_supabase: MagicMock,
        mock_complete: MagicMock,
        _mock_embed: MagicMock,
    ) -> None:
        mock_supabase.return_value = FakeSupabase([])
        result = retrieve_answer("How does Apple describe manufacturing risks?")
        mock_complete.assert_not_called()
        self.assertEqual(result["answer"], NO_EVIDENCE_ANSWER)
        self.assertEqual(result["citations"][0]["document_id"], "unavailable")

    @patch("rag.pipeline._embedding_for_text", return_value=[0.1] * 8)
    @patch("rag.pipeline.complete_answer")
    @patch("rag.pipeline._supabase_client")
    def test_skips_llm_when_all_below_threshold(
        self,
        mock_supabase: MagicMock,
        mock_complete: MagicMock,
        _mock_embed: MagicMock,
    ) -> None:
        mock_supabase.return_value = FakeSupabase([_chunk(similarity=0.2)])
        result = retrieve_answer(
            "How does Apple describe manufacturing risks?",
            min_similarity=0.5,
        )
        mock_complete.assert_not_called()
        self.assertEqual(result["answer"], NO_EVIDENCE_ANSWER)

    @patch("rag.pipeline._embedding_for_text", return_value=[0.1] * 8)
    @patch("rag.pipeline.complete_answer", return_value="Grounded answer [1].")
    @patch("rag.pipeline._supabase_client")
    def test_calls_llm_and_keeps_retrieved_citations(
        self,
        mock_supabase: MagicMock,
        mock_complete: MagicMock,
        _mock_embed: MagicMock,
    ) -> None:
        row = _chunk()
        mock_supabase.return_value = FakeSupabase([row])
        result = retrieve_answer("How does Apple describe supplier risk?")
        mock_complete.assert_called_once()
        question, evidence = mock_complete.call_args.args
        self.assertEqual(question, "How does Apple describe supplier risk?")
        self.assertEqual(evidence[0]["document_id"], "aapl-20250927")
        self.assertEqual(evidence[0]["text"], row["text"])
        self.assertEqual(result["answer"], "Grounded answer [1].")
        self.assertEqual(result["citations"][0]["document_id"], "aapl-20250927")
        self.assertEqual(result["citations"][0]["section"], "Risk Factors")
        self.assertTrue(row["text"].startswith(result["citations"][0]["excerpt"]))

    @patch("rag.pipeline._embedding_for_text", return_value=[0.1] * 8)
    @patch("rag.pipeline.complete_answer", return_value="Grounded answer [1].")
    @patch("rag.pipeline._supabase_client")
    def test_year_filter_maps_january_nvidia_to_prior_year(
        self,
        mock_supabase: MagicMock,
        mock_complete: MagicMock,
        _mock_embed: MagicMock,
    ) -> None:
        supabase = FakeSupabase(
            [
                _chunk("nvda-20260125", similarity=0.81),
                _chunk("nvda-20250126", similarity=0.80),
            ]
        )
        mock_supabase.return_value = supabase
        result = retrieve_answer(
            "What does NVIDIA disclose about export controls?",
            filing_year=2025,
        )
        self.assertEqual(
            [citation["document_id"] for citation in result["citations"]],
            ["nvda-20260125"],
        )
        self.assertEqual(supabase.last_rpc[1]["filter"]["filing_years"], [2025, 2026])


class DocumentMetaTests(unittest.TestCase):
    def test_january_fiscal_year_end_maps_to_prior_calendar_year(self) -> None:
        self.assertEqual(_document_meta("nvda-20260125", {}), ("NVDA", 2025))
        self.assertEqual(_document_meta("nvda-20250126", {}), ("NVDA", 2024))

    def test_non_january_year_is_unchanged(self) -> None:
        self.assertEqual(_document_meta("aapl-20250927", {}), ("AAPL", 2025))
        self.assertEqual(_document_meta("aapl-20240928", {}), ("AAPL", 2024))
        self.assertEqual(_document_meta("amzn-20251231", {}), ("AMZN", 2025))


if __name__ == "__main__":
    unittest.main()
