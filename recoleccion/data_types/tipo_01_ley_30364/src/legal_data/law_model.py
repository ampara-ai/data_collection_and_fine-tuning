from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Article:
    article_id: str
    heading: str | None
    text: str


@dataclass
class LawDocument:
    norm_id: str
    code: str
    title: str
    source: str
    articles: list[Article]
    complementary_provisions: list[dict[str, Any]]
    annexes: list[dict[str, Any]]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "norm_id": self.norm_id,
            "code": self.code,
            "title": self.title,
            "source": self.source,
            "articles": [asdict(article) for article in self.articles],
            "complementary_provisions": self.complementary_provisions,
            "annexes": self.annexes,
            "metadata": self.metadata,
        }
