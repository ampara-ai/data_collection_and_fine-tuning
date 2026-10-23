from __future__ import annotations

import unittest

from legal_data.collector import (
    merge_articles,
    validate_complete_numeric_coverage,
    validate_part,
)
from legal_data.models import ProcessArticle
from legal_data.parser import parse_cpp_html


def article(article_id: str, text: str | None = None) -> ProcessArticle:
    return ProcessArticle(
        article_id=article_id,
        heading=f"Artículo {article_id}",
        title=f"Artículo {article_id}",
        text=text or f"Texto {article_id}",
        jurisprudence_url=None,
        source_url="https://example.test/cpp",
        keyword_hits={"strong": [], "medium": [], "context": [], "negative": []},
        heuristic_score=0,
        candidate_status="unscored",
    )


class CollectorTests(unittest.TestCase):
    def test_parser_stops_article_at_non_article_heading(self) -> None:
        html = """
        <div class="td-post-content">
          <h4>Artículo 566. Ejecución de las penas</h4>
          <p>Texto propio del artículo.</p>
          <h2>DISPOSICIONES COMPLEMENTARIAS</h2>
          <h4>Primera. Vigencia</h4>
          <p>Este texto no pertenece al artículo 566.</p>
        </div>
        """
        parsed = parse_cpp_html(html, "https://example.test/parte-2")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].article_id, "566")
        self.assertEqual(parsed[0].text, "Texto propio del artículo.")

    def test_merge_preserves_source_order(self) -> None:
        merged = merge_articles([[article("I"), article("1")], [article("2")]])
        self.assertEqual([item.article_id for item in merged], ["I", "1", "2"])

    def test_merge_rejects_conflicting_duplicates(self) -> None:
        with self.assertRaisesRegex(ValueError, "contenido contradictorio"):
            merge_articles([[article("1", "versión A")], [article("1", "versión B")]])

    def test_part_requires_boundary_articles(self) -> None:
        with self.assertRaisesRegex(ValueError, "faltan artículos límite"):
            validate_part([article("446")], part_id="parte_2", required_article_ids=("446", "566"))

    def test_complete_numeric_coverage_accepts_inserted_articles(self) -> None:
        articles = [article("I"), article("1"), article("1-A"), article("2")]
        report = validate_complete_numeric_coverage(
            articles,
            first_article=1,
            last_article=2,
        )
        self.assertEqual(report["numeric_articles"], 2)
        self.assertEqual(report["non_numeric_or_inserted_articles"], 2)

    def test_complete_numeric_coverage_rejects_gaps(self) -> None:
        with self.assertRaisesRegex(ValueError, r"faltan: \['2'\]"):
            validate_complete_numeric_coverage(
                [article("1"), article("3")],
                first_article=1,
                last_article=3,
            )


if __name__ == "__main__":
    unittest.main()
