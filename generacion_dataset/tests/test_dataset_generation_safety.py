from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from generate_colloquial_legal_questions import (  # noqa: E402
    build_negative_candidate_pool,
    build_temporal_context,
    build_index_text,
    build_bm25,
    build_training_records,
    build_user_prompt,
    validate_hard_negative_candidate_ids,
)
from legal_candidate_resolver import ResolutionResult  # noqa: E402


def chunk(
    chunk_id: str,
    text: str,
    *,
    source_type: str = "tipo_04_jurisprudencia",
    doc_id: str | None = None,
    resolution_reference: str | None = None,
    article_id: str | None = None,
) -> dict:
    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id or chunk_id.removeprefix("chunk_"),
        "source_type": source_type,
        "title": chunk_id,
        "text": text,
        "metadata": {
            "resolution_reference": resolution_reference,
            "article_id": article_id,
        },
    }


class DatasetGenerationSafetyTest(unittest.TestCase):
    def test_negative_pool_excludes_related_text_and_resolution_duplicates(self) -> None:
        positive = chunk(
            "chunk_case",
            "La parte civil solicita reparación.",
            resolution_reference="RN 10-2020",
        )
        article = chunk(
            "chunk_cpp_104",
            "El actor civil puede ofrecer medios de investigación.",
            source_type="tipo_03_codigo_procesal_penal",
            article_id="104",
        )
        same_text = chunk("chunk_same_text", positive["text"])
        same_resolution = chunk(
            "chunk_same_resolution",
            "Otra publicación de la misma resolución.",
            resolution_reference="10-2020",
        )
        safe_one = chunk("chunk_safe_1", "Reglas sobre competencia territorial del juez.")
        safe_two = chunk("chunk_safe_2", "Plazos para una diligencia distinta.")
        corpus = [positive, article, same_text, same_resolution, safe_one, safe_two]
        result = ResolutionResult(
            candidates=[
                {"candidate_id": positive["chunk_id"], "chunk": positive, "relations": []},
                {"candidate_id": article["chunk_id"], "chunk": article, "relations": []},
            ],
            unresolved_references=[],
            relation_counts={},
        )
        pool = build_negative_candidate_pool(
            build_bm25(corpus),
            {
                "source_trace": {"title": "Parte civil y reparación"},
                "executive_summary": "La parte civil solicita reparación.",
                "legal_analysis": {},
            },
            result,
            max_candidates=10,
        )
        ids = {item["candidate_id"] for item in pool}
        self.assertNotIn("chunk_case", ids)
        self.assertNotIn("chunk_cpp_104", ids)
        self.assertNotIn("chunk_same_text", ids)
        self.assertNotIn("chunk_same_resolution", ids)
        self.assertEqual(ids, {"chunk_safe_1", "chunk_safe_2"})

    def test_negative_validation_rejects_collision_with_positive(self) -> None:
        positive = chunk("chunk_positive", "Texto jurídico idéntico")
        negative_pool = [
            {
                **chunk("chunk_negative", "Texto jurídico idéntico"),
                "candidate_id": "chunk_negative",
                "bm25_score": 10.0,
            }
        ]
        with self.assertRaisesRegex(ValueError, "duplican un positivo"):
            validate_hard_negative_candidate_ids(
                ["chunk_negative"], negative_pool, [positive]
            )

    def test_negative_validation_rejects_unknown_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "inexistentes"):
            validate_hard_negative_candidate_ids(
                ["chunk_inventado"],
                [{**chunk("chunk_safe", "Texto distinto"), "candidate_id": "chunk_safe"}],
                [chunk("chunk_positive", "Texto positivo")],
            )

    def test_historical_case_with_current_statute_is_flagged(self) -> None:
        context = build_temporal_context(
            {"source_trace": {"resolution_reference_raw": "RN 1969-2016"}},
            [
                chunk(
                    "chunk_cp_121b",
                    "Texto vigente",
                    source_type="tipo_02_codigo_penal",
                    article_id="121-B",
                )
            ],
        )
        self.assertEqual(context["case_reference_year"], 2016)
        self.assertEqual(context["status"], "requires_historical_version_review")

    def test_build_index_text_remains_compatible_with_test_chunks(self) -> None:
        value = build_index_text(chunk("chunk_1", "Texto de prueba"))
        self.assertIn("Texto de prueba", value)

    def test_training_records_reject_exact_positive_negative_collision(self) -> None:
        with self.assertRaisesRegex(ValueError, "mismo texto"):
            build_training_records(
                [
                    {
                        "dataset_id": "case_q001",
                        "case_id": "case",
                        "query": "Pregunta",
                        "topic": "procedimiento_penal",
                        "barrier": "desconocimiento_derechos",
                        "positive_chunks": [{"text": "Mismo texto jurídico"}],
                        "hard_negative_chunks": [{"text": "mismo texto juridico"}],
                    }
                ]
            )

    def test_retry_feedback_is_included_in_user_prompt(self) -> None:
        prompt = build_user_prompt(
            {"candidate_documents": [], "negative_candidate_documents": []},
            5,
            "candidate_id inexistente",
        )
        self.assertIn("CORRECCIÓN OBLIGATORIA", prompt)
        self.assertIn("candidate_id inexistente", prompt)


if __name__ == "__main__":
    unittest.main()
