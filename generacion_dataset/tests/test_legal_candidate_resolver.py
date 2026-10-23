from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from legal_candidate_resolver import (  # noqa: E402
    LegalCandidateResolver,
    SOURCE_CP,
    SOURCE_CPP,
    SOURCE_LEY_30364,
    article_reference_aliases,
    validate_positive_candidate_ids,
)


class LegalCandidateResolverTest(unittest.TestCase):
    def setUp(self) -> None:
        self.resolver = LegalCandidateResolver(
            article_rows={
                SOURCE_CP: [
                    {"article_id": "111", "title": "Homicidio culposo", "text": "Texto CP 111"},
                    {"article_id": "162", "title": "Artículo 162", "text": "Texto CP 162"},
                    {"article_id": "163", "title": "Artículo 163", "text": "Texto CP 163"},
                    {"article_id": "170", "title": "Artículo 170", "text": "Texto CP 170"},
                ],
                SOURCE_CPP: [
                    {"article_id": "429", "title": "Causales", "text": "Texto CPP 429 con numerales"},
                ],
                SOURCE_LEY_30364: [
                    {"article_id": "6", "heading": "Violencia familiar", "text": "Texto Ley 30364 artículo 6"},
                ],
            },
            context_units=[
                {
                    "entry_id": "jp_test_e0001",
                    "entry_url": "https://example.test/caso",
                    "provenance_sources": [
                        {"source_type": SOURCE_CP, "source_article_id": "111"},
                    ],
                    "context_unit": {
                        "applicable_norms": [
                            {
                                "norm_standardized": "Código Procesal Penal",
                                "norm_raw_text": "artículo 429.1 del CPP",
                                "articles": ["429.1"],
                            },
                            {
                                "norm_standardized": "Ley 30364",
                                "norm_raw_text": "artículo 999 inexistente",
                                "articles": ["999"],
                            },
                        ]
                    },
                }
            ],
            structured_entries=[
                {
                    "lp_entry_url": "https://example.test/caso/",
                    "page_source_url": "https://example.test/codigo-penal-articulo-111",
                    "page_concordances": [
                        {"code": "CP", "articles": ["111", "162-163"]},
                        {"code": "NCPP", "articles": ["429.1"]},
                    ],
                },
                {
                    "lp_entry_url": "https://example.test/caso/",
                    "page_source_url": "https://example.test/codigo-penal-articulo-170",
                    "page_concordances": [{"code": "CP", "articles": ["170"]}],
                },
            ],
        )
        self.jurisprudence = {
            "chunk_id": "chunk_tipo04_jp_test_e0001_01",
            "doc_id": "tipo04_jp_test_e0001",
            "source_type": "tipo_04_jurisprudencia",
            "title": "Sentencia de prueba",
            "text": "Criterio jurisprudencial de prueba",
            "metadata": {"resolution_reference": "CASACIÓN 1-2020"},
        }

    def test_aliases_resolve_numeral_and_range(self) -> None:
        self.assertEqual(article_reference_aliases("429.1"), ["429.1", "429"])
        self.assertEqual(article_reference_aliases("162-163"), ["162-163", "162", "163"])
        self.assertEqual(article_reference_aliases("IX Título Preliminar"), ["IXTÍTULOPRELIMINAR", "IX"])
        self.assertEqual(article_reference_aliases("II.1"), ["II.1", "II"])

    def test_resolves_and_deduplicates_candidates_with_provenance(self) -> None:
        result = self.resolver.resolve_case("jp_test_e0001", [self.jurisprudence])
        ids = result.candidate_ids

        self.assertIn("chunk_tipo04_jp_test_e0001_01", ids)
        self.assertIn("chunk_tipo02_cp_art_111_01", ids)
        self.assertIn("chunk_tipo03_cpp_art_429_01", ids)
        self.assertIn("chunk_tipo02_cp_art_162_01", ids)
        self.assertIn("chunk_tipo02_cp_art_163_01", ids)
        self.assertIn("chunk_tipo02_cp_art_170_01", ids)
        self.assertEqual(len(ids), 6)

        cp_111 = next(c for c in result.candidates if c["candidate_id"] == "chunk_tipo02_cp_art_111_01")
        relation_types = {relation["relation_type"] for relation in cp_111["relations"]}
        self.assertEqual(relation_types, {"source_article_anchor", "page_concordance"})

        self.assertEqual(len(result.unresolved_references), 1)
        self.assertEqual(result.unresolved_references[0]["raw_article_id"], "999")
        self.assertEqual(result.relation_counts["source_article_anchor_references_resolved"], 1)
        self.assertEqual(result.relation_counts["page_concordance_references_resolved"], 4)

    def test_selected_ids_must_belong_to_closed_set(self) -> None:
        result = self.resolver.resolve_case("jp_test_e0001", [self.jurisprudence])
        selected = validate_positive_candidate_ids(
            ["chunk_tipo02_cp_art_111_01", "chunk_tipo02_cp_art_111_01"],
            result,
        )
        self.assertEqual(selected, ["chunk_tipo02_cp_art_111_01"])

        with self.assertRaisesRegex(ValueError, "inexistentes"):
            validate_positive_candidate_ids(["chunk_inventado"], result)

    def test_missing_jurisprudence_is_reported(self) -> None:
        result = self.resolver.resolve_case("jp_test_e0001", [])
        unresolved_types = {item["relation_type"] for item in result.unresolved_references}
        self.assertIn("case_jurisprudence", unresolved_types)


if __name__ == "__main__":
    unittest.main()
