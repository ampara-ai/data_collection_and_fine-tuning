from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class ProcessArticle:
    article_id: str
    heading: str
    title: str
    text: str
    jurisprudence_url: str | None
    source_url: str
    keyword_hits: dict[str, list[str]]
    heuristic_score: int
    candidate_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
